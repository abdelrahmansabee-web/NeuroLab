# -*- coding: utf-8 -*-
"""
Stroke Kinematic Analysis — view-agnostic pipeline.
Compatible with: mediapipe_csv_extractor.py + raw MediaPipe landmark CSV.

Variables: SPARC, trunk_ratio, shoulder_elevation, hand_displacement_norm, movement_time, peak_velocity
Camera: auto-detect (side / frontal / oblique) — not side-view-only.
Phone video (~30 fps) is upsampled to 60 Hz (cubic spline) before SPARC/velocity metrics.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.fft import fft
from scipy.interpolate import CubicSpline
from scipy.signal import find_peaks

DEFAULT_FRAME_WIDTH = 1920
DEFAULT_FRAME_HEIGHT = 1080
DEFAULT_FS = 60.0
DEFAULT_VELOCITY_THRESHOLD_PX_S = 5.0
ANALYSIS_TARGET_FS = 60.0
NATIVE_FS_UPSAMPLE_BELOW = 55.0

_UPSAMPLE_COORD_COLS = [
    "palm_x", "palm_y", "wrist_x", "wrist_y",
    "trunk_x", "trunk_y", "shoulder_x", "shoulder_y",
    "elbow_x", "elbow_y",
]
_UPSAMPLE_VIS_COLS = [
    "palm_visibility", "wrist_visibility", "shoulder_visibility",
    "elbow_visibility", "trunk_visibility",
]


def _parse_arm_side(val: str) -> Optional[str]:
    v = (val or "").strip().lower()
    if v in ("left", "1", "l", "sol"):
        return "left"
    if v in ("right", "2", "r", "sag"):
        return "right"
    return None


def resolve_analysis_arm(
    phase: str = "pre",
    stroke_side: str = "auto",
    affected_side: str = "auto",
) -> str:
    """
    Resolve which arm to analyze.
    - pre/post: paretic side (stroke_side)
    - baseline/healthy: contralateral healthy arm
    - explicit affected_side overrides when left/right
    """
    ph = (phase or "pre").strip().lower()

    stroke = _parse_arm_side(stroke_side)
    if ph in ("baseline", "healthy"):
        if stroke:
            return "right" if stroke == "left" else "left"
        explicit = _parse_arm_side(affected_side)
        if explicit:
            return "right" if explicit == "left" else "left"
        return "auto"

    explicit = _parse_arm_side(affected_side)
    if explicit:
        return explicit

    if stroke:
        return stroke

    return "auto"


# ============================================================
# 1. SPARC
# ============================================================

def _sparc_quality_advisory(
    sparc_value: Optional[float],
    sparc_comparable: bool,
    active_frames: int,
    fs: float,
    amplitude_sw: float,
    speed_space: str,
) -> Dict[str, object]:
    """
    Clinical/technical advisory for SPARC reliability.

    Literature (Balasubramanian et al. 2012; 2015):
      - SPARC requires a clear, isolated reach bout.
      - Noisy/short windows inflate SPARC toward zero (less negative).
      - Values outside [-6, 0] or near 0 should be flagged.
    """
    flags = []
    notes = []

    if sparc_value is None or not np.isfinite(float(sparc_value)):
        flags.append("sparc_not_computed")
        notes.append("SPARC could not be computed from the selected window.")
    else:
        sp = float(sparc_value)
        if sp > -0.5:
            flags.append("sparc_near_zero")
            notes.append("SPARC is near zero; likely a very short or noisy window.")
        elif sp < -6.0:
            flags.append("sparc_very_negative")
            notes.append("SPARC is very negative; severe segmentation or tracking artifact.")
        if not sparc_comparable:
            flags.append("sparc_window_not_comparable")
            notes.append("Reach amplitude < 0.15 SW or duration < 0.35 s; SPARC may not be comparable.")

    dur_s = active_frames / fs if fs > 0 else 0.0
    if dur_s < 0.35:
        flags.append("sparc_window_short")
        notes.append(f"SPARC window duration ({dur_s:.2f}s) is below literature minimum (0.35s).")
    if amplitude_sw < 0.15:
        flags.append("sparc_amplitude_small")
        notes.append(f"Reach amplitude ({amplitude_sw:.2f} SW) is below literature minimum (0.15 SW).")

    if speed_space != "body_frame":
        flags.append("sparc_not_body_frame")
        notes.append(f"SPARC computed in {speed_space} space; body-frame preferred when shoulder tracking is reliable.")

    if not flags:
        notes.append("SPARC window appears suitable for literature comparison.")

    return {
        "sparc_reliable": len([f for f in flags if f not in ("sparc_not_body_frame",)]) == 0,
        "flags": flags,
        "notes": notes,
        "active_frames": active_frames,
        "active_duration_s": round(dur_s, 3),
        "amplitude_sw": round(amplitude_sw, 3) if np.isfinite(amplitude_sw) else None,
        "speed_space": speed_space,
    }

def calculate_sparc_from_speed(
    v: np.ndarray,
    fs: float = 60.0,
    padlevel: int = 4,
    fc: float = 20.0,
    amp_th: float = 0.05,
) -> float:
    """
    SPARC on tangential speed profile (Balasubramanian et al.).
    v: speed samples during movement window; no pre-filtering.
    """
    v = np.asarray(v, dtype=float)
    if len(v) < 10 or np.all(v == 0):
        return float("nan")

    t_span = len(v) / fs
    path_len = float(np.sum(v)) / fs
    if path_len == 0:
        return float("nan")
    v_norm = v * t_span / path_len

    nfft = int(pow(2, np.ceil(np.log2(len(v_norm))) + padlevel))
    f = np.arange(0, fs, fs / nfft)
    mf = abs(fft(v_norm, nfft))
    peak = max(mf) if len(mf) else 0.0
    if peak == 0:
        return float("nan")
    mf = mf / peak

    fc_idx = np.where(f <= fc)[0]
    if len(fc_idx) == 0:
        return float("nan")

    f_sel = f[fc_idx]
    mf_sel = mf[fc_idx]

    amp_idx = np.where(mf_sel >= amp_th)[0]
    if len(amp_idx) == 0:
        return float("nan")

    fc_range = range(amp_idx[0], amp_idx[-1] + 1)
    f_sel = f_sel[fc_range]
    mf_sel = mf_sel[fc_range]

    if len(f_sel) < 2:
        return float("nan")

    denom = f_sel[-1] - f_sel[0]
    if denom == 0:
        return float("nan")

    return float(
        -np.sum(
            np.sqrt(
                np.power(np.diff(f_sel) / denom, 2) + np.power(np.diff(mf_sel), 2)
            )
        )
    )


def calculate_multi_reach_sparc(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    shoulder_x: Optional[np.ndarray] = None,
    shoulder_y: Optional[np.ndarray] = None,
    n_reaches: int = 3,
    min_amplitude_sw: float = 0.12,
    min_duration_s: float = 0.50,
    **sparc_kw,
) -> Dict[str, object]:
    """
    Compute SPARC for the first N valid reach bouts and return their median.

    Literature (Balasubramanian et al. 2012): SPARC is a single-bout metric.
    When multiple comparable reaches exist, the median SPARC is more robust to
    one noisy bout than a single arbitrarily chosen reach.
    """
    from motion_invariants import (
        body_frame_palm,
        literature_reach_window,
        palm_image_speed,
        smooth_series,
        _list_segments,
    )

    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    sx = shoulder_x if shoulder_x is not None else np.full_like(px, px[0])
    sy = shoulder_y if shoulder_y is not None else np.full_like(py, py[0])
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )

    bx, by, _, _ = body_frame_palm(px, py, sx, sy, sw)
    bx_s = smooth_series(bx, fs)
    by_s = smooth_series(by, fs)

    spd = palm_image_speed(px, py, fs)
    segments = []
    segs = _list_segments(
        spd, px, py, fs, velocity_threshold=3.0,
        max_gap_frames=6, min_segment_frames=10,
    )
    for s in segs:
        on, off = int(s["start"]), int(s["end"])
        if off - on + 1 < 10:
            continue
        amp = float(np.hypot(bx[off] - bx[on], by[off] - by[on]))
        dur = (off - on + 1) / fs
        if dur >= min_duration_s and amp >= min_amplitude_sw:
            segments.append((on, off, amp))

    segments = sorted(segments, key=lambda x: -x[2])[:n_reaches]

    sparcs = []
    windows = []
    for on, off, _ in segments:
        try:
            sp = calculate_sparc(bx_s[on:off+1], by_s[on:off+1], fs=fs, **sparc_kw)
            if np.isfinite(sp):
                sparcs.append(float(sp))
                windows.append((on, off))
        except Exception:
            continue

    if not sparcs:
        return {"sparc_median": float("nan"), "sparcs": [], "windows": [], "n_valid": 0}

    return {
        "sparc_median": float(np.median(sparcs)),
        "sparcs": [round(s, 4) for s in sparcs],
        "windows": windows,
        "n_valid": len(sparcs),
    }


from motion_invariants import _lowpass_filter_speed

def calculate_sparc(
    x: np.ndarray,
    y: np.ndarray,
    fs: float = 60.0,
    padlevel: int = 4,
    fc: float = 10.0,
    amp_th: float = 0.05,
    smooth_speed: bool = True,
    smooth_cutoff_hz: float = 10.0,
) -> float:
    """
    SPARC on a 2D trajectory.

    Literature default (Balasubramanian et al. 2012):
      - Speed is computed from central differences.
      - A 10 Hz zero-phase low-pass filter is applied to the speed profile
        before SPARC to reduce differentiation/tracking noise.
      - Spectrum cut-off fc = 10 Hz, amplitude threshold = 0.05.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 10 or len(y) < 10:
        return float("nan")

    vx = np.gradient(x) * fs
    vy = np.gradient(y) * fs
    v = np.sqrt(vx**2 + vy**2)

    if smooth_speed and len(v) >= 7 and fs > 0 and smooth_cutoff_hz > 0:
        v = _lowpass_filter_speed(v, fs, cutoff_hz=smooth_cutoff_hz)

    return calculate_sparc_from_speed(v, fs=fs, padlevel=padlevel, fc=fc, amp_th=amp_th)



def _bridge_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    """Merge short inactive gaps (tracking dropouts) within one reach."""
    if max_gap <= 0 or not np.any(mask):
        return mask
    out = mask.copy()
    n = len(out)
    i = 0
    while i < n:
        if out[i]:
            i += 1
            continue
        g0 = i
        while i < n and not out[i]:
            i += 1
        gap = i - g0
        if gap <= max_gap and g0 > 0 and i < n and out[g0 - 1] and out[i]:
            out[g0:i] = True
    return out


def _movement_window(
    palm_speed: np.ndarray,
    fs: float,
    velocity_threshold: float,
    max_gap_frames: int = 6,
    min_segment_frames: int = 10,
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
    shoulder_width: Optional[float] = None,
) -> Tuple[int, int]:
    """
    Detect the primary reaching movement.

    When palm coordinates are supplied, picks the reach with the strongest
    peak×path score (not merely the longest low-speed drift).
    """
    if palm_x is not None and palm_y is not None and len(palm_x) == len(palm_speed):
        from motion_invariants import primary_reach_window

        return primary_reach_window(
            palm_speed,
            palm_x,
            palm_y,
            fs,
            velocity_threshold=velocity_threshold,
            shoulder_width=shoulder_width,
            max_gap_frames=max_gap_frames,
            min_segment_frames=min_segment_frames,
            coords_in_sw=shoulder_width is None,
        )

    if len(palm_speed) == 0:
        return 0, 0
    peak = float(np.max(palm_speed))
    thr = max(float(velocity_threshold), 0.05 * peak)
    mask = _bridge_gaps(palm_speed > thr, max_gap_frames)

    best_s, best_e, best_len = 0, 0, 0
    i, n = 0, len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        seg_len = j - i
        if seg_len > best_len:
            best_s, best_e, best_len = i, j - 1, seg_len
        i = j

    if best_len < min_segment_frames:
        idx = np.where(palm_speed > thr)[0]
        if len(idx) >= min_segment_frames:
            return int(idx[0]), int(idx[-1])
        return 0, max(0, n - 1)
    return best_s, best_e


