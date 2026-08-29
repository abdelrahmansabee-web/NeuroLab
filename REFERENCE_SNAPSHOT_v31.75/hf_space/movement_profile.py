# -*- coding: utf-8 -*-
"""
Task-agnostic movement profile — joint angles, speeds, compensations, quality index.

Uses the same movement window as trunk/elbow metrics (kin_start..kin_end) but also
reports how many distinct movement bouts were detected in the clip.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import find_peaks

from motion_invariants import (
    _list_segments,
    compute_elbow_reach_metric,
    hand_landmarker_window_coverage,
    palm_image_speed,
    resolve_fine_motor_hand_coords,
)


def _elbow_angles_series(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    start: int,
    end: int,
) -> np.ndarray:
    from motion_invariants import elbow_angle_2d_frame

    angles = np.full(end - start + 1, np.nan)
    for j, i in enumerate(range(start, end + 1)):
        a = elbow_angle_2d_frame(
            shoulder_x[i], shoulder_y[i],
            elbow_x[i], elbow_y[i],
            wrist_x[i], wrist_y[i],
        )
        if np.isfinite(a):
            angles[j] = a
    return angles


def _shoulder_flexion_series(
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    start: int,
    end: int,
) -> np.ndarray:
    from motion_invariants import shoulder_flexion_2d_frame

    angles = np.full(end - start + 1, np.nan)
    n = len(shoulder_x)
    for j, i in enumerate(range(start, end + 1)):
        tx = float(trunk_x[i]) if i < len(trunk_x) and np.isfinite(trunk_x[i]) else float("nan")
        ty = float(trunk_y[i]) if i < len(trunk_y) and np.isfinite(trunk_y[i]) else float("nan")
        if not np.isfinite(tx) or not np.isfinite(ty):
            tx = float(shoulder_x[i])
            ty = float(shoulder_y[i]) + 0.12
        a = shoulder_flexion_2d_frame(
            tx, ty,
            shoulder_x[i], shoulder_y[i],
            elbow_x[i], elbow_y[i],
        )
        if np.isfinite(a):
            angles[j] = a
    return angles


def _angular_velocity_deg_s(angles: np.ndarray, fs: float) -> np.ndarray:
    if len(angles) < 2:
        return np.array([], dtype=float)
    return np.abs(np.gradient(angles) * fs)


def _summarize_angle_block(prefix: str, angles: np.ndarray, fs: float) -> Dict[str, Any]:
    """Min/max/ROM/mean and peak/mean angular speed for a joint angle series."""
    out: Dict[str, Any] = {}
    if len(angles) == 0:
        return out
    ang_vel = _angular_velocity_deg_s(angles, fs)
    amin = float(np.nanmin(angles))
    amax = float(np.nanmax(angles))
    arom = float(amax - amin)
    amean = float(np.nanmean(angles))
    peak_v = float(np.nanmax(ang_vel)) if len(ang_vel) else float("nan")
    mean_v = float(np.nanmean(ang_vel)) if len(ang_vel) else float("nan")
    out[f"{prefix}_min_deg"] = round(amin, 1) if np.isfinite(amin) else None
    out[f"{prefix}_max_deg"] = round(amax, 1) if np.isfinite(amax) else None
    out[f"{prefix}_rom_deg"] = round(arom, 1) if np.isfinite(arom) else None
    out[f"{prefix}_mean_deg"] = round(amean, 1) if np.isfinite(amean) else None
    out[f"peak_{prefix}_vel_deg_s"] = round(peak_v, 1) if np.isfinite(peak_v) else None
    out[f"mean_{prefix}_vel_deg_s"] = round(mean_v, 1) if np.isfinite(mean_v) else None
    return out


def _shoulder_abduction_world_series(
    side: str,
    hand_world: Dict[str, np.ndarray],
    arm_world: Dict[str, np.ndarray],
    start: int,
    end: int,
) -> np.ndarray:
    from motion_invariants import shoulder_abduction_world_frame

    angles = np.full(end - start + 1, np.nan)
    for j, i in enumerate(range(start, end + 1)):
        a = shoulder_abduction_world_frame(side, hand_world, arm_world, i)
        if np.isfinite(a):
            angles[j] = a
    return angles


def _sparc_on_angle_series(angles: np.ndarray, fs: float) -> float:
    if len(angles) < 12:
        return float("nan")
    ang_vel = np.abs(np.gradient(np.asarray(angles, dtype=float)) * fs)
    if np.all(ang_vel == 0):
        return float("nan")
    from stroke_kinematic_pipeline import calculate_sparc_from_speed

    return float(calculate_sparc_from_speed(ang_vel, fs=fs, fc=10.0, amp_th=0.05))


def _abduction_trunk_compensation_index(
    shoulder_abduction_rom: float,
    trunk_ratio: float,
    shoulder_abduction_mean: float,
) -> Optional[float]:
    """High when trunk assists an abduction-like arm raise (whole-shoulder strategy)."""
    if not np.isfinite(trunk_ratio):
        return None
    abd_factor = 0.0
    if np.isfinite(shoulder_abduction_rom):
        abd_factor = min(1.0, shoulder_abduction_rom / 90.0)
    elif np.isfinite(shoulder_abduction_mean):
        abd_factor = min(1.0, shoulder_abduction_mean / 120.0)
    if abd_factor < 0.15:
        return round(float(min(1.0, trunk_ratio * 0.5)), 3)
    return round(float(min(1.0, 0.55 * trunk_ratio + 0.45 * abd_factor)), 3)


def _hand_landmarker_pinch_metrics(
    hand3d: Optional[Dict[str, np.ndarray]],
    fs: float,
    start: int,
    end: int,
    shoulder_width: Optional[float],
) -> Dict[str, Any]:
    """Pinch aperture + 8–12 Hz tremor from Hand Landmarker tips when available."""
    if hand3d is None or "index_tip_x" not in hand3d or "thumb_tip_x" not in hand3d:
        return {}
    if hand_landmarker_window_coverage(hand3d, start, end) < 0.35:
        return {}
    ix = hand3d["index_tip_x"]
    iy = hand3d["index_tip_y"]
    tx = hand3d["thumb_tip_x"]
    ty = hand3d["thumb_tip_y"]
    if end <= start or len(ix) <= end:
        return {}
    from motion_invariants import tremor_band_power

    dist = np.hypot(ix - tx, iy - ty)[start : end + 1]
    if not np.any(np.isfinite(dist)):
        return {}
    rom = float(np.nanmax(dist) - np.nanmin(dist))
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    rom_sw = float(rom / sw) if np.isfinite(sw) and sw > 0 else float("nan")
    tremor = tremor_band_power(dist / sw if np.isfinite(sw) and sw > 0 else dist, fs)
    mean_d = float(np.nanmean(dist))
    cv = float(np.nanstd(dist) / mean_d) if mean_d > 1e-6 else float("nan")
    q_parts = []
    if np.isfinite(rom_sw):
        q_parts.append(40.0 * min(1.0, rom_sw * 5.0))
    if np.isfinite(tremor):
        q_parts.append(35.0 * (1.0 - min(1.0, tremor * 8.0)))
    if np.isfinite(cv):
        q_parts.append(25.0 * (1.0 - min(1.0, cv)))
    pinch_q = float(np.clip(sum(q_parts), 0.0, 100.0)) if q_parts else None
    return {
        "hand_landmarker_used": True,
        "pinch_aperture_hl_rom_px": round(rom, 2) if np.isfinite(rom) else None,
        "pinch_aperture_hl_rom_sw": round(rom_sw, 4) if np.isfinite(rom_sw) else None,
        "pinch_tremor_8_12hz_power": round(tremor, 4) if np.isfinite(tremor) else None,
        "pinch_grasp_quality_index": round(pinch_q, 1) if pinch_q is not None else None,
    }


def _finger_flex_ext_metrics(
    hand3d: Optional[Dict[str, np.ndarray]],
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    index_x: Optional[np.ndarray],
    index_y: Optional[np.ndarray],
    pinky_x: Optional[np.ndarray],
    pinky_y: Optional[np.ndarray],
    thumb_x: Optional[np.ndarray],
    thumb_y: Optional[np.ndarray],
    fs: float,
    start: int,
    end: int,
    shoulder_width: Optional[float],
) -> Dict[str, Any]:
    """Finger open/close ROM (tip–wrist distance) and movement quality during ADL."""
    if end <= start:
        return {}
    roms_sw: List[float] = []
    dist_traces: List[np.ndarray] = []
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    hl_ok = (
        hand3d is not None
        and "index_tip_x" in hand3d
        and hand_landmarker_window_coverage(hand3d, start, end) >= 0.35
    )
    wx_use = hand3d["wrist_hl_x"] if hl_ok and hand3d and "wrist_hl_x" in hand3d else wrist_x
    wy_use = hand3d["wrist_hl_y"] if hl_ok and hand3d and "wrist_hl_y" in hand3d else wrist_y

    def _tip_wrist_rom(tx: np.ndarray, ty: np.ndarray) -> Optional[float]:
        dist = np.hypot(tx - wx_use, ty - wy_use)[start : end + 1]
        if not np.any(np.isfinite(dist)):
            return None
        dist_traces.append(dist)
        rom = float(np.nanmax(dist) - np.nanmin(dist))
        if np.isfinite(sw) and sw > 0:
            return float(rom / sw)
        return rom

    if hand3d and hl_ok:
        for key in ("index_tip", "thumb_tip", "middle_tip", "ring_tip", "pinky_tip"):
            if f"{key}_x" in hand3d and f"{key}_y" in hand3d:
                r = _tip_wrist_rom(hand3d[f"{key}_x"], hand3d[f"{key}_y"])
                if r is not None and np.isfinite(r):
                    roms_sw.append(r)

    if not hl_ok:
        for tx, ty in ((index_x, index_y), (pinky_x, pinky_y), (thumb_x, thumb_y)):
            if tx is not None and ty is not None and len(tx) > end:
                r = _tip_wrist_rom(tx, ty)
                if r is not None and np.isfinite(r):
                    roms_sw.append(r)

    if not roms_sw:
        return {}

    mean_rom_sw = float(np.nanmean(roms_sw))
    max_rom_sw = float(np.nanmax(roms_sw))
    cv = float("nan")
    if dist_traces:
        min_len = min(len(d) for d in dist_traces)
        if min_len > 2:
            stacked = np.vstack([d[:min_len] for d in dist_traces])
            combined = np.nanmean(stacked, axis=0)
            mu = float(np.nanmean(combined))
            if mu > 1e-6:
                cv = float(np.nanstd(combined) / mu)

    q_parts: List[float] = []
    if np.isfinite(mean_rom_sw):
        q_parts.append(45.0 * min(1.0, mean_rom_sw * 6.0))
    if np.isfinite(max_rom_sw):
        q_parts.append(25.0 * min(1.0, max_rom_sw * 4.0))
    if np.isfinite(cv):
        q_parts.append(30.0 * (1.0 - min(1.0, cv)))
    quality = float(np.clip(sum(q_parts), 0.0, 100.0)) if q_parts else None

    return {
        "hand_landmarker_finger_flex_ext": hl_ok,
        "finger_flex_ext_rom_sw": round(mean_rom_sw, 4) if np.isfinite(mean_rom_sw) else None,
        "finger_flex_ext_max_rom_sw": round(max_rom_sw, 4) if np.isfinite(max_rom_sw) else None,
        "finger_flex_ext_quality_index": round(quality, 1) if quality is not None else None,
    }


def _head_forward_flexion_metrics(
    nose_x: Optional[np.ndarray],
    nose_y: Optional[np.ndarray],
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    opp_shoulder_x: Optional[np.ndarray],
    opp_shoulder_y: Optional[np.ndarray],
    trunk_x: Optional[np.ndarray],
    trunk_y: Optional[np.ndarray],
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    start: int,
    end: int,
    shoulder_width: Optional[float],
) -> Dict[str, Any]:
    """
    Head forward lean + flexion toward cup during drink (higher = worse compensation).
    Uses nose vs shoulder girdle; stable head ≈ lower index.
    """
    if nose_x is None or nose_y is None or end <= start or len(nose_x) <= end:
        return {}

    if opp_shoulder_x is not None and opp_shoulder_y is not None:
        smx = (shoulder_x + opp_shoulder_x) / 2.0
        smy = (shoulder_y + opp_shoulder_y) / 2.0
    elif trunk_x is not None and trunk_y is not None:
        smx, smy = trunk_x, trunk_y
    else:
        smx, smy = shoulder_x, shoulder_y

    dx0 = float(palm_x[start] - nose_x[start])
    dy0 = float(palm_y[start] - nose_y[start])
    mag0 = float(np.hypot(dx0, dy0))
    if mag0 < 1e-6:
        ux, uy = 1.0, 0.0
    else:
        ux, uy = dx0 / mag0, dy0 / mag0

    projections: List[float] = []
    flex_angles: List[float] = []
    n0x, n0y = float(nose_x[start]), float(nose_y[start])
    for i in range(start, end + 1):
        nx, ny = float(nose_x[i]), float(nose_y[i])
        projections.append((nx - n0x) * ux + (ny - n0y) * uy)
        sx = float(smx[i])
        sy = float(smy[i])
        flex_angles.append(float(np.degrees(np.arctan2(ny - sy, abs(nx - sx) + 1e-6))))

    proj = np.asarray(projections, dtype=float)
    flex = np.asarray(flex_angles, dtype=float)
    forward_increase = max(0.0, float(np.nanmax(proj) - proj[0]))
    flex_increase = max(0.0, float(np.nanmax(flex) - flex[0]))
    flex_rom = float(np.nanmax(flex) - np.nanmin(flex))

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    forward_sw = float(forward_increase / sw) if np.isfinite(sw) else float("nan")

    parts: List[float] = []
    if np.isfinite(forward_sw):
        parts.append(min(1.0, forward_sw / 0.20))
    parts.append(min(1.0, flex_increase / 20.0))
    comp = float(np.clip(np.mean(parts), 0.0, 1.0)) if parts else None

    return {
        "head_forward_displacement_sw": round(forward_sw, 4) if np.isfinite(forward_sw) else None,
        "head_flexion_rom_deg": round(flex_rom, 2) if np.isfinite(flex_rom) else None,
        "head_flexion_increase_deg": round(flex_increase, 2) if np.isfinite(flex_increase) else None,
        "head_forward_flexion_compensation_index": round(comp, 3) if comp is not None else None,
    }


def _tremor_metrics_block(
    *,
    fs: float,
    start: int,
    end: int,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    elbow_angles: Optional[np.ndarray] = None,
    shoulder_flex_angles: Optional[np.ndarray] = None,
    index_x: Optional[np.ndarray] = None,
    index_y: Optional[np.ndarray] = None,
    shoulder_width: Optional[float] = None,
    pinch_distance: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """8–12 Hz relative power on hand speed and joint traces (all tasks)."""
    from motion_invariants import compute_tremor_metrics_block

    return compute_tremor_metrics_block(
        fs=fs,
        start=start,
        end=end,
        palm_x=palm_x,
        palm_y=palm_y,
        elbow_angles=elbow_angles,
        shoulder_flex_angles=shoulder_flex_angles,
        index_x=index_x,
        index_y=index_y,
        pinch_distance=pinch_distance,
        shoulder_width=shoulder_width,
    )


def _shoulder_abduction_series(
    opp_shoulder_x: np.ndarray,
    opp_shoulder_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    start: int,
    end: int,
) -> np.ndarray:
    from motion_invariants import shoulder_abduction_2d_frame

    angles = np.full(end - start + 1, np.nan)
    for j, i in enumerate(range(start, end + 1)):
        a = shoulder_abduction_2d_frame(
            opp_shoulder_x[i], opp_shoulder_y[i],
            shoulder_x[i], shoulder_y[i],
            elbow_x[i], elbow_y[i],
        )
        if np.isfinite(a):
            angles[j] = a
    return angles


def _forearm_rotation_series(
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    elbow_z: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    wrist_z: np.ndarray,
    index_x: np.ndarray,
    index_y: np.ndarray,
    index_z: np.ndarray,
    pinky_x: np.ndarray,
    pinky_y: np.ndarray,
    pinky_z: np.ndarray,
    start: int,
    end: int,
    baseline_frames: int = 12,
) -> np.ndarray:
    from motion_invariants import forearm_pronation_supination_deg_frame

    ref_normal = None
    baseline_end = min(end, start + max(1, baseline_frames) - 1)
    for i in range(start, baseline_end + 1):
        _, ref_normal = forearm_pronation_supination_deg_frame(
            (elbow_x[i], elbow_y[i], elbow_z[i]),
            (wrist_x[i], wrist_y[i], wrist_z[i]),
            (index_x[i], index_y[i], index_z[i]),
            (pinky_x[i], pinky_y[i], pinky_z[i]),
            ref_palm_normal=None,
        )

    angles = np.full(end - start + 1, np.nan)
    for j, i in enumerate(range(start, end + 1)):
        ang, ref_normal = forearm_pronation_supination_deg_frame(
            (elbow_x[i], elbow_y[i], elbow_z[i]),
            (wrist_x[i], wrist_y[i], wrist_z[i]),
            (index_x[i], index_y[i], index_z[i]),
            (pinky_x[i], pinky_y[i], pinky_z[i]),
            ref_palm_normal=ref_normal,
        )
        if np.isfinite(ang):
            angles[j] = ang
    return angles


def _forearm_rotation_series_2d(
    index_x: np.ndarray,
    index_y: np.ndarray,
    pinky_x: np.ndarray,
    pinky_y: np.ndarray,
    start: int,
    end: int,
    baseline_frames: int = 12,
) -> np.ndarray:
    from motion_invariants import hand_roll_2d_proxy_deg

    rest_vals = []
    baseline_end = min(end, start + max(1, baseline_frames) - 1)
    for i in range(start, baseline_end + 1):
        v = hand_roll_2d_proxy_deg(index_x[i], index_y[i], pinky_x[i], pinky_y[i])
        if np.isfinite(v):
            rest_vals.append(v)
    rest = float(np.nanmedian(rest_vals)) if rest_vals else 0.0
    angles = np.full(end - start + 1, np.nan)
    for j, i in enumerate(range(start, end + 1)):
        v = hand_roll_2d_proxy_deg(index_x[i], index_y[i], pinky_x[i], pinky_y[i])
        if np.isfinite(v):
            angles[j] = v - rest
    return angles


def _fine_motor_metrics(
    index_x: np.ndarray,
    index_y: np.ndarray,
    fs: float,
    start: int,
    end: int,
    thumb_x: Optional[np.ndarray] = None,
    thumb_y: Optional[np.ndarray] = None,
    shoulder_width: Optional[float] = None,
) -> Dict[str, Any]:
    """Index-tip dexterity: speed variability, micro-stops, optional pinch ROM."""
    from scipy.signal import find_peaks

    n = len(index_x)
    if end <= start or n < 2:
        return {}
    seg_x = index_x[start : end + 1]
    seg_y = index_y[start : end + 1]
    if len(seg_x) < 3:
        return {}
    vx = np.gradient(seg_x) * fs
    vy = np.gradient(seg_y) * fs
    spd = np.hypot(vx, vy)
    peak = float(np.nanmax(spd)) if len(spd) else 0.0
    mean_pos = float(np.nanmean(spd[spd > 0])) if np.any(spd > 0) else float("nan")
    cv = float(np.nanstd(spd) / mean_pos) if np.isfinite(mean_pos) and mean_pos > 1e-6 else float("nan")

    thr = 0.08 * peak if peak > 0 else 1.0
    micro_stops = 0
    for i in range(1, len(spd)):
        if spd[i - 1] >= thr and spd[i] < thr:
            micro_stops += 1

    nvp = 0
    if peak > 0 and len(spd) > 5:
        prom = max(0.05 * peak, 1.0)
        peaks, _ = find_peaks(spd, prominence=prom, distance=max(2, int(0.08 * fs)))
        nvp = int(len(peaks))

    pinch_rom = float("nan")
    if thumb_x is not None and thumb_y is not None and len(thumb_x) == n:
        dist = np.hypot(index_x - thumb_x, index_y - thumb_y)[start : end + 1]
        if np.any(np.isfinite(dist)):
            pinch_rom = float(np.nanmax(dist) - np.nanmin(dist))

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float("nan")
    pinch_rom_norm = float(pinch_rom / sw) if np.isfinite(pinch_rom) and np.isfinite(sw) else float("nan")

    quality_parts = []
    if np.isfinite(cv):
        quality_parts.append(35.0 * (1.0 - min(1.0, cv)))
    quality_parts.append(25.0 * (1.0 - min(1.0, micro_stops / 8.0)))
    quality_parts.append(25.0 * (1.0 - min(1.0, max(0, nvp - 1) / 6.0)))
    if np.isfinite(pinch_rom_norm) and pinch_rom_norm > 0:
        quality_parts.append(15.0 * min(1.0, pinch_rom_norm * 4.0))
    fine_q = float(np.clip(sum(quality_parts), 0.0, 100.0)) if quality_parts else None

    return {
        "fine_motor_index_speed_cv": round(cv, 3) if np.isfinite(cv) else None,
        "fine_motor_index_nvp": int(nvp),
        "fine_motor_micro_stops": int(micro_stops),
        "pinch_aperture_rom_px": round(pinch_rom, 2) if np.isfinite(pinch_rom) else None,
        "pinch_aperture_rom_sw": round(pinch_rom_norm, 4) if np.isfinite(pinch_rom_norm) else None,
        "fine_motor_quality_index": round(fine_q, 1) if fine_q is not None else None,
    }


def _joint_quality_index(
    rom_deg: float,
    peak_vel: float,
    pause_frac: float,
    compensation: Optional[float],
) -> Optional[float]:
    parts = []
    if np.isfinite(rom_deg):
        parts.append(min(35.0, rom_deg * 0.35))
    if np.isfinite(peak_vel):
        parts.append(min(25.0, peak_vel * 0.08))
    if np.isfinite(pause_frac):
        parts.append(25.0 * (1.0 - min(1.0, pause_frac)))
    if compensation is not None and np.isfinite(compensation):
        parts.append(15.0 * (1.0 - min(1.0, compensation)))
    if not parts:
        return None
    return float(np.clip(sum(parts), 0.0, 100.0))


def _nvp_and_peaks(speed: np.ndarray, fs: float, prominence_frac: float = 0.30) -> Tuple[int, List[int]]:
    speed = np.asarray(speed, dtype=float)
    if len(speed) < 5:
        return 0, []
    peak = float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0
    if peak <= 0:
        return 0, []
    prom = prominence_frac * peak
    peaks, _ = find_peaks(speed, prominence=prom)
    return int(len(peaks)), [int(p) for p in peaks]


def _straightness_palm(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    start: int,
    end: int,
) -> float:
    if end <= start:
        return float("nan")
    path = 0.0
    for i in range(start + 1, end + 1):
        path += float(np.hypot(palm_x[i] - palm_x[i - 1], palm_y[i] - palm_y[i - 1]))
    disp = float(np.hypot(palm_x[end] - palm_x[start], palm_y[end] - palm_y[start]))
    if path <= 0:
        return float("nan")
    return float(min(1.0, disp / path))


def _pause_and_stops(speed: np.ndarray, fs: float, start: int, end: int) -> Tuple[float, int]:
    seg = speed[start : end + 1]
    if len(seg) == 0:
        return 0.0, 0
    peak = float(np.nanmax(seg)) if np.any(np.isfinite(seg)) else 0.0
    thr = 0.05 * peak if peak > 0 else 1.0
    pause_frames = 0
    stops = 0
    for j in range(len(seg)):
        if seg[j] < thr:
            pause_frames += 1
        if j > 0 and seg[j - 1] >= thr and seg[j] < thr:
            stops += 1
    return pause_frames / fs, stops


def _shoulder_elevation_palm_ratio(
    shoulder_y: np.ndarray,
    palm_y: np.ndarray,
    shoulder_width: Optional[float],
    start: int,
    end: int,
) -> float:
    """Max shoulder rise above rest palm height, normalized by shoulder width."""
    if end <= start:
        return float("nan")
    rest_n = max(1, min(10, (end - start) // 10))
    palm_rest = float(np.median(palm_y[start : start + rest_n]))
    sh_rest = float(np.median(shoulder_y[start : start + rest_n]))
    denom = float(shoulder_width) if shoulder_width and shoulder_width > 0 else abs(palm_rest - sh_rest)
    if denom < 1e-6:
        denom = 1.0
    max_ratio = 0.0
    for i in range(start, end + 1):
        # Shoulder higher in image = smaller y
        rise = max(0.0, palm_rest - shoulder_y[i])
        max_ratio = max(max_ratio, rise / denom)
    return float(max_ratio)


def _infer_task_pattern(segments: List[Dict[str, float]], movement_duration_s: float) -> str:
    if not segments:
        return "minimal_motion"
    if len(segments) == 1:
        return "single_bout"
    durs = [s["dur"] for s in segments]
    med = float(np.median(durs))
    if med > 0 and all(abs(d - med) / med < 0.45 for d in durs) and len(segments) >= 2:
        return "repetitive"
    if movement_duration_s > 4.0 and len(segments) >= 3:
        return "multi_phase"
    return "multi_bout"


def _movement_quality_index(
    straightness: float,
    nvp: int,
    movement_time_sec: float,
    trunk_ratio: float,
    shoulder_elev: float,
    pause_time_sec: float,
) -> Optional[float]:
    """0–100 heuristic: smoother, straighter, less compensatory → higher."""
    parts = []
    if np.isfinite(straightness):
        parts.append(float(np.clip(straightness, 0, 1)) * 30.0)
    if movement_time_sec > 0.1:
        nvp_pen = min(25.0, max(0.0, (nvp - 1) * 4.0))
        parts.append(25.0 - nvp_pen)
        pause_frac = pause_time_sec / movement_time_sec
        parts.append(20.0 * (1.0 - min(1.0, pause_frac)))
    if np.isfinite(trunk_ratio):
        parts.append(15.0 * (1.0 - min(1.0, trunk_ratio)))
    if np.isfinite(shoulder_elev):
        parts.append(10.0 * (1.0 - min(1.0, shoulder_elev * 2.0)))
    if not parts:
        return None
    return float(np.clip(sum(parts), 0.0, 100.0))


def _compensation_index(trunk_ratio: float, shoulder_elev: float, trunk_cheat: float) -> Optional[float]:
    """0 = minimal compensation, 1 = high (heuristic blend)."""
    vals = []
    if np.isfinite(trunk_ratio):
        vals.append(min(1.0, trunk_ratio))
    if np.isfinite(shoulder_elev):
        vals.append(min(1.0, shoulder_elev * 1.5))
    if np.isfinite(trunk_cheat):
        vals.append(min(1.0, max(0.0, trunk_cheat - 1.0)))
    if not vals:
        return None
    return float(np.clip(np.mean(vals), 0.0, 1.0))


def build_movement_profile(
    *,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    trunk_x: Optional[np.ndarray] = None,
    trunk_y: Optional[np.ndarray] = None,
    fs: float,
    shoulder_width: Optional[float],
    start_idx: int,
    end_idx: int,
    camera_view: str = "unknown",
    arm3d: Optional[Dict[str, np.ndarray]] = None,
    trunk_ratio: float = float("nan"),
    trunk_cheat_ratio: float = float("nan"),
    velocity_threshold: float = 5.0,
    opp_shoulder_x: Optional[np.ndarray] = None,
    opp_shoulder_y: Optional[np.ndarray] = None,
    index_x: Optional[np.ndarray] = None,
    index_y: Optional[np.ndarray] = None,
    pinky_x: Optional[np.ndarray] = None,
    pinky_y: Optional[np.ndarray] = None,
    thumb_x: Optional[np.ndarray] = None,
    thumb_y: Optional[np.ndarray] = None,
    hand3d: Optional[Dict[str, np.ndarray]] = None,
    arm_world: Optional[Dict[str, np.ndarray]] = None,
    hand_world: Optional[Dict[str, np.ndarray]] = None,
    affected_side: str = "auto",
    clinical_task: Optional[str] = None,
    nose_x: Optional[np.ndarray] = None,
    nose_y: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """Numeric movement specification for any upper-limb task clip."""
    n = len(palm_x)
    start = int(max(0, min(start_idx, n - 1)))
    end = int(max(start, min(end_idx, n - 1)))

    spd_full = palm_image_speed(palm_x, palm_y, fs)
    segments = _list_segments(
        spd_full, palm_x, palm_y, fs, velocity_threshold,
        min_segment_frames=max(8, int(0.15 * fs)),
    )
    movement_duration_s = (end - start + 1) / fs if fs > 0 else 0.0
    task_pattern = _infer_task_pattern(segments, movement_duration_s)

    spd_win = spd_full[start : end + 1]
    nvp, peak_frames = _nvp_and_peaks(spd_win, fs)
    straightness = _straightness_palm(palm_x, palm_y, start, end)
    pause_time_sec, number_of_stops = _pause_and_stops(spd_full, fs, start, end)

    peak_velocity = float(np.nanmax(spd_win)) if len(spd_win) else float("nan")
    mean_velocity = float(np.nanmean(spd_win[spd_win > 0])) if np.any(spd_win > 0) else float("nan")

    elbow_reach = compute_elbow_reach_metric(
        shoulder_x, shoulder_y, elbow_x, elbow_y, wrist_x, wrist_y,
        start, end, arm3d=arm3d, camera_view=camera_view,
    )
    angles = _elbow_angles_series(
        shoulder_x, shoulder_y, elbow_x, elbow_y, wrist_x, wrist_y, start, end,
    )
    ang_vel = _angular_velocity_deg_s(angles, fs)
    peak_elbow_ang_vel = float(np.nanmax(ang_vel)) if len(ang_vel) else float("nan")
    mean_elbow_ang_vel = float(np.nanmean(ang_vel)) if len(ang_vel) else float("nan")

    elbow_finite = angles[np.isfinite(angles)]
    elbow_min = float(np.nanmin(elbow_finite)) if len(elbow_finite) else float("nan")
    elbow_max = float(np.nanmax(elbow_finite)) if len(elbow_finite) else float("nan")
    elbow_rom = float(elbow_max - elbow_min) if len(elbow_finite) else float("nan")
    elbow_mean = float(np.nanmean(elbow_finite)) if len(elbow_finite) else float("nan")

    if trunk_x is None or trunk_y is None:
        trunk_x = np.full(n, np.nan)
        trunk_y = np.full(n, np.nan)
    sh_flex = _shoulder_flexion_series(
        trunk_x, trunk_y, shoulder_x, shoulder_y, elbow_x, elbow_y, start, end,
    )
    sh_flex_vel = _angular_velocity_deg_s(sh_flex, fs)
    peak_shoulder_flex_vel = float(np.nanmax(sh_flex_vel)) if len(sh_flex_vel) else float("nan")
    mean_shoulder_flex_vel = float(np.nanmean(sh_flex_vel)) if len(sh_flex_vel) else float("nan")
    sh_finite = sh_flex[np.isfinite(sh_flex)]
    sh_flex_min = float(np.nanmin(sh_finite)) if len(sh_finite) else float("nan")
    sh_flex_max = float(np.nanmax(sh_finite)) if len(sh_finite) else float("nan")
    sh_flex_rom = float(sh_flex_max - sh_flex_min) if len(sh_finite) else float("nan")
    sh_flex_mean = float(np.nanmean(sh_finite)) if len(sh_finite) else float("nan")

    pause_frac = pause_time_sec / movement_duration_s if movement_duration_s > 0.1 else float("nan")
    flex_q = _joint_quality_index(
        float(sh_flex_rom) if np.isfinite(sh_flex_rom) else float("nan"),
        float(peak_shoulder_flex_vel) if np.isfinite(peak_shoulder_flex_vel) else float("nan"),
        float(pause_frac) if np.isfinite(pause_frac) else float("nan"),
        None,
    )

    sh_abd = np.array([], dtype=float)
    shoulder_abduction_reliable = False
    shoulder_abduction_angle_space = "2d_image"
    if (
        hand_world is not None
        and arm_world is not None
        and "left_shoulder_x" in hand_world
    ):
        sh_abd_w = _shoulder_abduction_world_series(
            affected_side, hand_world, arm_world, start, end,
        )
        if len(sh_abd_w) >= max(8, int(0.1 * (end - start))):
            sh_abd = sh_abd_w
            shoulder_abduction_reliable = True
            shoulder_abduction_angle_space = "world_meters"
    if len(sh_abd) == 0 and opp_shoulder_x is not None and opp_shoulder_y is not None and len(opp_shoulder_x) == n:
        sh_abd = _shoulder_abduction_series(
            opp_shoulder_x, opp_shoulder_y, shoulder_x, shoulder_y, elbow_x, elbow_y, start, end,
        )
        sw_span = float(np.nanmedian(np.hypot(opp_shoulder_x - shoulder_x, opp_shoulder_y - shoulder_y)))
        ref_sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else sw_span
        shoulder_abduction_reliable = bool(np.isfinite(ref_sw) and ref_sw > 0.05 * max(n, 1))

    forearm_rot = np.array([], dtype=float)
    forearm_rotation_reliable = False
    forearm_rotation_angle_space = "2d_proxy"
    if hand_world is not None and arm_world is not None:
        try:
            forearm_rot = _forearm_rotation_series(
                arm_world["elbow_x"], arm_world["elbow_y"], arm_world["elbow_z"],
                arm_world["wrist_x"], arm_world["wrist_y"], arm_world["wrist_z"],
                hand_world["index_x"], hand_world["index_y"], hand_world["index_z"],
                hand_world["pinky_x"], hand_world["pinky_y"], hand_world["pinky_z"],
                start, end,
            )
            if len(forearm_rot) >= max(8, int(0.1 * (end - start))):
                forearm_rotation_reliable = True
                forearm_rotation_angle_space = "world_meters"
        except (KeyError, TypeError):
            forearm_rot = np.array([], dtype=float)
    if len(forearm_rot) == 0 and hand3d is not None and arm3d is not None:
        try:
            forearm_rot = _forearm_rotation_series(
                arm3d["elbow_x"], arm3d["elbow_y"], arm3d["elbow_z"],
                arm3d["wrist_x"], arm3d["wrist_y"], arm3d["wrist_z"],
                hand3d["index_x"], hand3d["index_y"], hand3d["index_z"],
                hand3d["pinky_x"], hand3d["pinky_y"], hand3d["pinky_z"],
                start, end,
            )
            forearm_rotation_reliable = len(forearm_rot) >= max(8, int(0.1 * (end - start)))
        except (KeyError, TypeError):
            forearm_rot = np.array([], dtype=float)
    elif (
        index_x is not None and pinky_x is not None
        and index_y is not None and pinky_y is not None
        and len(index_x) == n and len(pinky_x) == n
    ):
        forearm_rot = _forearm_rotation_series_2d(
            index_x, index_y, pinky_x, pinky_y, start, end,
        )
        forearm_rotation_reliable = len(forearm_rot) >= max(8, int(0.1 * (end - start)))

    fine_block: Dict[str, Any] = {}
    fm_ix, fm_iy, fm_tx, fm_ty, fm_px, fm_py, hl_fine = resolve_fine_motor_hand_coords(
        hand3d, index_x, index_y, thumb_x, thumb_y, pinky_x, pinky_y, start, end,
    )
    if fm_ix is not None and fm_iy is not None and len(fm_ix) == n:
        fine_block = _fine_motor_metrics(
            fm_ix, fm_iy, fs, start, end,
            thumb_x=fm_tx, thumb_y=fm_ty, shoulder_width=shoulder_width,
        )
        if hl_fine:
            fine_block["hand_landmarker_fine_motor"] = True

    sh_palm = _shoulder_elevation_palm_ratio(
        shoulder_y, palm_y, shoulder_width, start, end,
    )

    comp_idx = _compensation_index(trunk_ratio, sh_palm, trunk_cheat_ratio)
    quality_idx = _movement_quality_index(
        straightness, nvp, movement_duration_s, trunk_ratio, sh_palm, pause_time_sec,
    )

    profile: Dict[str, Any] = {
        "task_pattern": task_pattern,
        "movement_segments_detected": len(segments),
        "analysis_window_start_frame": start,
        "analysis_window_end_frame": end,
        "movement_time_sec": round(movement_duration_s, 3),
        "nvp": int(nvp),
        "straightness": round(straightness, 4) if np.isfinite(straightness) else None,
        "pause_time_sec": round(pause_time_sec, 3),
        "number_of_stops": int(number_of_stops),
        "peak_hand_speed_px_s": round(peak_velocity, 2) if np.isfinite(peak_velocity) else None,
        "mean_hand_speed_px_s": round(mean_velocity, 2) if np.isfinite(mean_velocity) else None,
        "elbow_angle_min_deg": round(elbow_min, 1) if np.isfinite(elbow_min) else None,
        "elbow_angle_max_deg": round(elbow_max, 1) if np.isfinite(elbow_max) else None,
        "elbow_rom_deg": round(elbow_rom, 1) if np.isfinite(elbow_rom) else None,
        "elbow_angle_mean_deg": round(elbow_mean, 1) if np.isfinite(elbow_mean) else None,
        "peak_elbow_ang_vel_deg_s": round(peak_elbow_ang_vel, 1) if np.isfinite(peak_elbow_ang_vel) else None,
        "mean_elbow_ang_vel_deg_s": round(mean_elbow_ang_vel, 1) if np.isfinite(mean_elbow_ang_vel) else None,
        "shoulder_flexion_min_deg": round(sh_flex_min, 1) if np.isfinite(sh_flex_min) else None,
        "shoulder_flexion_max_deg": round(sh_flex_max, 1) if np.isfinite(sh_flex_max) else None,
        "shoulder_flexion_rom_deg": round(sh_flex_rom, 1) if np.isfinite(sh_flex_rom) else None,
        "shoulder_flexion_mean_deg": round(sh_flex_mean, 1) if np.isfinite(sh_flex_mean) else None,
        "peak_shoulder_flexion_vel_deg_s": round(peak_shoulder_flex_vel, 1) if np.isfinite(peak_shoulder_flex_vel) else None,
        "mean_shoulder_flexion_vel_deg_s": round(mean_shoulder_flex_vel, 1) if np.isfinite(mean_shoulder_flex_vel) else None,
        "shoulder_flexion_quality_index": round(flex_q, 1) if flex_q is not None else None,
        "shoulder_elevation_palm_ratio": round(sh_palm, 4) if np.isfinite(sh_palm) else None,
        "compensation_index": round(comp_idx, 3) if comp_idx is not None else None,
        "movement_quality_index": round(quality_idx, 1) if quality_idx is not None else None,
        "peak_velocity_frame_indices": [start + p for p in peak_frames[:20]],
    }
    profile.update(_summarize_angle_block("shoulder_abduction", sh_abd, fs))
    profile.update(_summarize_angle_block("forearm_rotation", forearm_rot, fs))
    profile["forearm_pronation_supination_rom_deg"] = profile.pop("forearm_rotation_rom_deg", None)
    profile["forearm_rotation_mean_deg"] = profile.pop("forearm_rotation_mean_deg", None)
    profile["peak_forearm_rotation_vel_deg_s"] = profile.pop("peak_forearm_rotation_vel_deg_s", None)
    profile["mean_forearm_rotation_vel_deg_s"] = profile.pop("mean_forearm_rotation_vel_deg_s", None)
    profile["shoulder_abduction_reliable"] = shoulder_abduction_reliable
    profile["shoulder_abduction_angle_space"] = shoulder_abduction_angle_space
    profile["forearm_rotation_reliable"] = forearm_rotation_reliable
    profile["forearm_rotation_angle_space"] = forearm_rotation_angle_space
    profile.update(fine_block)
    profile.update(_hand_landmarker_pinch_metrics(hand3d, fs, start, end, shoulder_width))
    profile.update(
        _finger_flex_ext_metrics(
            hand3d, wrist_x, wrist_y, index_x, index_y, pinky_x, pinky_y, thumb_x, thumb_y,
            fs, start, end, shoulder_width,
        )
    )
    profile.update(
        _head_forward_flexion_metrics(
            nose_x, nose_y, shoulder_x, shoulder_y,
            opp_shoulder_x, opp_shoulder_y, trunk_x, trunk_y,
            palm_x, palm_y, start, end, shoulder_width,
        )
    )
    profile.update(
        _tremor_metrics_block(
            fs=fs,
            start=start,
            end=end,
            palm_x=palm_x,
            palm_y=palm_y,
            elbow_angles=angles,
            shoulder_flex_angles=sh_flex,
            index_x=fm_ix,
            index_y=fm_iy,
            shoulder_width=shoulder_width,
            pinch_distance=np.hypot(
                fm_ix - fm_tx,
                fm_iy - fm_ty,
            )
            if hl_fine and fm_tx is not None and fm_ty is not None and fm_ix is not None
            else (
                np.hypot(
                    hand3d["index_tip_x"] - hand3d["thumb_tip_x"],
                    hand3d["index_tip_y"] - hand3d["thumb_tip_y"],
                )
                if hand3d and "index_tip_x" in hand3d and "thumb_tip_x" in hand3d
                else None
            ),
        )
    )
    if profile.get("pinch_tremor_8_12hz_power") is not None and profile.get("tremor_8_12hz_power") is None:
        profile["tremor_8_12hz_power"] = profile["pinch_tremor_8_12hz_power"]

    sparc_sh = _sparc_on_angle_series(sh_flex[np.isfinite(sh_flex)], fs) if np.any(np.isfinite(sh_flex)) else float("nan")
    sparc_abd = _sparc_on_angle_series(sh_abd[np.isfinite(sh_abd)], fs) if len(sh_abd) and np.any(np.isfinite(sh_abd)) else float("nan")
    sparc_fr = _sparc_on_angle_series(forearm_rot[np.isfinite(forearm_rot)], fs) if len(forearm_rot) and np.any(np.isfinite(forearm_rot)) else float("nan")
    if np.isfinite(sparc_sh):
        profile["sparc_shoulder_flexion"] = round(sparc_sh, 3)
    if np.isfinite(sparc_abd):
        profile["sparc_shoulder_abduction"] = round(sparc_abd, 3)
    if np.isfinite(sparc_fr):
        profile["sparc_forearm_rotation"] = round(sparc_fr, 3)

    abd_mean = profile.get("shoulder_abduction_mean_deg")
    abd_rom = profile.get("shoulder_abduction_rom_deg")
    abd_trunk_comp = _abduction_trunk_compensation_index(
        float(abd_rom) if abd_rom is not None else float("nan"),
        float(trunk_ratio) if np.isfinite(trunk_ratio) else float("nan"),
        float(abd_mean) if abd_mean is not None else float("nan"),
    )
    if abd_trunk_comp is not None:
        profile["shoulder_abduction_trunk_compensation_index"] = abd_trunk_comp

    if clinical_task:
        profile["clinical_task"] = clinical_task

    sh_abd_rom = profile.get("shoulder_abduction_rom_deg")
    sh_abd_peak_v = profile.get("peak_shoulder_abduction_vel_deg_s")
    abd_q = _joint_quality_index(
        float(sh_abd_rom) if sh_abd_rom is not None else float("nan"),
        float(sh_abd_peak_v) if sh_abd_peak_v is not None else float("nan"),
        float(pause_frac) if np.isfinite(pause_frac) else float("nan"),
        comp_idx,
    )
    if abd_q is not None:
        profile["shoulder_abduction_quality_index"] = round(abd_q, 1)

    fr_rom = profile.get("forearm_pronation_supination_rom_deg")
    fr_peak_v = profile.get("peak_forearm_rotation_vel_deg_s")
    rot_q = _joint_quality_index(
        float(fr_rom) if fr_rom is not None else float("nan"),
        float(fr_peak_v) if fr_peak_v is not None else float("nan"),
        float(pause_frac) if np.isfinite(pause_frac) else float("nan"),
        comp_idx,
    )
    if rot_q is not None:
        profile["forearm_rotation_quality_index"] = round(rot_q, 1)

    if elbow_reach:
        profile["elbow_extension_at_peak_reach_deg"] = round(
            float(elbow_reach.get("primary") or elbow_reach.get("max") or float("nan")), 1,
        )
        profile["elbow_angle_method"] = elbow_reach.get("method")
        profile["elbow_angle_reliable"] = bool(elbow_reach.get("reliable"))

    return profile


def find_peak_rom_window(
    signal: np.ndarray,
    fs: float,
    min_duration_s: float = 0.25,
) -> Tuple[int, int, float]:
    """Find contiguous window with maximum range-of-motion on a scalar kinematic trace."""
    y = np.asarray(signal, dtype=float)
    n = len(y)
    min_f = max(4, int(min_duration_s * fs))
    if n <= min_f:
        return 0, max(0, n - 1), float("nan")
    best_s, best_e, best_rom = 0, min_f - 1, -1.0
    for s in range(0, n - min_f + 1):
        for e in range(s + min_f - 1, min(n, s + int(4.0 * fs))):
            seg = y[s : e + 1]
            if not np.any(np.isfinite(seg)):
                continue
            rom = float(np.nanmax(seg) - np.nanmin(seg))
            if rom > best_rom:
                best_rom = rom
                best_s, best_e = s, e
    return int(best_s), int(best_e), float(best_rom)


def merge_profile_into_results(results: Dict[str, Any], profile: Dict[str, Any]) -> None:
    """Attach profile and fill study-aligned keys when missing."""
    results["movement_profile"] = profile
    mapping = {
        "nvp": "nvp",
        "straightness": "straightness",
        "pause_time_sec": "pause_time_sec",
        "number_of_stops": "number_of_stops",
        "elbow_angle_mean_deg": "elbow_angle_mean_deg",
        "peak_elbow_ang_vel_deg_s": "peak_elbow_ang_vel_deg_s",
        "shoulder_flexion_mean_deg": "shoulder_flexion_mean_deg",
        "peak_shoulder_flexion_vel_deg_s": "peak_shoulder_flexion_vel_deg_s",
        "shoulder_elevation_palm_ratio": "shoulder_elevation_palm_ratio",
        "movement_quality_index": "movement_quality_index",
        "compensation_index": "compensation_index",
        "task_pattern": "task_pattern",
        "sparc_shoulder_flexion": "sparc_shoulder_flexion",
        "sparc_shoulder_abduction": "sparc_shoulder_abduction",
        "sparc_forearm_rotation": "sparc_forearm_rotation",
        "shoulder_abduction_trunk_compensation_index": "shoulder_abduction_trunk_compensation_index",
        "pinch_grasp_quality_index": "pinch_grasp_quality_index",
        "tremor_8_12hz_power": "tremor_8_12hz_power",
        "tremor_peak_freq_hz": "tremor_peak_freq_hz",
        "tremor_index": "tremor_index",
        "hand_speed_tremor_8_12hz_power": "hand_speed_tremor_8_12hz_power",
        "index_tremor_8_12hz_power": "index_tremor_8_12hz_power",
        "index_tremor_peak_freq_hz": "index_tremor_peak_freq_hz",
        "elbow_tremor_8_12hz_power": "elbow_tremor_8_12hz_power",
        "shoulder_flexion_tremor_8_12hz_power": "shoulder_flexion_tremor_8_12hz_power",
    }
    for src, dst in mapping.items():
        val = profile.get(src)
        if val is not None and results.get(dst) is None:
            results[dst] = val
    if profile.get("elbow_angle_max_deg") is not None:
        results.setdefault("elbow_angle_max_deg", profile["elbow_angle_max_deg"])
    if profile.get("elbow_rom_deg") is not None:
        results.setdefault("elbow_angle_range_deg", profile["elbow_rom_deg"])
    for k in (
        "shoulder_abduction_mean_deg",
        "shoulder_abduction_rom_deg",
        "peak_shoulder_abduction_vel_deg_s",
        "shoulder_abduction_quality_index",
        "forearm_pronation_supination_rom_deg",
        "forearm_rotation_mean_deg",
        "peak_forearm_rotation_vel_deg_s",
        "forearm_rotation_quality_index",
        "fine_motor_quality_index",
        "fine_motor_index_nvp",
        "fine_motor_micro_stops",
        "pinch_aperture_rom_sw",
        "pinch_aperture_hl_rom_sw",
        "pinch_tremor_8_12hz_power",
        "finger_flex_ext_rom_sw",
        "finger_flex_ext_max_rom_sw",
        "finger_flex_ext_quality_index",
        "head_forward_displacement_sw",
        "head_flexion_rom_deg",
        "head_flexion_increase_deg",
        "head_forward_flexion_compensation_index",
    ):
        v = profile.get(k)
        if v is not None:
            results.setdefault(k, v)