def calculate_sparc_movement_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    min_segment_frames: int = 10,
    shoulder_x: Optional[np.ndarray] = None,
    shoulder_y: Optional[np.ndarray] = None,
    shoulder_width: Optional[float] = None,
    palm_z: Optional[np.ndarray] = None,
    shoulder_z: Optional[np.ndarray] = None,
    move_start: Optional[int] = None,
    move_end: Optional[int] = None,
    analysis_profile: str = "uniform",
    reference_amplitude_sw: Optional[float] = None,
    target_amplitude_sw: Optional[float] = None,
    sparc_window_method: str = "literature_5pct",
    **sparc_kw,
) -> Tuple[float, int, int, int, float, bool, int, int]:
    """
    SPARC on the outbound reach in a shoulder-centered, SW-normalized frame.

    reference (unaffected): first speed bell — smooth normative profile.
    affected (pre/post): same bell metric on outbound segment — impairment
    shows as more negative SPARC vs reference.

    Less negative = smoother.
    Returns (sparc, sparc_frames, move_start, move_end, reach_amplitude_sw,
             sparc_comparable, sparc_window_start, sparc_window_end, speed_space).
    """
    from motion_invariants import (
        amplitude_matched_reach_window,
        body_frame_palm,
        reach_amplitude_sw,
        reach_speed_series,
        select_literature_matched_window,
        select_reach_window,
        smooth_series,
        sparc_bell_window,
        sparc_quality_ok,
        sparc_speed_profile,
    )

    sx = shoulder_x if shoulder_x is not None else np.full_like(palm_x, palm_x[0])
    sy = shoulder_y if shoulder_y is not None else np.full_like(palm_y, palm_y[0])
    bx, by, bz, _sw = body_frame_palm(
        palm_x, palm_y, sx, sy, shoulder_width, palm_z=palm_z, shoulder_z=shoulder_z
    )
    bx_s = smooth_series(bx, fs)
    by_s = smooth_series(by, fs)
    if bz is not None:
        bz_s = smooth_series(bz, fs)
    else:
        bz_s = bz

    if move_start is None or move_end is None:
        if sparc_window_method == "literature_5pct":
            move_start, move_end = select_literature_matched_window(
                palm_x,
                palm_y,
                fs,
                shoulder_width=shoulder_width,
                reference_amplitude_sw=reference_amplitude_sw,
                velocity_threshold_frac=0.05,
                min_duration_s=0.50,
                min_amplitude_sw=0.12,
                amplitude_tolerance=0.20,
            )
        else:
            move_start, move_end = select_reach_window(
                palm_x,
                palm_y,
                fs,
                shoulder_width=shoulder_width,
                velocity_threshold=velocity_threshold,
                min_segment_frames=min_segment_frames,
                analysis_profile=analysis_profile,
            )
    move_start, move_end = int(move_start), int(move_end)

    # SPARC should reflect the primary ballistic reach (rest -> target). Cap the
    # offset at the first forward-reach displacement peak so return/wipe/correction
    # phases do not contaminate the smoothness metric (Balasubramanian et al.).
    from motion_invariants import forward_reach_window

    fwd_on, fwd_off, _ = forward_reach_window(
        palm_x, palm_y, fs,
        shoulder_width=shoulder_width if shoulder_width and shoulder_width > 0 else _sw,
        min_segment_frames=min_segment_frames,
    )
    if fwd_off - fwd_on + 1 >= min_segment_frames and fwd_on <= move_end:
        move_start = max(move_start, fwd_on)
        move_end = min(move_end, fwd_off)
        if move_end - move_start + 1 < min_segment_frames:
            move_end = min(len(palm_x) - 1, move_start + min_segment_frames - 1)

    speed_raw, speed_space = sparc_speed_profile(
        palm_x,
        palm_y,
        sx,
        sy,
        shoulder_width,
        fs,
        move_start,
        move_end,
        palm_z=palm_z,
        shoulder_z=shoulder_z,
    )

    if sparc_window_method == "literature_5pct":
        from motion_invariants import literature_reach_window

        sparc_start, sparc_end = literature_reach_window(
            speed_raw, fs, v_frac=0.05,
            search_start=move_start, search_end=move_end, min_segment_frames=min_segment_frames,
        )
    else:
        sparc_start, sparc_end = sparc_bell_window(
            speed_raw,
            move_start,
            move_end,
            min_segment_frames=min_segment_frames,
        )

    if (sparc_end - sparc_start + 1) / fs < 0.35:
        speed_2d = reach_speed_series(bx, by, None, fs)
        if sparc_window_method == "literature_5pct":
            from motion_invariants import literature_reach_window

            sparc_start, sparc_end = literature_reach_window(
                speed_2d, fs, v_frac=0.05,
                search_start=move_start, search_end=move_end, min_segment_frames=min_segment_frames,
            )
        else:
            sparc_start, sparc_end = sparc_bell_window(
                speed_2d,
                move_start,
                move_end,
                min_segment_frames=min_segment_frames,
            )
        speed_raw = speed_2d
        speed_space = "body_frame_2d"

    fc_hz = min(float(sparc_kw.get("fc", 10.0)), 20.0)
    amp_th = float(sparc_kw.get("amp_th", 0.05))

    n_frames = sparc_end - sparc_start + 1
    move_dur_s = (move_end - move_start + 1) / fs
    amp_sw = reach_amplitude_sw(bx_s, by_s, bz_s, move_start, move_end)
    comparable = sparc_quality_ok(
        amp_sw, n_frames, fs, movement_duration_s=move_dur_s
    )

    if n_frames < min_segment_frames:
        return float("nan"), 0, move_start, move_end, float(amp_sw), False, sparc_start, sparc_end, speed_space

    # Outlier rejection: drop isolated speed spikes >3 SD from median before SPARC.
    sparc_speed = np.asarray(speed_raw[sparc_start : sparc_end + 1], dtype=float)
    if len(sparc_speed) > 10:
        med = float(np.median(sparc_speed))
        mad = float(np.median(np.abs(sparc_speed - med)))
        if mad > 1e-9:
            threshold = med + 3.0 * 1.4826 * mad
            sparc_speed = np.clip(sparc_speed, 0.0, threshold)

    sparc = calculate_sparc_from_speed(
        sparc_speed,
        fs=fs,
        fc=fc_hz,
        amp_th=amp_th,
    )
    return (
        sparc,
        int(n_frames),
        move_start,
        move_end,
        float(amp_sw),
        bool(comparable),
        int(sparc_start),
        int(sparc_end),
        speed_space,
    )


# ============================================================
# Physical forward displacement fallback
# ============================================================

def _forward_displacement_cm_along_axis(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    start: int,
    end: int,
    cm_per_px: Optional[float],
) -> Optional[float]:
    """
    Net forward displacement of the palm along the initial reach axis,
    using trunk-relative coordinates and table-derived cm/px scale.
    """
    if end <= start or not cm_per_px or cm_per_px <= 0:
        return None
    rx = np.asarray(palm_x, dtype=float) - np.asarray(trunk_x, dtype=float)
    ry = np.asarray(palm_y, dtype=float) - np.asarray(trunk_y, dtype=float)
    span = end - start
    early_i = start + max(3, min(int(0.15 * span), 12))
    ax = float(rx[early_i] - rx[start])
    ay = float(ry[early_i] - ry[start])
    am = float(np.hypot(ax, ay))
    if am < 2.0:
        return None
    ux, uy = ax / am, ay / am
    proj = (rx[end] - rx[start]) * ux + (ry[end] - ry[start]) * uy
    return float(proj * cm_per_px)


def _net_palm_displacement_cm(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    start: int,
    end: int,
    cm_per_px: Optional[float],
) -> Optional[float]:
    """Net Euclidean palm displacement over the window, in cm."""
    if end <= start or not cm_per_px or cm_per_px <= 0:
        return None
    dx = float(palm_x[end] - palm_x[start])
    dy = float(palm_y[end] - palm_y[start])
    return float(np.hypot(dx, dy) * cm_per_px)


# ============================================================
# 2. TRUNK RATIO
# ============================================================

def calculate_trunk_ratio(
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    shoulder_width: Optional[float] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> Tuple[float, float, float, float]:
    palm_vx = np.gradient(palm_x) * fs
    palm_vy = np.gradient(palm_y) * fs
    palm_speed = np.sqrt(palm_vx**2 + palm_vy**2)

    if start_idx is None or end_idx is None:
        start_idx, end_idx = _movement_window(
            palm_speed, fs, velocity_threshold,
            palm_x=palm_x, palm_y=palm_y, shoulder_width=shoulder_width,
        )
    if (end_idx - start_idx) < 10:
        return float("nan"), float("nan"), float("nan"), float("nan")

    trunk_seg_x = trunk_x[start_idx : end_idx + 1]
    trunk_seg_y = trunk_y[start_idx : end_idx + 1]
    palm_seg_x = palm_x[start_idx : end_idx + 1]
    palm_seg_y = palm_y[start_idx : end_idx + 1]

    trunk_path = float(np.sum(np.hypot(np.diff(trunk_seg_x), np.diff(trunk_seg_y))))
    palm_path = float(np.sum(np.hypot(np.diff(palm_seg_x), np.diff(palm_seg_y))))

    trunk_disp = float(np.hypot(trunk_x[end_idx] - trunk_x[start_idx], trunk_y[end_idx] - trunk_y[start_idx]))
    palm_disp = float(np.hypot(palm_x[end_idx] - palm_x[start_idx], palm_y[end_idx] - palm_y[start_idx]))

    if shoulder_width and shoulder_width > 0:
        palm_den = max(palm_disp, 0.08 * shoulder_width)
    else:
        palm_den = max(palm_disp, 10.0)

    trunk_disp_ratio = trunk_disp / palm_den if palm_den > 0 else float("nan")
    trunk_path_ratio = trunk_path / max(palm_path, palm_den * 0.5) if palm_path > 0 else float("nan")

    return trunk_disp_ratio, trunk_disp, palm_disp, trunk_path_ratio


def calculate_hand_displacement_trunk_relative(
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    shoulder_width: Optional[float] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> Tuple[float, float, float, float]:
    """
    Peak hand reach relative to trunk proxy (shoulder-girdle midpoint).

    Whole-body lean/translation moves trunk and palm together → low trunk-relative
    reach (anti-cheat). Normalized by shoulder width for cross-subject comparison.
    """
    if start_idx is None or end_idx is None or (end_idx - start_idx) < 10:
        return float("nan"), float("nan"), float("nan"), float("nan")

    rel_x = palm_x - trunk_x
    rel_y = palm_y - trunk_y
    rx0 = float(rel_x[start_idx])
    ry0 = float(rel_y[start_idx])

    seg_x = rel_x[start_idx : end_idx + 1] - rx0
    seg_y = rel_y[start_idx : end_idx + 1] - ry0
    dists = np.hypot(seg_x, seg_y)
    peak_px = float(np.max(dists)) if len(dists) else float("nan")

    palm_raw = float(
        np.hypot(palm_x[end_idx] - palm_x[start_idx], palm_y[end_idx] - palm_y[start_idx])
    )
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    norm = peak_px / sw if np.isfinite(sw) and sw > 0 and np.isfinite(peak_px) else float("nan")
    cheat_ratio = (
        palm_raw / max(peak_px, 1e-6)
        if np.isfinite(palm_raw) and np.isfinite(peak_px) and peak_px > 1e-6
        else float("nan")
    )
    return norm, peak_px, palm_raw, cheat_ratio


# ============================================================
# 3. SHOULDER ELEVATION
# ============================================================

def calculate_shoulder_elevation_range(
    shoulder_y: np.ndarray,
    shoulder_width: Optional[float],
    fs: float,
    velocity_threshold: float,
    palm_speed: np.ndarray,
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
) -> Tuple[float, float]:
    """Range-based shoulder excursion during the primary reach."""
    win_kw: Dict[str, Any] = {}
    if palm_x is not None and palm_y is not None:
        win_kw = {"palm_x": palm_x, "palm_y": palm_y, "shoulder_width": shoulder_width}
    start_idx, end_idx = _movement_window(palm_speed, fs, velocity_threshold, **win_kw)
    if (end_idx - start_idx) < 10:
        return float("nan"), float("nan")
    seg = shoulder_y[start_idx : end_idx + 1]
    elev_abs = float(seg.max() - seg.min())
    elev_norm = elev_abs / shoulder_width if shoulder_width and shoulder_width > 0 else elev_abs
    return elev_norm, elev_abs


def calculate_shoulder_elevation_adaptive(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    shoulder_width: Optional[float],
    fs: float,
    velocity_threshold: float,
    palm_speed: np.ndarray,
    camera_view: str = "auto",
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
) -> Tuple[float, float, str]:
    """
    Shoulder elevation — auto-picks the method with the stronger normalized signal.
    Does not gate on camera-view label (body orientation in frame varies per session).
    """
    _ = camera_view  # legacy API; kept for callers
    kw = dict(
        shoulder_width=shoulder_width,
        fs=fs,
        velocity_threshold=velocity_threshold,
        palm_speed=palm_speed,
        palm_x=palm_x,
        palm_y=palm_y,
    )
    peak_norm, peak_abs = calculate_shoulder_elevation(
        shoulder_x,
        shoulder_y,
        shoulder_width=shoulder_width,
        fs=fs,
        velocity_threshold=velocity_threshold,
        palm_speed=palm_speed,
        palm_x=palm_x,
        palm_y=palm_y,
    )
    range_norm, range_abs = calculate_shoulder_elevation_range(shoulder_y, **kw)

    candidates = []
    if np.isfinite(peak_norm):
        candidates.append((abs(peak_norm), peak_norm, peak_abs, "rest_to_peak_y"))
    if np.isfinite(range_norm):
        candidates.append((abs(range_norm), range_norm, range_abs, "range_y_norm"))
    if not candidates:
        return float("nan"), float("nan"), "none"
    _, norm, abs_px, method = max(candidates, key=lambda t: t[0])
    return norm, abs_px, method


def _resolve_camera_view(df: pd.DataFrame, camera_view: str) -> str:
    view = (camera_view or "auto").lower()
    if view != "auto":
        return view
    if "camera_view" in df.columns:
        v = str(df["camera_view"].iloc[0]).lower()
        if v and v != "nan":
            return v
    if "LEFT_SHOULDER_X" in df.columns:
        fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else DEFAULT_FRAME_WIDTH
        fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else DEFAULT_FRAME_HEIGHT
        from mediapipe_csv_extractor import detect_camera_view

        return detect_camera_view(df, fw, fh)
    return "unknown"


def _resolve_affected_side(df: pd.DataFrame, affected_side: str) -> str:
    side = (affected_side or "auto").lower()
    if side in ("left", "right"):
        return side
    if "affected_side" in df.columns:
        s = str(df["affected_side"].iloc[0]).lower()
        if s in ("left", "right"):
            return s
    if "LEFT_WRIST_X" in df.columns:
        fw = int(df["frame_width_px"].iloc[0]) if "frame_width_px" in df.columns else DEFAULT_FRAME_WIDTH
        fh = int(df["frame_height_px"].iloc[0]) if "frame_height_px" in df.columns else DEFAULT_FRAME_HEIGHT
        from mediapipe_csv_extractor import detect_affected_side

        return detect_affected_side(df, fw, fh)
    return "left"


def calculate_shoulder_elevation(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    shoulder_width: Optional[float] = None,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    palm_speed: Optional[np.ndarray] = None,
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> Tuple[float, float]:
    if start_idx is None or end_idx is None:
        if palm_speed is None:
            shoulder_vx = np.gradient(shoulder_x) * fs
            shoulder_vy = np.gradient(shoulder_y) * fs
            palm_speed = np.sqrt(shoulder_vx**2 + shoulder_vy**2)

        win_kw: Dict[str, Any] = {}
        if palm_x is not None and palm_y is not None:
            win_kw = {"palm_x": palm_x, "palm_y": palm_y, "shoulder_width": shoulder_width}
        start_idx, end_idx = _movement_window(palm_speed, fs, velocity_threshold, **win_kw)
    if (end_idx - start_idx) < 10:
        return float("nan"), float("nan")

    rest_frames = min(10, (end_idx - start_idx) // 10)
    rest_frames = max(rest_frames, 1)
    shoulder_y_rest = float(np.mean(shoulder_y[start_idx : start_idx + rest_frames]))
    shoulder_y_peak = float(np.min(shoulder_y[start_idx : end_idx + 1]))
    shoulder_elevation_abs = shoulder_y_rest - shoulder_y_peak

    if shoulder_width is not None and shoulder_width > 0:
        shoulder_elevation_norm = shoulder_elevation_abs / shoulder_width
    else:
        shoulder_elevation_norm = shoulder_elevation_abs

    return shoulder_elevation_norm, shoulder_elevation_abs


# ============================================================
# 4. ELBOW ANGLE
# ============================================================

def calculate_elbow_angle(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    palm_speed: Optional[np.ndarray] = None,
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
    shoulder_width: Optional[float] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> Tuple[float, float, float]:
    if palm_speed is None:
        wx = palm_x if palm_x is not None else wrist_x
        wy = palm_y if palm_y is not None else wrist_y
        wrist_vx = np.gradient(wx) * fs
        wrist_vy = np.gradient(wy) * fs
        palm_speed = np.sqrt(wrist_vx**2 + wrist_vy**2)

    if start_idx is None or end_idx is None:
        win_kw: Dict[str, Any] = {}
        px = palm_x if palm_x is not None else wrist_x
        py = palm_y if palm_y is not None else wrist_y
        if px is not None and py is not None:
            win_kw = {"palm_x": px, "palm_y": py, "shoulder_width": shoulder_width}
        start_idx, end_idx = _movement_window(palm_speed, fs, velocity_threshold, **win_kw)
    if (end_idx - start_idx) < 10:
        return float("nan"), float("nan"), float("nan")

    angles = []
    for i in range(start_idx, end_idx + 1):
        v1_x = shoulder_x[i] - elbow_x[i]
        v1_y = shoulder_y[i] - elbow_y[i]
        v2_x = wrist_x[i] - elbow_x[i]
        v2_y = wrist_y[i] - elbow_y[i]

        mag1 = np.sqrt(v1_x**2 + v1_y**2)
        mag2 = np.sqrt(v2_x**2 + v2_y**2)
        if mag1 == 0 or mag2 == 0:
            continue

        cos_angle = np.clip((v1_x * v2_x + v1_y * v2_y) / (mag1 * mag2), -1.0, 1.0)
        angles.append(np.arccos(cos_angle) * 180 / np.pi)

    if not angles:
        return float("nan"), float("nan"), float("nan")

    arr = np.array(angles)
    return float(np.mean(arr)), float(np.min(arr)), float(np.max(arr))


# ============================================================
# 5. MOVEMENT TIME
# ============================================================

def calculate_movement_time(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    shoulder_width: Optional[float] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> float:
    vx = np.gradient(palm_x) * fs
    vy = np.gradient(palm_y) * fs
    speed = np.sqrt(vx**2 + vy**2)

    if start_idx is None or end_idx is None:
        start_idx, end_idx = _movement_window(
            speed, fs, velocity_threshold, palm_x=palm_x, palm_y=palm_y, shoulder_width=shoulder_width
        )
    if (end_idx - start_idx) < 5:
        return float("nan")

    return (end_idx - start_idx + 1) / fs


# ============================================================
# 6. PEAK VELOCITY
# ============================================================

def calculate_peak_velocity(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float = 60.0,
    velocity_threshold: float = 5.0,
    shoulder_width: Optional[float] = None,
    shoulder_x: Optional[np.ndarray] = None,
    shoulder_y: Optional[np.ndarray] = None,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> Tuple[float, float, float]:
    from motion_invariants import body_frame_palm, reach_speed_series, smooth_series

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else None
    if (
        sw
        and shoulder_x is not None
        and shoulder_y is not None
        and len(shoulder_x) == len(palm_x)
    ):
        bx, by, _, _ = body_frame_palm(
            np.asarray(palm_x, dtype=float),
            np.asarray(palm_y, dtype=float),
            np.asarray(shoulder_x, dtype=float),
            np.asarray(shoulder_y, dtype=float),
            sw,
        )
        bx = smooth_series(bx, fs, window_s=0.11)
        by = smooth_series(by, fs, window_s=0.11)
        speed = reach_speed_series(bx, by, None, fs) * sw
    else:
        px_s = smooth_series(np.asarray(palm_x, dtype=float), fs, window_s=0.12)
        py_s = smooth_series(np.asarray(palm_y, dtype=float), fs, window_s=0.12)
        vx = np.gradient(px_s) * fs
        vy = np.gradient(py_s) * fs
        speed = np.sqrt(vx**2 + vy**2)

    if start_idx is None or end_idx is None:
        start_idx, end_idx = _movement_window(
            speed, fs, velocity_threshold,
            palm_x=palm_x, palm_y=palm_y, shoulder_width=shoulder_width,
        )
    if (end_idx - start_idx) < 5:
        return float("nan"), float("nan"), float("nan")

    movement_speed = speed[start_idx : end_idx + 1]
    peak_velocity = float(np.max(movement_speed))
    peak_idx = int(np.argmax(movement_speed)) + start_idx
    time_to_peak_velocity = (peak_idx - start_idx) / fs
    movement_time = (end_idx - start_idx + 1) / fs
    relative_time_to_peak = (time_to_peak_velocity / movement_time) * 100 if movement_time > 0 else float("nan")

    return peak_velocity, time_to_peak_velocity, relative_time_to_peak


# ============================================================
# 6b. REACH-TO-GRASP PRIMARY METRICS (protocol-aligned)
# ============================================================

def calculate_nvp(
    speed: np.ndarray,
    prominence_frac: float = 0.30,
) -> int:
    """Number of velocity peaks (local maxima) in the palm speed profile."""
    if len(speed) < 5:
        return 0
    std = float(np.nanstd(speed))
    peak = float(np.nanmax(speed))
    prominence = std * prominence_frac if std > 0 else peak * 0.05
    peaks, _ = find_peaks(speed, prominence=prominence)
    return int(len(peaks))


def calculate_straightness(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
) -> float:
    """Path straightness: straight-line displacement / actual path length."""
    if start_idx is None:
        start_idx = 0
    if end_idx is None:
        end_idx = len(palm_x) - 1
    if end_idx <= start_idx:
        return float("nan")
    x = palm_x[start_idx : end_idx + 1]
    y = palm_y[start_idx : end_idx + 1]
    straight = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    path = float(np.nansum(np.hypot(np.gradient(x), np.gradient(y))))
    if path <= 0 or not np.isfinite(path):
        return float("nan")
    return straight / path


def calculate_pause_time_and_stops(
    speed: np.ndarray,
    fs: float = 60.0,
    pause_threshold_frac: float = 0.05,
    min_pause_frames: int = 6,
) -> Tuple[float, int]:
    """
    Total pause time and number of stops during a reach.
    A stop is a contiguous run below a speed threshold for at least
    min_pause_frames (~100 ms at 60 Hz).
    """
    if len(speed) == 0:
        return 0.0, 0
    peak = float(np.nanmax(speed)) if np.nanmax(speed) > 0 else 1.0
    threshold = pause_threshold_frac * peak
    below = speed < threshold

    pause_time = 0.0
    n_stops = 0
    i = 0
    while i < len(below):
        if below[i]:
            j = i
            while j < len(below) and below[j]:
                j += 1
            run = j - i
            if run >= min_pause_frames:
                pause_time += run / fs
                n_stops += 1
            i = j
        else:
            i += 1
    return pause_time, n_stops


# ============================================================
# 7. CSV adapters
# ============================================================

def _infer_fs(df: pd.DataFrame, default: float = DEFAULT_FS) -> float:
    if "fps" in df.columns:
        try:
            fps = float(df["fps"].iloc[0])
            if fps > 0:
                return fps
        except (TypeError, ValueError):
            pass
    if "time" in df.columns and len(df) > 2:
        dt = float(np.median(np.diff(df["time"].astype(float).values)))
        if dt > 0:
            return 1.0 / dt
    return default


def _upsample_array(y: np.ndarray, native_fs: float, target_fs: float) -> np.ndarray:
    """Cubic-spline upsample a 1D kinematic series to target_fs (same movement duration)."""
    arr = np.asarray(y, dtype=float)
    n = len(arr)
    if n < 4 or abs(native_fs - target_fs) < 0.5:
        return arr
    t_src = np.arange(n, dtype=float) / native_fs
    duration = t_src[-1]
    n_new = max(int(round(duration * target_fs)) + 1, n)
    t_new = np.arange(n_new, dtype=float) / target_fs
    return CubicSpline(t_src, arr)(t_new)


def upsample_trial_dataframe(
    df: pd.DataFrame,
    target_fs: float = ANALYSIS_TARGET_FS,
) -> pd.DataFrame:
    """Upsample mediapipe_csv_extractor trial CSV from native (~30) fps to target_fs."""
    src_fs = float(_infer_fs(df))
    n = len(df)
    if n < 4 or abs(src_fs - target_fs) < 0.5:
        out = df.copy()
        out["fps"] = target_fs
        return out

    t_src = np.arange(n, dtype=float) / src_fs
    duration = t_src[-1]
    n_new = max(int(round(duration * target_fs)) + 1, n)
    t_new = np.arange(n_new, dtype=float) / target_fs

    out: Dict[str, Any] = {}
    for col in _UPSAMPLE_COORD_COLS:
        if col in df.columns:
            out[col] = CubicSpline(t_src, df[col].astype(float).values)(t_new)

    if "shoulder_width" in df.columns:
        sw = float(np.nanmedian(df["shoulder_width"].values))
        out["shoulder_width"] = np.full(n_new, sw)

    for col in _UPSAMPLE_VIS_COLS:
        if col in df.columns:
            y = df[col].astype(float).values
            out[col] = np.clip(CubicSpline(t_src, y)(t_new), 0.0, 1.0)

    for col in ("frame_width_px", "frame_height_px", "camera_view", "affected_side"):
        if col in df.columns:
            out[col] = df[col].iloc[0]

    out["frame"] = np.arange(n_new, dtype=int)
    out["time"] = t_new
    out["fps"] = np.full(n_new, target_fs)
    if "frame_quality_ok" in df.columns:
        fq = df["frame_quality_ok"].astype(float).values
        out["frame_quality_ok"] = (CubicSpline(t_src, fq)(t_new) >= 0.5).astype(int)

    return pd.DataFrame(out)


def prepare_trial_timeseries(
    df: pd.DataFrame,
    target_fs: float = ANALYSIS_TARGET_FS,
) -> Tuple[pd.DataFrame, float, float, bool]:
    """
    When native video fps is below ~55 Hz, upsample pose trajectories to 60 Hz for SPARC.
    Returns (working_df, native_fs, analysis_fs, did_upsample).
    """
    native_fs = float(_infer_fs(df))
    if (
        native_fs >= NATIVE_FS_UPSAMPLE_BELOW
        or len(df) < 4
        or "palm_x" not in df.columns
    ):
        return df, native_fs, native_fs, False
    return upsample_trial_dataframe(df, target_fs), native_fs, target_fs, True


def _upsample_coord_dict(
    coords: Dict[str, np.ndarray],
    native_fs: float,
    target_fs: float,
) -> Dict[str, np.ndarray]:
    out = dict(coords)
    for key in _UPSAMPLE_COORD_COLS:
        if key in out:
            out[key] = _upsample_array(out[key], native_fs, target_fs)
    return out


def _map_frames_to_native_fs(
    start: int,
    end: int,
    analysis_fs: float,
    native_fs: float,
    n_native: int,
) -> Tuple[int, int]:
    """Map analysis-frame indices back to native pose CSV indices (same time in seconds)."""
    if n_native <= 0:
        return 0, 0
    t0 = start / max(analysis_fs, 1e-6)
    t1 = end / max(analysis_fs, 1e-6)
    s = int(round(t0 * native_fs))
    e = int(round(t1 * native_fs))
    s = max(0, min(s, n_native - 1))
    e = max(s, min(e, n_native - 1))
    return s, e


def _col(df: pd.DataFrame, name: str, axis: str) -> np.ndarray:
    key = f"{name}_{axis}"
    if key not in df.columns:
        raise KeyError(key)
    return df[key].astype(float).values


def _pick_side(
    df: pd.DataFrame,
    affected_side: str,
    frame_width: int = DEFAULT_FRAME_WIDTH,
    frame_height: int = DEFAULT_FRAME_HEIGHT,
) -> str:
    side = (affected_side or "auto").lower()
    if side in ("left", "right"):
        return side
    try:
        from mediapipe_csv_extractor import detect_active_arm

        fs = _infer_fs(df)
        return detect_active_arm(df, frame_width, frame_height, fs=fs)
    except KeyError:
        return "left"


def _landmarks_from_mediapipe_csv(
    df: pd.DataFrame,
    affected_side: str = "auto",
    frame_width: int = DEFAULT_FRAME_WIDTH,
    frame_height: int = DEFAULT_FRAME_HEIGHT,
    *,
    refine_landmarks: bool = True,
) -> Tuple[Dict[str, np.ndarray], str, float]:
    """Build palm_x, trunk_x, … pixel arrays from NeuroLab / MediaPipe landmark CSV."""
    from landmark_tracker_enhance import compute_trunk_coords, infer_fps_from_df, refine_pose_landmarks_df

    work = df
    if refine_landmarks and "LEFT_SHOULDER_X" in df.columns:
        work = refine_pose_landmarks_df(df, fps=infer_fps_from_df(df))

    side = _pick_side(work, affected_side, frame_width=frame_width, frame_height=frame_height)
    p = side.upper()

    wrist_x = _col(work, f"{p}_WRIST", "X") * frame_width
    wrist_y = _col(work, f"{p}_WRIST", "Y") * frame_height
    index_x = _col(work, f"{p}_INDEX", "X") * frame_width
    index_y = _col(work, f"{p}_INDEX", "Y") * frame_height
    palm_x = (wrist_x + index_x) / 2.0
    palm_y = (wrist_y + index_y) / 2.0

    shoulder_x = _col(work, f"{p}_SHOULDER", "X") * frame_width
    shoulder_y = _col(work, f"{p}_SHOULDER", "Y") * frame_height
    elbow_x = _col(work, f"{p}_ELBOW", "X") * frame_width
    elbow_y = _col(work, f"{p}_ELBOW", "Y") * frame_height

    ls_x = _col(work, "LEFT_SHOULDER", "X") * frame_width
    ls_y = _col(work, "LEFT_SHOULDER", "Y") * frame_height
    rs_x = _col(work, "RIGHT_SHOULDER", "X") * frame_width
    rs_y = _col(work, "RIGHT_SHOULDER", "Y") * frame_height
    lh_x = _col(work, "LEFT_HIP", "X") * frame_width
    lh_y = _col(work, "LEFT_HIP", "Y") * frame_height
    rh_x = _col(work, "RIGHT_HIP", "X") * frame_width
    rh_y = _col(work, "RIGHT_HIP", "Y") * frame_height
    trunk_x, trunk_y = compute_trunk_coords(ls_x, ls_y, rs_x, rs_y, lh_x, lh_y, rh_x, rh_y)

    shoulder_width = float(np.median(np.hypot(rs_x - ls_x, rs_y - ls_y)))
    if shoulder_width <= 0:
        shoulder_width = float("nan")

    coords = {
        "palm_x": palm_x,
        "palm_y": palm_y,
        "wrist_x": wrist_x,
        "wrist_y": wrist_y,
        "trunk_x": trunk_x,
        "trunk_y": trunk_y,
        "shoulder_x": shoulder_x,
        "shoulder_y": shoulder_y,
        "elbow_x": elbow_x,
        "elbow_y": elbow_y,
        "shoulder_width": shoulder_width,
    }
    return coords, side, shoulder_width


def _load_trial_coords(df: pd.DataFrame) -> Tuple[Dict[str, np.ndarray], Optional[float]]:
    """Load precomputed columns from mediapipe_csv_extractor.py output."""
    required = ["palm_x", "palm_y", "wrist_x", "wrist_y", "trunk_x", "trunk_y",
                "shoulder_x", "shoulder_y", "elbow_x", "elbow_y"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns for analyze_trial: {missing}")

    shoulder_width = None
    if "shoulder_width" in df.columns:
        sw = df["shoulder_width"].iloc[0]
        if pd.notna(sw) and float(sw) > 0:
            shoulder_width = float(sw)

    coords = {k: df[k].astype(float).values for k in required}
    coords["shoulder_width"] = shoulder_width if shoulder_width else float("nan")
    return coords, shoulder_width


def _normalize_landmark_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map legacy lowercase _x/_y landmark columns to pipeline _X/_Y names."""
    rename = {}
    for c in df.columns:
        if c.endswith("_x"):
            rename[c] = c[:-2] + "_X"
        elif c.endswith("_y"):
            rename[c] = c[:-2] + "_Y"
        elif c.endswith("_z"):
            rename[c] = c[:-2] + "_Z"
        elif c.endswith("_v") and "_VISIBILITY" not in c.upper():
            rename[c] = c[:-2] + "_VISIBILITY"
    return df.rename(columns=rename) if rename else df


def _try_load_raw_pose_csv(csv_path: str) -> Optional[pd.DataFrame]:
    if not csv_path:
        return None
    p = Path(csv_path)
    if p.stem.endswith("_raw_pose") and p.exists():
        return _normalize_landmark_columns(pd.read_csv(p))
    candidate = p.with_name(p.stem + "_raw_pose.csv")
    if candidate.exists():
        return _normalize_landmark_columns(pd.read_csv(candidate))
    return None


def _pose_landmark_df(df: pd.DataFrame, csv_path: str) -> Optional[pd.DataFrame]:
    """Normalized MediaPipe landmark table (raw_pose sibling or inline X/Y/Z columns)."""
    raw = _try_load_raw_pose_csv(csv_path)
    if raw is not None:
        return raw
    norm = _normalize_landmark_columns(df)
    if "LEFT_SHOULDER_X" in norm.columns:
        return norm
    return None


def _coords_for_trial(
    df: pd.DataFrame,
    csv_path: str,
    resolved_side: str,
    frame_width: int,
    frame_height: int,
) -> Tuple[Dict[str, np.ndarray], Optional[float], str]:
    """Load palm/elbow coords; auto mode re-detects active arm from raw landmarks when possible."""
    from mediapipe_csv_extractor import _build_coords_from_raw

    side_auto = (resolved_side or "auto").lower() not in ("left", "right")
    baked_side = None
    if "affected_side" in df.columns:
        val = df["affected_side"].iloc[0]
        if pd.notna(val):
            baked_side = str(val).lower()

    side_mismatch = (
        not side_auto
        and resolved_side in ("left", "right")
        and baked_side in ("left", "right")
        and resolved_side != baked_side
    )

    if "palm_x" in df.columns and not side_mismatch:
        coords, shoulder_width = _load_trial_coords(df)
        side = baked_side if baked_side in ("left", "right") else (
            resolved_side if resolved_side in ("left", "right") else "auto"
        )
        return coords, shoulder_width, side

    raw_df = _try_load_raw_pose_csv(csv_path)
    source = raw_df if raw_df is not None else _normalize_landmark_columns(df)
    has_landmarks = "LEFT_WRIST_X" in source.columns

    if side_mismatch and (raw_df is not None or has_landmarks):
        side = resolved_side if resolved_side in ("left", "right") else "auto"
        built = _build_coords_from_raw(source, side, frame_width, frame_height)
        side_used = str(built.pop("affected_side", side))
        shoulder_width = built.pop("shoulder_width", float("nan"))
        coord_keys = [
            "palm_x", "palm_y", "wrist_x", "wrist_y", "trunk_x", "trunk_y",
            "shoulder_x", "shoulder_y", "elbow_x", "elbow_y",
        ]
        coords = {k: built[k] for k in coord_keys}
        sw = float(shoulder_width) if shoulder_width and np.isfinite(shoulder_width) else None
        return coords, sw, side_used

    if has_landmarks:
        coords, side, shoulder_width = _landmarks_from_mediapipe_csv(
            source, affected_side=resolved_side, frame_width=frame_width, frame_height=frame_height
        )
        sw = shoulder_width if shoulder_width and np.isfinite(shoulder_width) else None
        return coords, sw, side

    if "palm_x" in df.columns:
        coords, shoulder_width = _load_trial_coords(df)
        return coords, shoulder_width, baked_side or resolved_side or "left"

    coords, side, shoulder_width = _landmarks_from_mediapipe_csv(
        source, affected_side=resolved_side, frame_width=frame_width, frame_height=frame_height
    )
    sw = shoulder_width if shoulder_width and np.isfinite(shoulder_width) else None
    return coords, sw, side


# ============================================================
# MAIN PIPELINE
# ============================================================

def analyze_trial(
    csv_path: str,
    fs: Optional[float] = None,
    velocity_threshold: float = DEFAULT_VELOCITY_THRESHOLD_PX_S,
    camera_view: str = "auto",
    affected_side: str = "auto",
    frame_width: int = DEFAULT_FRAME_WIDTH,
    frame_height: int = DEFAULT_FRAME_HEIGHT,
    trial_df: Optional[pd.DataFrame] = None,
    native_fs: Optional[float] = None,
    upsampled: bool = False,
    reference_amplitude_sw: Optional[float] = None,
    target_amplitude_sw: Optional[float] = None,
    trial_role: Optional[str] = None,
    video_path: Optional[str] = None,
    task_mode: str = "reach_only",
) -> Dict[str, Any]:
    """
    Complete analysis for one trial CSV or video.
    Accepts mediapipe_csv_extractor output, raw MediaPipe landmark CSV, or a
    video path (in which case pose extraction is performed first).
    """
    import mimetypes

    p = Path(csv_path)
    mime, _ = mimetypes.guess_type(str(p))
    is_video = mime and mime.startswith("video/")
    if trial_df is None and is_video:
        from mediapipe_csv_extractor import extract_from_video

        out_dir = p.parent / "extracted"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_csv = out_dir / (p.stem + "_landmarks.csv")
        video_path = str(p)
        extract_from_video(
            video_path=str(p),
            output_csv=str(output_csv),
            affected_side=affected_side,
            camera_view=camera_view,
            save_raw_pose=True,
            legacy_format=True,
        )
        csv_path = str(output_csv)
        p = Path(csv_path)

    native_df = trial_df if trial_df is not None else pd.read_csv(csv_path)
    native_fs = float(_infer_fs(native_df)) if native_fs is None else float(native_fs)

    if "frame_width_px" in native_df.columns:
        frame_width = int(native_df["frame_width_px"].iloc[0])
    if "frame_height_px" in native_df.columns:
        frame_height = int(native_df["frame_height_px"].iloc[0])

    resolved_view = _resolve_camera_view(native_df, camera_view)
    resolved_side = _resolve_affected_side(native_df, affected_side)

    native_coords, shoulder_width, side = _coords_for_trial(
        native_df, csv_path, resolved_side, frame_width, frame_height
    )

    from motion_invariants import (
        amplitude_matched_reach_window,
        body_frame_palm,
        forward_reach_window,
        infer_trial_role,
        kinematic_reach_window,
        reach_amplitude_sw,
        reach_only_window,
        select_literature_matched_window,
        select_reach_window,
        table_reach_window,
    )

    sw_native = shoulder_width if shoulder_width and shoulder_width > 0 else None

    role = (trial_role or infer_trial_role(csv_path, affected_side=resolved_side)).lower()
    analysis_profile = "reference" if role == "healthy" else "affected"
    sparc_profile = "uniform"
    mode = (task_mode or "reach_only").lower()

    # Reach window always on native timeline (literature: segment before upsample).
    # Use the same literature-backed algorithm for all conditions so differences
    # in SPARC reflect neuromotor control, not window-selection bias.
    move_start_native, move_end_native = select_literature_matched_window(
        native_coords["palm_x"],
        native_coords["palm_y"],
        native_fs,
        shoulder_width=sw_native,
        reference_amplitude_sw=reference_amplitude_sw,
        velocity_threshold_frac=0.05,
        min_duration_s=0.50,
        min_amplitude_sw=0.12,
        amplitude_tolerance=0.20,
    )

    # Literature amplitude matching: cap all conditions at the same body-frame
    # displacement BEFORE upsampling. Upsampling artifacts (cubic-spline overshoot)
    # can inflate amplitude, so matching must be done on native coordinates.
    sw = sw_native if sw_native and sw_native > 0 else 1.0
    bx_native, by_native, bz_native, _ = body_frame_palm(
        native_coords["palm_x"], native_coords["palm_y"],
        native_coords.get("shoulder_x", np.full_like(native_coords["palm_x"], native_coords["palm_x"][0])),
        native_coords.get("shoulder_y", np.full_like(native_coords["palm_y"], native_coords["palm_y"][0])),
        sw,
    )
    native_amp_sw = reach_amplitude_sw(bx_native, by_native, bz_native, move_start_native, move_end_native)

    if target_amplitude_sw is not None and np.isfinite(target_amplitude_sw) and target_amplitude_sw > 0:
        move_start_native, move_end_native = amplitude_matched_reach_window(
            native_coords["palm_x"],
            native_coords["palm_y"],
            move_start_native,
            move_end_native,
            float(target_amplitude_sw),
            sw,
            shoulder_x=native_coords.get("shoulder_x"),
            shoulder_y=native_coords.get("shoulder_y"),
            min_segment_frames=10,
        )

    _full_on, _full_off = table_reach_window(
        native_coords["palm_x"],
        native_coords["palm_y"],
        native_fs,
        shoulder_width=sw_native,
    )
    ro_on_native, ro_off_native, _disp_peak = reach_only_window(
        native_coords["palm_x"],
        native_coords["palm_y"],
        native_fs,
        shoulder_width=sw_native,
    )
    fwd_on_native, fwd_off_native = ro_on_native, ro_off_native
    kin_start_native, kin_end_native = kinematic_reach_window(
        native_coords["palm_x"],
        native_coords["palm_y"],
        native_fs,
        shoulder_width=sw_native,
        analysis_profile=analysis_profile,
    )

    df, _, analysis_fs, prepared_up = prepare_trial_timeseries(native_df)
    need_up = prepared_up or native_fs < NATIVE_FS_UPSAMPLE_BELOW
    if need_up:
        coords = _upsample_coord_dict(native_coords, native_fs, ANALYSIS_TARGET_FS)
        fs = ANALYSIS_TARGET_FS
        upsampled = True
        n_analysis = len(coords["palm_x"])
        move_start = int(round(move_start_native / native_fs * fs))
        move_end = int(round(move_end_native / native_fs * fs))
        move_start = max(0, min(move_start, n_analysis - 1))
        move_end = max(move_start, min(move_end, n_analysis - 1))
        kin_start = int(round(kin_start_native / native_fs * fs))
        kin_end = int(round(kin_end_native / native_fs * fs))
        kin_start = max(0, min(kin_start, n_analysis - 1))
        kin_end = max(kin_start, min(kin_end, n_analysis - 1))
        hand_reach_start = int(round(ro_on_native / native_fs * fs))
        hand_reach_end = int(round(ro_off_native / native_fs * fs))
        hand_reach_start = max(0, min(hand_reach_start, n_analysis - 1))
        hand_reach_end = max(hand_reach_start, min(hand_reach_end, n_analysis - 1))
    else:
        df = native_df
        coords = native_coords
        fs = native_fs
        upsampled = False
        move_start, move_end = int(move_start_native), int(move_end_native)
        kin_start, kin_end = int(kin_start_native), int(kin_end_native)
        hand_reach_start, hand_reach_end = int(ro_on_native), int(ro_off_native)

    n_frames = len(coords["palm_x"])
    move_start = max(0, min(move_start, n_frames - 1))
    move_end = max(move_start, min(move_end, n_frames - 1))
    kin_start = max(0, min(kin_start, n_frames - 1))
    kin_end = max(kin_start, min(kin_end, n_frames - 1))
    hand_reach_start = max(0, min(hand_reach_start, n_frames - 1))
    hand_reach_end = max(hand_reach_start, min(hand_reach_end, n_frames - 1))

    palm_x = coords["palm_x"]
    palm_y = coords["palm_y"]
    wrist_x = coords["wrist_x"]
    wrist_y = coords["wrist_y"]
    trunk_x = coords["trunk_x"]
    trunk_y = coords["trunk_y"]
    shoulder_x = coords["shoulder_x"]
    shoulder_y = coords["shoulder_y"]
    elbow_x = coords["elbow_x"]
    elbow_y = coords["elbow_y"]

    palm_vx = np.gradient(palm_x) * fs
    palm_vy = np.gradient(palm_y) * fs
    palm_speed = np.sqrt(palm_vx**2 + palm_vy**2)

    sw = shoulder_width if shoulder_width and shoulder_width > 0 else None

    raw_df = _try_load_raw_pose_csv(csv_path)
    arm3d = None
    body_orient: Dict[str, Any] = {"label": resolved_view, "ratio": None, "confidence": 0.0}
    if raw_df is not None:
        from motion_invariants import detect_body_orientation, load_arm_3d

        body_orient = detect_body_orientation(raw_df, frame_width, frame_height)
        resolved_view = str(body_orient.get("label") or resolved_view)
        arm3d = load_arm_3d(raw_df, side, frame_width, frame_height)
        if arm3d and upsampled:
            arm3d = {
                k: _upsample_array(v, native_fs, fs) if isinstance(v, np.ndarray) else v
                for k, v in arm3d.items()
            }

    results: Dict[str, Any] = {
        "camera_view": resolved_view,
        "body_orientation_ratio": body_orient.get("ratio"),
        "body_orientation_confidence": body_orient.get("confidence"),
        "fs_hz": round(fs, 2),
        "native_fs_hz": round(native_fs, 2),
        "analysis_fs_hz": round(fs, 2),
        "upsampled_to_60hz": upsampled,
        "velocity_threshold_px_s": velocity_threshold,
        "side_analyzed": side,
        "analysis_frame": "body_normalized_3d" if arm3d else "body_normalized_2d",
        "landmark_tracking_enhanced": True,
        "trunk_proxy": "shoulder_girdle_midpoint",
        "task_mode": (task_mode or "reach_only").lower(),
    }

    palm_z = arm3d["palm_z"] if arm3d else None
    shoulder_z = arm3d["shoulder_z"] if arm3d else None

    sparc_val, sparc_frames, move_start, move_end, amp_sw, sparc_comparable, sparc_ws, sparc_we, speed_space = (
        calculate_sparc_movement_window(
            palm_x, palm_y, fs=fs, velocity_threshold=velocity_threshold,
            shoulder_x=shoulder_x, shoulder_y=shoulder_y, shoulder_width=sw,
            palm_z=palm_z, shoulder_z=shoulder_z,
            move_start=move_start, move_end=move_end,
            analysis_profile=sparc_profile,
            sparc_window_method="literature_5pct",
        )
    )
    results["sparc"] = sparc_val
    results["sparc_active_frames"] = sparc_frames
    results["sparc_comparable"] = sparc_comparable
    results["sparc_window_onset_frame"] = sparc_ws
    results["sparc_window_offset_frame"] = sparc_we
    results["sparc_method"] = "literature_5pct"
    results["sparc_speed_space"] = speed_space
    results["analysis_profile"] = analysis_profile
    results["reach_amplitude_sw"] = amp_sw
    results["native_reach_amplitude_sw"] = round(float(native_amp_sw), 4) if np.isfinite(native_amp_sw) else None
    results["sparc_reach_onset_frame"] = move_start
    results["sparc_reach_offset_frame"] = move_end
    results["reach_window_onset_frame"] = move_start
    results["reach_window_offset_frame"] = move_end
    results["reach_window_onset_s"] = round(move_start / fs, 3)
    results["reach_window_offset_s"] = round(move_end / fs, 3)
    results["reach_window_duration_s"] = round((move_end - move_start + 1) / fs, 3)

    results["hand_reach_window_onset_frame"] = hand_reach_start
    results["hand_reach_window_offset_frame"] = hand_reach_end
    results["hand_reach_window_onset_s"] = round(hand_reach_start / fs, 3)
    results["hand_reach_window_offset_s"] = round(hand_reach_end / fs, 3)
    results["hand_reach_window_duration_s"] = round((hand_reach_end - hand_reach_start + 1) / fs, 3)
    results["kinematic_window_onset_frame"] = kin_start
    results["kinematic_window_offset_frame"] = kin_end
    results["movement_onset_frame"] = kin_start
    results["movement_offset_frame"] = kin_end

    from motion_invariants import amplitude_matched

    results["comparison_role"] = role
    results["arm_role"] = "reference_unaffected" if role == "healthy" else "affected"
    results["sparc_primary_comparison"] = role in ("pre", "post", "paretic")
    ref_amp = reference_amplitude_sw
    if ref_amp is not None and np.isfinite(ref_amp):
        results["amplitude_matched"] = bool(amplitude_matched(amp_sw, float(ref_amp)))
        results["reference_amplitude_sw"] = float(ref_amp)
    else:
        results["amplitude_matched"] = None
        results["reference_amplitude_sw"] = None

    trunk_disp_ratio, trunk_disp, palm_disp, trunk_path_ratio = calculate_trunk_ratio(
        trunk_x, trunk_y, palm_x, palm_y, fs=fs, velocity_threshold=velocity_threshold,
        shoulder_width=sw, start_idx=kin_start, end_idx=kin_end,
    )
    # Path ratio (trunk path / hand path) is stable for reach-wipe when net endpoint
    # displacement spans wipe/return (Zeinab post); disp ratio kept as trunk_disp_ratio.
    results["trunk_ratio"] = trunk_path_ratio
    results["trunk_path_ratio"] = trunk_path_ratio
    results["trunk_disp_ratio"] = trunk_disp_ratio
    results["trunk_displacement_px"] = trunk_disp
    results["palm_displacement_px"] = palm_disp

    hand_disp_norm, hand_disp_px, palm_raw_px, trunk_cheat_ratio = (
        calculate_hand_displacement_trunk_relative(
            trunk_x, trunk_y, palm_x, palm_y,
            shoulder_width=sw,
            start_idx=kin_start,
            end_idx=kin_end,
        )
    )

    from motion_invariants import compute_forward_reach_cm, compute_hand_reach_displacement
    from table_calibrator import TABLE_WIDTH_CM, calibrate_table_scale, px_to_cm

    scale_info = calibrate_table_scale(
        csv_path, palm_x, palm_y, shoulder_width_px=sw, video_path=video_path,
        reach_only=(mode == "reach_only"),
    )
    cm_per_px = scale_info.get("cm_per_px")
    results["table_width_cm"] = TABLE_WIDTH_CM
    results["table_width_px"] = scale_info.get("table_width_px")
    results["cm_per_px"] = cm_per_px
    results["table_scale_method"] = scale_info.get("scale_method")
    results["calibration_video"] = scale_info.get("video_path")

    palm_z = arm3d["palm_z"] if arm3d else None
    shoulder_z = arm3d["shoulder_z"] if arm3d else None
    # Use the longer literature-matched reach window for hand displacement so it
    # reflects the actual distance covered during the primary reach, not the short
    # reach-only cut that can be near zero when the hand is already near the target.
    displacement_start = move_start
    displacement_end = move_end
    if hand_reach_end > hand_reach_start and (hand_reach_end - hand_reach_start) >= (displacement_end - displacement_start):
        displacement_start = hand_reach_start
        displacement_end = hand_reach_end

    reach_fwd = compute_forward_reach_cm(
        trunk_x, trunk_y, palm_x, palm_y, displacement_start, displacement_end, cm_per_px,
    )
    reach_lit = compute_hand_reach_displacement(
        palm_x, palm_y, shoulder_x, shoulder_y,
        elbow_x, elbow_y, wrist_x, wrist_y,
        trunk_x, trunk_y, sw, displacement_start, displacement_end,
        palm_z=palm_z, shoulder_z=shoulder_z,
    )

    # Physical displacement fallback: net palm displacement along the forward-reach axis,
    # calibrated from table width when available, otherwise shoulder-width fallback.
    physical_cm = _forward_displacement_cm_along_axis(
        palm_x, palm_y, trunk_x, trunk_y, displacement_start, displacement_end, cm_per_px
    )
    net_palm_cm = _net_palm_displacement_cm(
        palm_x, palm_y, displacement_start, displacement_end, cm_per_px
    )

    if reach_fwd and np.isfinite(reach_fwd.get("peak_cm", float("nan"))) and reach_fwd["peak_cm"] > 0:
        hand_cm = reach_fwd["peak_cm"]
        results["hand_displacement_cm"] = hand_cm
        results["hand_displacement_norm"] = hand_cm
        results["hand_displacement_table_frac"] = (
            hand_cm / TABLE_WIDTH_CM if np.isfinite(hand_cm) else float("nan")
        )
        results["hand_displacement_endpoint_cm"] = reach_fwd["endpoint_cm"]
        results["hand_displacement_px"] = reach_fwd["peak_fwd_px"]
        results["hand_displacement_method"] = "table_60cm_forward_outbound"
    elif physical_cm is not None and np.isfinite(physical_cm) and physical_cm > 0:
        results["hand_displacement_cm"] = physical_cm
        results["hand_displacement_norm"] = physical_cm
        results["hand_displacement_table_frac"] = (
            physical_cm / TABLE_WIDTH_CM if np.isfinite(physical_cm) else float("nan")
        )
        results["hand_displacement_px"] = float(np.hypot(
            palm_x[hand_reach_end] - palm_x[hand_reach_start],
            palm_y[hand_reach_end] - palm_y[hand_reach_start],
        ))
        results["hand_displacement_method"] = "forward_axis_table_calibrated"
    elif net_palm_cm is not None and np.isfinite(net_palm_cm) and net_palm_cm > 0:
        results["hand_displacement_cm"] = net_palm_cm
        results["hand_displacement_norm"] = net_palm_cm
        results["hand_displacement_table_frac"] = (
            net_palm_cm / TABLE_WIDTH_CM if np.isfinite(net_palm_cm) else float("nan")
        )
        results["hand_displacement_px"] = float(np.hypot(
            palm_x[hand_reach_end] - palm_x[hand_reach_start],
            palm_y[hand_reach_end] - palm_y[hand_reach_start],
        ))
        results["hand_displacement_method"] = "net_palm_table_calibrated"
    elif reach_lit:
        trunk_peak_px = reach_lit.get("trunk_peak_px", float("nan"))
        hand_cm = px_to_cm(trunk_peak_px, cm_per_px)
        results["hand_displacement_cm"] = hand_cm
        results["hand_displacement_norm"] = hand_cm
        results["hand_displacement_table_frac"] = (
            hand_cm / TABLE_WIDTH_CM if np.isfinite(hand_cm) else float("nan")
        )
        results["hand_displacement_px"] = trunk_peak_px
        results["hand_displacement_method"] = "table_60cm_trunk_peak_fallback"
    else:
        hand_cm = px_to_cm(hand_disp_px, cm_per_px)
        results["hand_displacement_cm"] = hand_cm
        results["hand_displacement_norm"] = hand_cm
        results["hand_displacement_table_frac"] = (
            hand_cm / TABLE_WIDTH_CM if np.isfinite(hand_cm) else float("nan")
        )
        results["hand_displacement_px"] = hand_disp_px
        results["hand_displacement_method"] = "table_60cm_trunk_peak_fallback"
    if reach_lit:
        results["hand_displacement_endpoint_sw"] = reach_lit["endpoint_sw"]
        results["hand_displacement_limb_norm"] = reach_lit["limb_norm"]
        results["hand_displacement_trunk_norm"] = reach_lit["trunk_peak_sw"]
        results["hand_disp_sw"] = reach_lit["peak_sw"]
        results["palm_displacement_raw_px"] = reach_lit["palm_raw_px"]
        results["trunk_cheat_ratio"] = reach_lit["trunk_cheat_ratio"]
    else:
        results["hand_displacement_trunk_norm"] = hand_disp_norm
        results["hand_disp_sw"] = hand_disp_norm
        results["palm_displacement_raw_px"] = palm_raw_px
        results["trunk_cheat_ratio"] = trunk_cheat_ratio

    shoulder_elev_norm, shoulder_elev_abs = calculate_shoulder_elevation(
        shoulder_x, shoulder_y,
        shoulder_width=sw,
        fs=fs,
        velocity_threshold=velocity_threshold,
        palm_speed=palm_speed,
        palm_x=palm_x,
        palm_y=palm_y,
        start_idx=kin_start,
        end_idx=kin_end,
    )
    results["shoulder_elevation_norm"] = shoulder_elev_norm
    results["shoulder_elevation_abs_px"] = shoulder_elev_abs
    results["shoulder_elevation_method"] = "rest_to_peak_y_reach_window"

    # Movement time / peak velocity: use the same literature-backed reach window
    # as SPARC and trunk metrics (Balasubramanian 5% peak-velocity window).
    mt_start, mt_end = move_start, move_end
    n_analysis = len(palm_x)
    mt_start = max(0, min(mt_start, n_analysis - 1))
    mt_end = max(mt_start, min(mt_end, n_analysis - 1))
    mt_window = "literature_5pct"
    results["reach_only_onset_frame_native"] = int(ro_on_native)
    results["reach_only_offset_frame_native"] = int(ro_off_native)
    results["reach_only_duration_s"] = round((ro_off_native - ro_on_native + 1) / native_fs, 3)

    results["movement_metrics_onset_frame"] = mt_start
    results["movement_metrics_offset_frame"] = mt_end
    results["movement_metrics_duration_s"] = round((mt_end - mt_start + 1) / fs, 3)

    # Compute palm speed profile once for reach-to-grasp primary metrics.
    from motion_invariants import smooth_series
    px_s = smooth_series(np.asarray(palm_x, dtype=float), fs, window_s=0.12)
    py_s = smooth_series(np.asarray(palm_y, dtype=float), fs, window_s=0.12)
    palm_speed_profile = np.sqrt(np.gradient(px_s) ** 2 + np.gradient(py_s) ** 2) * fs

    results["movement_time_sec"] = calculate_movement_time(
        palm_x, palm_y, fs=fs, velocity_threshold=velocity_threshold,
        shoulder_width=sw, start_idx=mt_start, end_idx=mt_end,
    )
    results["movement_time_window"] = mt_window

    peak_vel, ttpv, rel_ttpv = calculate_peak_velocity(
        palm_x, palm_y, fs=fs, velocity_threshold=velocity_threshold,
        shoulder_width=sw, shoulder_x=shoulder_x, shoulder_y=shoulder_y,
        start_idx=mt_start, end_idx=mt_end,
    )
    results["peak_velocity_px_s"] = peak_vel
    if cm_per_px and cm_per_px > 0 and np.isfinite(peak_vel):
        results["peak_velocity_cm_s"] = float(peak_vel * cm_per_px)
    else:
        results["peak_velocity_cm_s"] = float("nan")
    results["time_to_peak_velocity_sec"] = ttpv
    results["relative_time_to_peak_pct"] = rel_ttpv

    # Reach-to-grasp primary outcomes (protocol-aligned)
    nvp = calculate_nvp(palm_speed_profile, prominence_frac=0.30)
    straightness = calculate_straightness(palm_x, palm_y, start_idx=mt_start, end_idx=mt_end)
    pause_time, number_of_stops = calculate_pause_time_and_stops(
        palm_speed_profile, fs=fs, pause_threshold_frac=0.05, min_pause_frames=6
    )
    results["nvp"] = int(nvp)
    results["straightness"] = float(straightness) if np.isfinite(straightness) else float("nan")
    results["pause_time_sec"] = float(pause_time)
    results["number_of_stops"] = int(number_of_stops)

    # Elbow angle secondary outcome
    elbow_angle_mean, elbow_angle_min, elbow_angle_max = calculate_elbow_angle(
        shoulder_x, shoulder_y, elbow_x, elbow_y, wrist_x, wrist_y,
        fs=fs, velocity_threshold=velocity_threshold,
        palm_speed=palm_speed_profile, palm_x=palm_x, palm_y=palm_y,
        shoulder_width=sw, start_idx=mt_start, end_idx=mt_end,
    )
    results["elbow_angle_mean_deg"] = elbow_angle_mean
    results["elbow_angle_min_deg"] = elbow_angle_min
    results["elbow_angle_max_deg"] = elbow_angle_max
    results["elbow_angle_range_deg"] = (
        float(elbow_angle_max - elbow_angle_min)
        if np.isfinite(elbow_angle_max) and np.isfinite(elbow_angle_min)
        else float("nan")
    )

    frame_quality_pct = None
    if "frame_quality_ok" in df.columns:
        fq = pd.to_numeric(df["frame_quality_ok"], errors="coerce")
        if fq.notna().any():
            frame_quality_pct = float(fq.mean() * 100.0)

    movement_frames = int(kin_end - kin_start + 1)
    movement_duration_s = float(movement_frames / fs)

    def _scale_native_frame(idx: int) -> int:
        if upsampled and native_fs > 0:
            return int(round(idx / native_fs * fs))
        return int(idx)

    results["reach_phase"] = "forward_only"
    results["forward_onset_frame_native"] = int(fwd_on_native)
    results["forward_offset_frame_native"] = int(fwd_off_native)
    results["displacement_peak_frame_native"] = int(_disp_peak)
    results["full_cycle_onset_frame_native"] = int(_full_on)
    results["full_cycle_offset_frame_native"] = int(_full_off)

    from motion_invariants import assess_trial_quality

    quality = assess_trial_quality(
        amplitude_sw=float(amp_sw),
        movement_frames=movement_frames,
        movement_duration_s=movement_duration_s,
        fs=fs,
        trunk_ratio=float(trunk_path_ratio) if np.isfinite(trunk_path_ratio) else float("nan"),
        trunk_disp_px=float(trunk_disp),
        palm_disp_px=float(palm_disp),
        shoulder_width=sw,
        sparc_comparable=bool(sparc_comparable),
        sparc_value=float(sparc_val) if np.isfinite(sparc_val) else float("nan"),
        forward_reach=True,
        frame_quality_pct=frame_quality_pct,
    )
    results["trial_valid"] = quality["trial_valid"]
    results["metrics_comparable"] = quality["metrics_comparable"]
    results["reach_valid"] = quality["reach_valid"]
    results["trunk_valid"] = quality["trunk_valid"]
    results["sparc_valid"] = quality["sparc_valid"]
    results["quality_flags"] = quality["quality_flags"]
    results["quality_issues"] = quality["quality_issues"]
    if frame_quality_pct is not None:
        results["frame_quality_pct"] = round(frame_quality_pct, 1)

    # SPARC quality advisory: explain why a trial may be borderline.
    results["sparc_quality_advisory"] = _sparc_quality_advisory(
        float(sparc_val) if np.isfinite(sparc_val) else None,
        sparc_comparable,
        int(sparc_frames),
        fs,
        float(amp_sw),
        speed_space,
    )

    # Keep SPARC available for backward compatibility but no longer primary.
    return results


REFERENCE_METRICS: List[Tuple[str, str]] = [
    ("nvp", "lower"),
    ("straightness", "higher"),
    ("pause_time_sec", "lower"),
    ("number_of_stops", "lower"),
    ("trunk_ratio", "lower"),
    ("shoulder_elevation_norm", "lower"),
    ("elbow_angle_mean_deg", "none"),
    ("peak_velocity_px_s", "higher"),
    ("movement_time_sec", "lower"),
]

# Keep legacy SPARC/hand displacement references available for old exports.
_LEGACY_REFERENCE_METRICS: List[Tuple[str, str]] = [
    ("sparc", "higher"),
    ("trunk_ratio", "lower"),
    ("shoulder_elevation_norm", "lower"),
    ("hand_displacement_norm", "higher"),
    ("peak_velocity_px_s", "higher"),
    ("movement_time_sec", "lower"),
]


def _finite(v: Any) -> bool:
    try:
        return v is not None and np.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def gap_from_healthy(value: float, healthy: float, direction: str) -> Optional[float]:
    """
    Signed gap from unaffected-arm reference (descriptive).
    higher-is-better: healthy − value (positive = affected still worse).
    lower-is-better: value − healthy (positive = affected still worse).
    """
    if not (_finite(value) and _finite(healthy)):
        return None
    v, h = float(value), float(healthy)
    if direction == "higher":
        return h - v
    if direction == "lower":
        return v - h
    return None


def recovery_toward_healthy_pct(
    pre: float, post: float, healthy: float, direction: str
) -> Optional[float]:
    """% recovery from Pre toward Healthy reference (100% = reached healthy)."""
    if not all(_finite(x) for x in (pre, post, healthy)):
        return None
    pre_f, post_f, hel_f = float(pre), float(post), float(healthy)
    if direction == "higher":
        denom = hel_f - pre_f
        if abs(denom) < 1e-9:
            return None
        return (post_f - pre_f) / denom * 100.0
    if direction == "lower":
        denom = pre_f - hel_f
        if abs(denom) < 1e-9:
            return None
        return (pre_f - post_f) / denom * 100.0
    return None


def compute_patient_reference_gaps(
    pre: Dict[str, Any],
    post: Dict[str, Any],
    healthy: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Descriptive gaps: how far affected arm (Pre/Post) is from this patient's
    unaffected-arm reference (Healthy). Not a primary inferential test.
    """
    ref: Dict[str, Any] = {
        "healthy_amplitude_sw": healthy.get("reach_amplitude_sw"),
        "healthy_sparc_comparable": healthy.get("sparc_comparable"),
    }
    gaps_pre: Dict[str, Optional[float]] = {}
    gaps_post: Dict[str, Optional[float]] = {}
    recovery: Dict[str, Optional[float]] = {}

    for key, direction in REFERENCE_METRICS:
        h_val = healthy.get(key)
        ref[key] = h_val
        gaps_pre[key] = gap_from_healthy(pre.get(key), h_val, direction) if _finite(h_val) else None
        gaps_post[key] = gap_from_healthy(post.get(key), h_val, direction) if _finite(h_val) else None
        recovery[key] = recovery_toward_healthy_pct(
            pre.get(key), post.get(key), h_val, direction
        ) if _finite(h_val) else None

    return {
        "healthy_reference": ref,
        "gap_pre_vs_healthy": gaps_pre,
        "gap_post_vs_healthy": gaps_post,
        "recovery_toward_healthy_pct": recovery,
        "pre_post_sparc_change": (
            float(post["sparc"]) - float(pre["sparc"])
            if _finite(pre.get("sparc")) and _finite(post.get("sparc"))
            else None
        ),
    }


def interpret_sparc(sparc_value: Optional[float]) -> Dict[str, Any]:
    """
    Clinical interpretation of SPARC (Spectral Arc Length) values.

    SPARC is the negative arc length of the normalized Fourier magnitude spectrum
    of movement speed (Balasubramanian et al., 2012). It is unitless and bounded
    roughly between -6 (very rough/segmented) and 0 (perfectly smooth).

    Interpretation guide (reach-to-grasp after stroke, population-dependent):
      - >= -1.5 : Excellent / healthy ballistic movement
      - -1.5 to -2.5 : Good / mild compensation or fatigue
      - -2.5 to -3.5 : Moderate / some segmentation or trunk compensation
      - -3.5 to -5.0 : Poor / clearly segmented movement
      - < -5.0       : Very poor / severely discontinuous

    The clinically meaningful comparison is WITHIN-PATIENT across conditions
    (healthy reference > post > pre), not absolute cut-offs.
    """
    if sparc_value is None or not np.isfinite(float(sparc_value)):
        return {
            "value": None,
            "rating": "unknown",
            "description": "SPARC could not be computed.",
        }
    v = float(sparc_value)
    if v >= -1.5:
        rating, desc = "excellent", "Very smooth, healthy ballistic profile."
    elif v >= -2.5:
        rating, desc = "good", "Smooth with only mild compensation or fatigue."
    elif v >= -3.5:
        rating, desc = "moderate", "Some segmentation or trunk compensation present."
    elif v >= -5.0:
        rating, desc = "poor", "Clearly segmented movement."
    else:
        rating, desc = "very_poor", "Severely discontinuous movement."
    return {"value": round(v, 4), "rating": rating, "description": desc}


def _extracted_csv_path(video_or_csv_path: str) -> str:
    """If input was a video, return the extracted landmarks CSV path."""
    p = Path(video_or_csv_path)
    mime, _ = __import__("mimetypes").guess_type(str(p))
    if mime and mime.startswith("video/"):
        return str(p.parent / "extracted" / (p.stem + "_landmarks.csv"))
    return video_or_csv_path


def analyze_patient_kinematic_triad(
    pre_csv: str,
    post_csv: str,
    healthy_csv: str,
    pre_side: str = "auto",
    post_side: str = "auto",
    healthy_side: str = "auto",
    pre_video: Optional[str] = None,
    post_video: Optional[str] = None,
    healthy_video: Optional[str] = None,
    **analyze_kw,
) -> Dict[str, Any]:
    """Analyze Pre + Post (affected) + Healthy (reference) for one participant."""

    def _run(csv: str, side: str, role: str, vid: Optional[str], ref_amp: Optional[float]) -> Dict[str, Any]:
        return analyze_trial(
            csv,
            affected_side=side,
            trial_role=role,
            video_path=vid,
            reference_amplitude_sw=ref_amp,
            **analyze_kw,
        )

    # --- Pass 1: standard analysis to obtain reach amplitudes -----------------
    # The first pass uses no external amplitude reference so each trial is
    # analyzed with the same uniform literature window. Passing the healthy
    # amplitude as a reference can bias pre/post toward a late slow segment that
    # matches the healthy reference but is not the patient's primary reach.
    healthy_r = _run(healthy_csv, healthy_side, "healthy", healthy_video, None)
    ref_amp = healthy_r.get("reach_amplitude_sw")
    pre_r = _run(pre_csv, pre_side, "pre", pre_video, None)
    post_r = _run(post_csv, post_side, "post", post_video, None)

    # Use native (non-upsampled) amplitudes for amplitude-matching decisions.
    # Upsampling can inflate reach amplitude via spline overshoot, especially for
    # short 30 fps videos, so matching targets must be derived from native coords.
    native_amps = {
        "healthy": healthy_r.get("native_reach_amplitude_sw"),
        "pre": pre_r.get("native_reach_amplitude_sw"),
        "post": post_r.get("native_reach_amplitude_sw"),
    }
    finite_native_amps = [float(v) for v in native_amps.values() if v is not None and np.isfinite(float(v)) and float(v) > 0]

    # --- Pass 2: literature-backed amplitude-matched SPARC --------------------
    # Use the smallest common amplitude (with a small safety margin) so every
    # condition is evaluated over the same movement extent. This mirrors the
    # amplitude-matching approach used in Balasubramanian et al. and Krebs et al.
    # However, if one condition is much shorter/smaller than the others, forced
    # matching would distort the comparison; in that case we skip matching and
    # warn instead.
    comparison_valid = True
    comparison_issues: List[str] = []
    comparison_warnings: List[str] = []
    matched_results: Dict[str, Dict[str, Any]] = {}
    target_amp: Optional[float] = None
    if finite_native_amps:
        min_amp = float(np.min(finite_native_amps))
        max_amp = float(np.max(finite_native_amps))
        amp_ratio = max_amp / min_amp if min_amp > 0 else float("inf")
        # Only force amplitude matching when the smallest reach is still clinically
        # meaningful (>= 0.30 SW) and the spread is within a factor of 2.
        if min_amp >= 0.30 and amp_ratio <= 2.0:
            target_amp = min_amp * 0.95
            for label, csv, side, vid in (
                ("pre", pre_csv, pre_side, pre_video),
                ("post", post_csv, post_side, post_video),
                ("healthy", healthy_csv, healthy_side, healthy_video),
            ):
                csv_for_pass2 = _extracted_csv_path(csv)
                matched_results[label] = analyze_trial(
                    csv_for_pass2,
                    affected_side=side,
                    trial_role=label,
                    video_path=vid,
                    reference_amplitude_sw=target_amp,
                    target_amplitude_sw=target_amp,
                    **analyze_kw,
                )
        else:
            comparison_warnings.append(
                f"Amplitude spread too large to apply safe amplitude matching "
                f"(max/min = {amp_ratio:.2f}, min = {min_amp:.2f} SW); "
                f"interpret cross-condition SPARC cautiously."
            )
            matched_results = {"pre": pre_r, "post": post_r, "healthy": healthy_r}
    else:
        matched_results = {"pre": pre_r, "post": post_r, "healthy": healthy_r}

    # Inject matched SPARC and interpretation into the primary results
    for label in ("pre", "post", "healthy"):
        mr = matched_results.get(label, {})
        primary = {"pre": pre_r, "post": post_r, "healthy": healthy_r}[label]
        primary["sparc_matched"] = mr.get("sparc")
        primary["sparc_matched_amplitude_sw"] = mr.get("reach_amplitude_sw")
        primary["sparc_matched_comparable"] = mr.get("sparc_comparable")
        primary["sparc_matched_window"] = (
            f"{mr.get('sparc_window_onset_frame')}-{mr.get('sparc_window_offset_frame')}"
            if mr.get("sparc_window_onset_frame") is not None
            else None
        )
        primary["sparc_interpretation"] = interpret_sparc(primary.get("sparc"))
        primary["sparc_matched_interpretation"] = interpret_sparc(mr.get("sparc"))

    # --- Cross-condition plausibility ----------------------------------------
    def _sp(label: str) -> Optional[float]:
        # Prefer amplitude-matched SPARC for comparison; fall back to original.
        r = matched_results.get(label, {})
        v = r.get("sparc")
        if v is not None and np.isfinite(float(v)):
            return float(v)
        return {"pre": pre_r, "post": post_r, "healthy": healthy_r}[label].get("sparc")

    sp_h, sp_pre, sp_post = _sp("healthy"), _sp("pre"), _sp("post")

    if _finite(sp_h) and _finite(sp_pre):
        if float(sp_h) <= float(sp_pre):
            comparison_valid = False
            comparison_issues.append(
                "Healthy SPARC is not higher than Pre SPARC; likely window or amplitude mismatch."
            )
    if _finite(sp_post) and _finite(sp_h):
        if float(sp_post) >= float(sp_h):
            comparison_valid = False
            comparison_issues.append(
                "Post SPARC is not lower than Healthy SPARC; check for true recovery ceiling or window mismatch."
            )
    if _finite(sp_post) and _finite(sp_pre):
        if float(sp_post) <= float(sp_pre):
            comparison_valid = False
            comparison_issues.append(
                "Post SPARC is not higher than Pre SPARC; no smoothness recovery detected."
            )

    # Amplitude matching advisory
    for label, trial_r in (("pre", pre_r), ("post", post_r)):
        ref_amp_v = trial_r.get("reference_amplitude_sw")
        amp = trial_r.get("reach_amplitude_sw")
        if (
            ref_amp_v is not None and np.isfinite(ref_amp_v) and ref_amp_v > 0
            and amp is not None and np.isfinite(amp) and amp > 0
        ):
            ratio = float(amp) / float(ref_amp_v)
            if ratio < 0.67 or ratio > 1.50:
                comparison_warnings.append(
                    f"{label} reach amplitude ({amp:.2f} SW) differs from healthy reference ({ref_amp_v:.2f} SW) by more than 50%; interpret SPARC comparison cautiously."
                )

    result = {
        "pre": pre_r,
        "post": post_r,
        "healthy": healthy_r,
        "reference_analysis": compute_patient_reference_gaps(pre_r, post_r, healthy_r),
    }
    result["sparc_comparison_valid"] = comparison_valid
    result["sparc_comparison_issues"] = comparison_issues
    result["sparc_comparison_warnings"] = comparison_warnings
    result["sparc_matched_available"] = len(finite_native_amps) > 0
    result["sparc_matched_target_amplitude_sw"] = round(float(target_amp), 3) if target_amp is not None else None
    result["sparc_rating_guide"] = {
        "excellent": ">= -1.5 (healthy ballistic)",
        "good": "-1.5 to -2.5 (mild compensation)",
        "moderate": "-2.5 to -3.5 (some segmentation)",
        "poor": "-3.5 to -5.0 (clearly segmented)",
        "very_poor": "< -5.0 (severely discontinuous)",
    }
    return result


def analyze_multiple_trials(
    csv_folder: str,
    fs: float = DEFAULT_FS,
    velocity_threshold: float = DEFAULT_VELOCITY_THRESHOLD_PX_S,
    camera_view: str = "auto",
    pattern: str = "*_landmarks.csv",
) -> pd.DataFrame:
    folder = Path(csv_folder)
    csv_files = sorted(folder.glob(pattern))
    all_results = []
    for csv_file in csv_files:
        try:
            row = analyze_trial(
                str(csv_file), fs=fs, velocity_threshold=velocity_threshold, camera_view=camera_view
            )
            row["trial_name"] = csv_file.stem
            all_results.append(row)
        except Exception as exc:
            all_results.append({"trial_name": csv_file.stem, "error": str(exc)})
    summary_df = pd.DataFrame(all_results)
    if len(summary_df):
        cols = ["trial_name"] + [c for c in summary_df.columns if c != "trial_name"]
        summary_df = summary_df[cols]
        summary_df.to_csv(folder / "kinematic_summary.csv", index=False)
    return summary_df


def analyze_stroke_kinematic_csv(
    csv_path: str,
    affected_side: str = "auto",
    metric_scale: float = 0.0,
    fs: Optional[float] = None,
    frame_width: int = DEFAULT_FRAME_WIDTH,
    frame_height: int = DEFAULT_FRAME_HEIGHT,
    velocity_threshold_px_s: float = DEFAULT_VELOCITY_THRESHOLD_PX_S,
    name: str = "",
    camera_view: str = "auto",
    task_mode: str = "reach_only",
    video_path: Optional[str] = None,
    trial_role: Optional[str] = None,
) -> Dict[str, Any]:
    """NeuroLab API entry — wraps analyze_trial with rounded export keys."""
    try:
        from motion_invariants import infer_trial_role
        from table_calibrator import find_video_for_csv

        df = pd.read_csv(csv_path)
        native_df = df.copy()
        df, native_fs, analysis_fs, upsampled = prepare_trial_timeseries(df)
        role = trial_role or infer_trial_role(csv_path, affected_side=affected_side)
        if not video_path:
            vid = find_video_for_csv(csv_path, None)
            video_path = str(vid) if vid else None
        # Pass the native dataframe so analyze_trial can upsample consistently.
        # (Passing the already-upsampled df with native_fs < 55 causes double upsampling.)
        raw = analyze_trial(
            csv_path,
            fs=analysis_fs,
            velocity_threshold=velocity_threshold_px_s,
            camera_view=camera_view,
            affected_side=affected_side,
            frame_width=frame_width,
            frame_height=frame_height,
            trial_df=native_df,
            native_fs=native_fs,
            upsampled=upsampled,
            task_mode=task_mode,
            video_path=video_path,
            trial_role=role,
        )
    except Exception as exc:
        return {"error": str(exc), "name": name or Path(csv_path).stem}

    def _r(v, n=4):
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return None
        return round(float(v), n)

    fs_hz = float(raw.get("analysis_fs_hz") or raw.get("fs_hz") or analysis_fs)
    sw_px = None
    if "palm_x" in df.columns and "shoulder_width" in df.columns:
        sw = df["shoulder_width"].iloc[0]
        if pd.notna(sw) and float(sw) > 0:
            sw_px = float(sw)
    elif "LEFT_SHOULDER_X" in df.columns:
        try:
            _, _, sw_px_val = _landmarks_from_mediapipe_csv(
                df, affected_side=affected_side, frame_width=frame_width, frame_height=frame_height
            )
            sw_px = sw_px_val if np.isfinite(sw_px_val) else None
        except KeyError:
            sw_px = None

    if "palm_x" in native_df.columns:
        px_native = native_df["palm_x"].astype(float).values
        py_native = native_df["palm_y"].astype(float).values
    else:
        lm, _, _ = _landmarks_from_mediapipe_csv(
            native_df, affected_side=affected_side, frame_width=frame_width, frame_height=frame_height
        )
        px_native, py_native = lm["palm_x"], lm["palm_y"]

    n_native = len(px_native)
    spd_native = np.sqrt(np.gradient(px_native) ** 2 + np.gradient(py_native) ** 2) * native_fs

    start_i = int(raw.get("movement_onset_frame") or 0)
    end_i = int(raw.get("movement_offset_frame") or (n_native - 1))

    # The raw window indices are on the analysis (upsampled) timeline, but the
    # exported dataframe and validation video use native video frames. Map them
    # back so the onset/offset point to the same moment in the original video.
    if upsampled and native_fs and fs_hz and abs(fs_hz - native_fs) > 1e-6:
        start_i, end_i = _map_frames_to_native_fs(start_i, end_i, fs_hz, native_fs, n_native)

    start_i = max(0, min(start_i, n_native - 1))
    end_i = max(start_i, min(end_i, n_native - 1))
    if end_i <= start_i:
        mask = spd_native > velocity_threshold_px_s
        start_i = int(np.where(mask)[0][0]) if np.any(mask) else 0
        end_i = int(np.where(mask)[0][-1]) if np.any(mask) else n_native - 1
    start_i = max(0, min(start_i, n_native - 1))
    end_i = max(start_i, min(end_i, n_native - 1))

    # Map other exported frame windows back to native indices for consistency.
    def _map_frame_key(key: str) -> Optional[int]:
        v = raw.get(key)
        if v is None:
            return None
        try:
            v = int(v)
        except Exception:
            return None
        if upsampled and native_fs and fs_hz and abs(fs_hz - native_fs) > 1e-6:
            _, v = _map_frames_to_native_fs(v, v, fs_hz, native_fs, n_native)
        return max(0, min(v, n_native - 1))

    sparc_onset_native = _map_frame_key("sparc_window_onset_frame")
    sparc_offset_native = _map_frame_key("sparc_window_offset_frame")

    if "palm_x" in df.columns:
        px = df["palm_x"].astype(float).values
        py = df["palm_y"].astype(float).values
    else:
        lm, _, _ = _landmarks_from_mediapipe_csv(
            df, affected_side=affected_side, frame_width=frame_width, frame_height=frame_height
        )
        px, py = lm["palm_x"], lm["palm_y"]

    spd = np.sqrt(np.gradient(px) ** 2 + np.gradient(py) ** 2) * fs_hz

    result = {
        # --- reach-to-grasp primary outcomes ---
        "nvp": _r(raw.get("nvp"), 0),
        "straightness": _r(raw.get("straightness"), 4),
        "pause_time_sec": _r(raw.get("pause_time_sec"), 3),
        "number_of_stops": _r(raw.get("number_of_stops"), 0),
        # --- secondary kinematic metrics ---
        "trunk_ratio": _r(raw.get("trunk_ratio"), 4),
        "shoulder_elevation_norm": _r(raw.get("shoulder_elevation_norm"), 4),
        "shoulder_vert_norm": _r(raw.get("shoulder_elevation_norm"), 4),
        "elbow_angle_mean_deg": _r(raw.get("elbow_angle_mean_deg"), 2),
        "elbow_angle_range_deg": _r(raw.get("elbow_angle_range_deg"), 2),
        "movement_time_sec": _r(raw.get("movement_time_sec"), 3),
        "peak_velocity_px_s": _r(raw.get("peak_velocity_px_s"), 2),
        "peak_velocity_cm_s": None,
        "time_to_peak_velocity_sec": _r(raw.get("time_to_peak_velocity_sec"), 3),
        "relative_time_to_peak_pct": _r(raw.get("relative_time_to_peak_pct"), 1),
        # --- legacy / supplementary values ---
        "hand_displacement_px": _r(raw.get("hand_displacement_px"), 2),
        "palm_displacement_raw_px": _r(raw.get("palm_displacement_raw_px"), 2),
        "trunk_displacement_px": _r(raw.get("trunk_displacement_px"), 2),
        "palm_displacement_px": _r(raw.get("palm_displacement_px"), 2),
        "shoulder_elevation_abs_px": _r(raw.get("shoulder_elevation_abs_px"), 2),
        "shoulder_width_px": round(sw_px, 2) if sw_px else None,
        "sparc": _r(raw.get("sparc"), 4),
        # --- physical-unit values (prefer metric_scale when provided) ---
        "hand_displacement_cm": None,
        "hand_displacement_norm": None,
        "hand_displacement_table_frac": None,
        "shoulder_elevation_cm": None,
        "cm_per_px": _r(raw.get("cm_per_px"), 5),
        "table_scale_method": raw.get("table_scale_method"),
        "table_width_cm": raw.get("table_width_cm"),
        "table_width_px": _r(raw.get("table_width_px"), 1),
        # --- metadata ---
        "_code_version": "stroke-kinematic-v24-reach2grasp",
        "task_mode": raw.get("task_mode", task_mode),
        "name": name or Path(csv_path).stem,
        "side_analyzed": raw.get("side_analyzed"),
        "camera_view": raw.get("camera_view") if (camera_view or "auto") == "auto" else camera_view,
        "body_orientation_ratio": raw.get("body_orientation_ratio"),
        "body_orientation_confidence": raw.get("body_orientation_confidence"),
        "analysis_frame": raw.get("analysis_frame"),
        "fs_hz": raw.get("fs_hz"),
        "native_fs_hz": raw.get("native_fs_hz", round(native_fs, 2)),
        "analysis_fs_hz": raw.get("analysis_fs_hz", round(fs_hz, 2)),
        "upsampled_to_60hz": raw.get("upsampled_to_60hz", upsampled),
        "frame_width_px": frame_width,
        "frame_height_px": frame_height,
        "velocity_threshold_px_s": velocity_threshold_px_s,
        "movement_onset_frame": start_i,
        "movement_offset_frame": end_i,
        "active_onset_s": round(start_i / native_fs, 3) if native_fs else round(start_i / fs_hz, 3),
        "active_offset_s": round(end_i / native_fs, 3) if native_fs else round(end_i / fs_hz, 3),
        "sparc_interpretation": raw.get("sparc_interpretation"),
        "sparc_active_frames": raw.get("sparc_active_frames"),
        "sparc_comparable": raw.get("sparc_comparable"),
        "sparc_method": raw.get("sparc_method"),
        "sparc_window_onset_frame": sparc_onset_native,
        "sparc_window_offset_frame": sparc_offset_native,
        "sparc_matched": _r(raw.get("sparc_matched"), 4),
        "sparc_matched_interpretation": raw.get("sparc_matched_interpretation"),
        "sparc_matched_amplitude_sw": _r(raw.get("sparc_matched_amplitude_sw"), 3),
        "sparc_matched_comparable": raw.get("sparc_matched_comparable"),
        "sparc_matched_window": raw.get("sparc_matched_window"),
        "comparison_role": raw.get("comparison_role"),
        "sparc_primary_comparison": raw.get("sparc_primary_comparison"),
        "amplitude_matched": raw.get("amplitude_matched"),
        "reference_amplitude_sw": _r(raw.get("reference_amplitude_sw"), 3),
        "trial_valid": raw.get("trial_valid"),
        "metrics_comparable": raw.get("metrics_comparable"),
        "reach_valid": raw.get("reach_valid"),
        "trunk_valid": raw.get("trunk_valid"),
        "sparc_valid": raw.get("sparc_valid"),
        "reach_phase": raw.get("reach_phase"),
        "quality_flags": raw.get("quality_flags") or [],
        "quality_issues": raw.get("quality_issues") or [],
        "reach_amplitude_sw": _r(raw.get("reach_amplitude_sw"), 3),
        "shoulder_elevation_norm": _r(raw.get("shoulder_elevation_norm"), 4),
        "shoulder_vert_norm": _r(raw.get("shoulder_elevation_norm"), 4),
        "hand_displacement_endpoint_sw": _r(raw.get("hand_displacement_endpoint_sw"), 3),
        "hand_displacement_limb_norm": _r(raw.get("hand_displacement_limb_norm"), 3),
        "hand_displacement_trunk_norm": _r(raw.get("hand_displacement_trunk_norm"), 3),
        "hand_disp_sw": _r(raw.get("hand_disp_sw"), 3),
        "trunk_path_ratio": _r(raw.get("trunk_path_ratio"), 4),
        "trunk_disp_ratio": _r(raw.get("trunk_disp_ratio"), 4),
        "trunk_cheat_ratio": _r(raw.get("trunk_cheat_ratio"), 2),
        "hand_displacement_method": raw.get("hand_displacement_method"),
        "movement_time_window": raw.get("movement_time_window"),
        "reach_only_duration_s": raw.get("reach_only_duration_s"),
        "movement_metrics_duration_s": raw.get("movement_metrics_duration_s"),
        "shoulder_elevation_method": raw.get("shoulder_elevation_method"),
        "shoulder_elevation_side_view_warning": raw.get("shoulder_elevation_method") == "range_y_norm",
        "data_quality": {
            "total_frames": len(df),
            "movement_frames": end_i - start_i + 1,
            "native_fs_hz": round(native_fs, 2),
            "trial_valid": raw.get("trial_valid"),
            "metrics_comparable": raw.get("metrics_comparable"),
            "quality_flags": raw.get("quality_flags") or [],
            "frame_quality_pct": raw.get("frame_quality_pct"),
        },
        "landmark_tracking_enhanced": raw.get("landmark_tracking_enhanced"),
        "trunk_proxy": raw.get("trunk_proxy"),
    }

    # --- Physical-unit conversion: prefer user-provided metric_scale (shoulder width in m) ---
    user_provided_scale = bool(metric_scale and metric_scale > 0 and sw_px and sw_px > 0)
    if user_provided_scale:
        px_to_m = metric_scale / sw_px
        result["metric_scale_m"] = round(metric_scale, 4)
        result["shoulder_width_cm"] = round(metric_scale * 100, 1)
        result["cm_per_px"] = round(px_to_m * 100, 5)
        result["table_scale_method"] = "user_shoulder_width"
        if result["hand_displacement_px"] is not None:
            result["hand_displacement_cm"] = round(result["hand_displacement_px"] * px_to_m * 100, 2)
            result["hand_displacement_norm"] = result["hand_displacement_cm"]
            if result["table_width_cm"]:
                result["hand_displacement_table_frac"] = round(
                    result["hand_displacement_cm"] / result["table_width_cm"], 3
                )
        if result["peak_velocity_px_s"] is not None:
            result["peak_velocity_cm_s"] = round(result["peak_velocity_px_s"] * px_to_m * 100, 2)
            result["peak_velocity_m_s"] = round(result["peak_velocity_px_s"] * px_to_m, 3)
        if result["shoulder_elevation_abs_px"] is not None:
            result["shoulder_elevation_cm"] = round(result["shoulder_elevation_abs_px"] * px_to_m * 100, 2)
    else:
        # Fallback to table/shoulder-width calibration when no user scale supplied.
        result["hand_displacement_cm"] = _r(raw.get("hand_displacement_cm"), 2)
        result["hand_displacement_norm"] = _r(raw.get("hand_displacement_norm"), 2)
        result["hand_displacement_table_frac"] = _r(raw.get("hand_displacement_table_frac"), 3)
        result["peak_velocity_cm_s"] = _r(raw.get("peak_velocity_cm_s"), 2)

    return result


if __name__ == "__main__":
    print("Stroke Kinematic Analysis Ready!")
    print("View-agnostic: auto-detects side / frontal / oblique from CSV metadata or geometry.")
