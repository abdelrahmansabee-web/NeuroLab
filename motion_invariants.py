# -*- coding: utf-8 -*-
"""
View-invariant motion helpers — PCA / 3D MediaPipe / body-normalized kinematics.

Camera mount angle is NOT inferred from a single shoulder ratio. We measure
*body orientation in the frame* (soft metadata) and compute reach metrics in a
shoulder-centered, shoulder-width-normalized frame with optional 3D depth (Z).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.signal import savgol_filter


def _col_norm(df, name: str, axis: str) -> np.ndarray:
    key = f"{name}_{axis}"
    if key not in df.columns:
        raise KeyError(key)
    return df[key].astype(float).values


def shoulder_layout_ratio(raw, frame_width: int, frame_height: int) -> float:
    """Horizontal vs vertical shoulder spread in image (continuous, not camera angle)."""
    try:
        ls_x = np.nanmedian(_col_norm(raw, "LEFT_SHOULDER", "X") * frame_width)
        rs_x = np.nanmedian(_col_norm(raw, "RIGHT_SHOULDER", "X") * frame_width)
        ls_y = np.nanmedian(_col_norm(raw, "LEFT_SHOULDER", "Y") * frame_height)
        rs_y = np.nanmedian(_col_norm(raw, "RIGHT_SHOULDER", "Y") * frame_height)
    except KeyError:
        return float("nan")
    spread_x = abs(float(rs_x - ls_x))
    spread_y = abs(float(rs_y - ls_y))
    if spread_x < 1e-6 and spread_y < 1e-6:
        return float("nan")
    return spread_x / max(spread_y, 1e-6)


def detect_body_orientation(
    raw,
    frame_width: int,
    frame_height: int,
) -> Dict[str, object]:
    """
    Soft body-orientation label from shoulder geometry over time.
    Same camera can yield different labels if the patient rotates — metrics
    should NOT depend on this label (see body-frame SPARC / 3D elbow).
    """
    try:
        ls_x = _col_norm(raw, "LEFT_SHOULDER", "X") * frame_width
        rs_x = _col_norm(raw, "RIGHT_SHOULDER", "X") * frame_width
        ls_y = _col_norm(raw, "LEFT_SHOULDER", "Y") * frame_height
        rs_y = _col_norm(raw, "RIGHT_SHOULDER", "Y") * frame_height
    except KeyError:
        return {"label": "unknown", "ratio": None, "confidence": 0.0, "stable": False}

    ratios = np.abs(rs_x - ls_x) / np.maximum(np.abs(rs_y - ls_y), 1e-6)
    ratios = ratios[np.isfinite(ratios)]
    if len(ratios) == 0:
        return {"label": "unknown", "ratio": None, "confidence": 0.0, "stable": False}

    med = float(np.nanmedian(ratios))
    iqr = float(np.nanpercentile(ratios, 75) - np.nanpercentile(ratios, 25))
    stable = iqr < 0.8 * max(med, 1.0)

    # Wide bands → prefer oblique; avoids false frontal/side when pose shifts.
    if med >= 2.8:
        label = "frontal"
    elif med <= 0.55:
        label = "side"
    else:
        label = "oblique"

    confidence = float(np.clip(1.0 - iqr / max(med, 1.0), 0.0, 1.0))
    if not stable:
        label = "oblique"
        confidence *= 0.6

    return {
        "label": label,
        "ratio": round(med, 3),
        "confidence": round(confidence, 3),
        "stable": stable,
    }


def _bridge_gaps(mask: np.ndarray, max_gap: int = 6) -> np.ndarray:
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


def _list_segments(
    palm_speed: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    velocity_threshold: float,
    max_gap_frames: int = 6,
    min_segment_frames: int = 10,
) -> List[Dict[str, float]]:
    if len(palm_speed) == 0:
        return []
    peak = float(np.max(palm_speed))
    thr = max(float(velocity_threshold), 0.05 * peak)
    mask = _bridge_gaps(palm_speed > thr, max_gap_frames)

    segs: List[Dict[str, float]] = []
    i, n = 0, len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        s, e = i, j - 1
        seg_len = e - s + 1
        if seg_len >= min_segment_frames:
            disp = float(np.hypot(palm_x[e] - palm_x[s], palm_y[e] - palm_y[s]))
            pk = float(np.max(palm_speed[s : e + 1]))
            path = float(np.sum(np.hypot(np.diff(palm_x[s : e + 1]), np.diff(palm_y[s : e + 1]))))
            segs.append(
                {
                    "start": float(s),
                    "end": float(e),
                    "len": float(seg_len),
                    "peak": pk,
                    "disp": disp,
                    "path": path,
                    "dur": seg_len / fs,
                }
            )
        i = j
    return segs


def primary_reach_window(
    palm_speed: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    velocity_threshold: float = 5.0,
    shoulder_width: Optional[float] = None,
    max_gap_frames: int = 6,
    min_segment_frames: int = 10,
    coords_in_sw: bool = False,
    min_path_sw: float = 0.15,
    min_amp_sw: float = 0.15,
) -> Tuple[int, int]:
    """
    First clinically valid reach bout (chronological), not a later wipe burst.

    Later wipe/return bursts can exceed the first reach in peak speed; comparing
    each segment to a global peak therefore skips the primary bout (Kurusal pre/post).
    """
    segs = _list_segments(
        palm_speed, palm_x, palm_y, fs, velocity_threshold, max_gap_frames, min_segment_frames
    )
    if not segs:
        return 0, max(0, len(palm_speed) - 1)

    segs = sorted(segs, key=lambda s: s["start"])
    sw_px = float(shoulder_width) if shoulder_width and shoulder_width > 0 else None
    min_amp_sw = float(min_amp_sw)
    min_dur_s = 0.35

    if coords_in_sw and sw_px:
        min_path = float(min_path_sw)
        min_disp = min_amp_sw
    else:
        min_path = max(8.0, 0.08 * sw_px) if sw_px else 8.0
        min_disp = max(6.0, 0.06 * sw_px) if sw_px else 6.0

    def _norm(s: Dict[str, float]) -> Dict[str, float]:
        if sw_px:
            return {**s, "disp_n": s["disp"] / sw_px, "path_n": s["path"] / sw_px}
        return {**s, "disp_n": s["disp"], "path_n": s["path"]}

    normed = [_norm(s) for s in segs]

    # Chronological first-fit: earliest bout with adequate amp, path, duration.
    for s in normed:
        if s["dur"] >= min_dur_s and s["path_n"] >= min_path and s["disp_n"] >= min_disp:
            return int(s["start"]), int(s["end"])

    for s in normed:
        if s["dur"] >= min_dur_s and s["disp_n"] >= max(min_disp * 0.5, 0.04):
            return int(s["start"]), int(s["end"])

    for s in normed:
        if s["dur"] >= min_dur_s:
            return int(s["start"]), int(s["end"])

    best = min(normed, key=lambda x: (x["start"], -x["disp_n"]))
    return int(best["start"]), int(best["end"])


def body_frame_palm(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    shoulder_width: Optional[float],
    palm_z: Optional[np.ndarray] = None,
    shoulder_z: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray], float]:
    """Shoulder-centered coordinates normalized by shoulder width (view-stable scale)."""
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        np.nanmedian(np.hypot(np.diff(shoulder_x[: min(30, len(shoulder_x))]), np.diff(shoulder_y[: min(30, len(shoulder_y))])) * 8)
    )
    if not np.isfinite(sw) or sw < 1e-6:
        sw = max(float(np.ptp(palm_x)), float(np.ptp(palm_y)), 50.0)

    rest = 0
    bx = (palm_x - shoulder_x[rest]) / sw
    by = (palm_y - shoulder_y[rest]) / sw
    bz = None
    if palm_z is not None and shoulder_z is not None:
        z_scale = sw  # MediaPipe Z shares x-normalized scale
        bz = (palm_z - shoulder_z[rest]) / z_scale
    return bx, by, bz, sw


def reach_speed_series(
    bx: np.ndarray,
    by: np.ndarray,
    bz: Optional[np.ndarray],
    fs: float,
) -> np.ndarray:
    if bz is not None and len(bz) == len(bx):
        vx = np.gradient(bx) * fs
        vy = np.gradient(by) * fs
        vz = np.gradient(bz) * fs
        return np.sqrt(vx**2 + vy**2 + vz**2)
    vx = np.gradient(bx) * fs
    vy = np.gradient(by) * fs
    return np.sqrt(vx**2 + vy**2)


def palm_image_speed(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
) -> np.ndarray:
    """Tangential palm speed in image plane (px/s). Used for reach window detection."""
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    return np.sqrt(vx**2 + vy**2)


def sparc_speed_profile(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    shoulder_width: Optional[float],
    fs: float,
    move_start: int,
    move_end: int,
    palm_z: Optional[np.ndarray] = None,
    shoulder_z: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, str]:
    """
    Speed series for SPARC. Body-frame is preferred; falls back to image plane when
    shoulder/trunk co-movement cancels body-frame speed (common in frontal video).
    """
    bx, by, bz, sw = body_frame_palm(
        palm_x, palm_y, shoulder_x, shoulder_y, shoulder_width, palm_z, shoulder_z
    )
    bf = reach_speed_series(bx, by, bz, fs)
    pix = palm_image_speed(palm_x, palm_y, fs)
    ms, me = int(move_start), int(move_end)
    ms = max(0, ms)
    me = min(len(pix) - 1, me)
    if me <= ms:
        return bf, "body_frame"
    bf_peak = float(np.max(bf[ms : me + 1]))
    pix_peak = float(np.max(pix[ms : me + 1]))
    pix_peak_sw = pix_peak / sw if sw and sw > 0 else pix_peak
    if pix_peak_sw > 1e-6 and bf_peak < 0.20 * pix_peak_sw:
        return pix, "image_plane"
    return bf, "body_frame"


def smooth_series(y: np.ndarray, fs: float, window_s: float = 0.11) -> np.ndarray:
    n = len(y)
    if n < 7:
        return y
    win = int(max(5, round(window_s * fs)))
    if win % 2 == 0:
        win += 1
    win = min(win, n if n % 2 == 1 else n - 1)
    if win < 5:
        return y
    try:
        return savgol_filter(y, window_length=win, polyorder=2, mode="interp")
    except Exception:
        return y


def load_arm_3d(raw, side: str, frame_width: int, frame_height: int) -> Optional[Dict[str, np.ndarray]]:
    """Load shoulder/elbow/wrist/palm in pseudo-3D (x,y pixels; z scaled by frame width)."""
    p = side.upper()
    try:
        wx = _col_norm(raw, f"{p}_WRIST", "X") * frame_width
        wy = _col_norm(raw, f"{p}_WRIST", "Y") * frame_height
        wz = _col_norm(raw, f"{p}_WRIST", "Z") * frame_width
        ix = _col_norm(raw, f"{p}_INDEX", "X") * frame_width
        iy = _col_norm(raw, f"{p}_INDEX", "Y") * frame_height
        iz = _col_norm(raw, f"{p}_INDEX", "Z") * frame_width
        sx = _col_norm(raw, f"{p}_SHOULDER", "X") * frame_width
        sy = _col_norm(raw, f"{p}_SHOULDER", "Y") * frame_height
        sz = _col_norm(raw, f"{p}_SHOULDER", "Z") * frame_width
        ex = _col_norm(raw, f"{p}_ELBOW", "X") * frame_width
        ey = _col_norm(raw, f"{p}_ELBOW", "Y") * frame_height
        ez = _col_norm(raw, f"{p}_ELBOW", "Z") * frame_width
    except KeyError:
        return None

    return {
        "palm_x": (wx + ix) / 2.0,
        "palm_y": (wy + iy) / 2.0,
        "palm_z": (wz + iz) / 2.0,
        "wrist_x": wx,
        "wrist_y": wy,
        "wrist_z": wz,
        "shoulder_x": sx,
        "shoulder_y": sy,
        "shoulder_z": sz,
        "elbow_x": ex,
        "elbow_y": ey,
        "elbow_z": ez,
    }


def _col_world(df, name: str, axis: str) -> np.ndarray:
    key = f"{name}_{axis}"
    if key not in df.columns:
        raise KeyError(key)
    return df[key].astype(float).values


def load_arm_world(raw: pd.DataFrame, side: str) -> Optional[Dict[str, np.ndarray]]:
    """MediaPipe pose_world_landmarks (meters, hip-centered) for one arm."""
    p = side.upper()
    try:
        return {
            "shoulder_x": _col_world(raw, f"{p}_SHOULDER", "WX"),
            "shoulder_y": _col_world(raw, f"{p}_SHOULDER", "WY"),
            "shoulder_z": _col_world(raw, f"{p}_SHOULDER", "WZ"),
            "elbow_x": _col_world(raw, f"{p}_ELBOW", "WX"),
            "elbow_y": _col_world(raw, f"{p}_ELBOW", "WY"),
            "elbow_z": _col_world(raw, f"{p}_ELBOW", "WZ"),
            "wrist_x": _col_world(raw, f"{p}_WRIST", "WX"),
            "wrist_y": _col_world(raw, f"{p}_WRIST", "WY"),
            "wrist_z": _col_world(raw, f"{p}_WRIST", "WZ"),
        }
    except KeyError:
        return None


def compute_elbow_world(
    raw: pd.DataFrame,
    side: str,
    start: int,
    end: int,
) -> Optional[Dict[str, float]]:
    """
    Elbow interior angle (shoulder–elbow–wrist) in MediaPipe world space (meters).
    Comparable across left/right and camera views — use for healthy-side baseline.
    """
    arm = load_arm_world(raw, side)
    if arm is None or end <= start:
        return None

    angles = elbow_angles_3d(
        (arm["shoulder_x"], arm["shoulder_y"], arm["shoulder_z"]),
        (arm["elbow_x"], arm["elbow_y"], arm["elbow_z"]),
        (arm["wrist_x"], arm["wrist_y"], arm["wrist_z"]),
        start,
        end,
    )
    if len(angles) < 8:
        return None

    sx, sy, sz = arm["shoulder_x"], arm["shoulder_y"], arm["shoulder_z"]
    ex, ey, ez = arm["elbow_x"], arm["elbow_y"], arm["elbow_z"]
    wx, wy, wz = arm["wrist_x"], arm["wrist_y"], arm["wrist_z"]
    ua = np.linalg.norm(
        np.column_stack([
            ex[start : end + 1] - sx[start : end + 1],
            ey[start : end + 1] - sy[start : end + 1],
            ez[start : end + 1] - sz[start : end + 1],
        ]),
        axis=1,
    )
    fa = np.linalg.norm(
        np.column_stack([
            wx[start : end + 1] - ex[start : end + 1],
            wy[start : end + 1] - ey[start : end + 1],
            wz[start : end + 1] - ez[start : end + 1],
        ]),
        axis=1,
    )
    reliable = elbow_angle_reliable(angles, ua, fa, coord_space="world_m")
    if not reliable:
        return {
            "mean": float(np.mean(angles)),
            "min": float(np.min(angles)),
            "max": float(np.max(angles)),
            "reliable": False,
        }
    return {
        "mean": float(np.mean(angles)),
        "min": float(np.min(angles)),
        "max": float(np.max(angles)),
        "reliable": True,
    }


def elbow_angles_3d(
    shoulder: Tuple[np.ndarray, np.ndarray, np.ndarray],
    elbow: Tuple[np.ndarray, np.ndarray, np.ndarray],
    wrist: Tuple[np.ndarray, np.ndarray, np.ndarray],
    start: int,
    end: int,
) -> np.ndarray:
    sx, sy, sz = shoulder
    ex, ey, ez = elbow
    wx, wy, wz = wrist
    angles = []
    for i in range(start, end + 1):
        # Both vectors emanate from the elbow vertex (shoulder→elbow, wrist→elbow).
        v1 = np.array([sx[i] - ex[i], sy[i] - ey[i], sz[i] - ez[i]], dtype=float)
        v2 = np.array([wx[i] - ex[i], wy[i] - ey[i], wz[i] - ez[i]], dtype=float)
        m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if m1 < 1e-6 or m2 < 1e-6:
            continue
        cos_a = np.clip(float(np.dot(v1, v2) / (m1 * m2)), -1.0, 1.0)
        angles.append(float(np.arccos(cos_a) * 180.0 / np.pi))
    return np.array(angles, dtype=float)


def elbow_angle_reliable(
    angles: np.ndarray,
    upper_arm_len: np.ndarray,
    forearm_len: np.ndarray,
    used_3d: bool = False,
    coord_space: str = "2d_px",
) -> bool:
    if len(angles) < 8:
        return False
    ua_mean = float(np.mean(upper_arm_len))
    fa_mean = float(np.mean(forearm_len))
    ua_cv = float(np.std(upper_arm_len) / max(ua_mean, 1e-6))
    fa_cv = float(np.std(forearm_len) / max(fa_mean, 1e-6))
    ang_range = float(np.nanmax(angles) - np.nanmin(angles)) if len(angles) else 0.0

    if coord_space == "world_m":
        if ua_mean < 0.07 or fa_mean < 0.05:
            return False
        if ua_cv > 0.18 or fa_cv > 0.18:
            return False
        return True

    if coord_space == "mediapipe_3d":
        if ua_mean < 35 or fa_mean < 35:
            return False
        if ang_range >= 8.0:
            return True
        if ua_cv <= 0.40 and fa_cv <= 0.40:
            return True
        return False

    if coord_space == "2d_px":
        if ua_mean < 35 or fa_mean < 35:
            return False
        # Foreshortening during reach inflates 2D segment-length CV; accept visible elbow excursion.
        if ang_range >= 12.0:
            return True
        if ua_cv > 0.22 or fa_cv > 0.22:
            return False
        return True

    if ua_cv > 0.22 or fa_cv > 0.22:
        return False
    if ua_mean < 35 or fa_mean < 35:
        return False
    if used_3d:
        return ang_range >= 4.0
    return True


def compute_elbow_arm3d(
    arm: Dict[str, np.ndarray],
    start: int,
    end: int,
    *,
    coord_space: str = "mediapipe_3d",
) -> Optional[Dict[str, float]]:
    """Elbow interior angle from pseudo-3D MediaPipe landmarks (X,Y pixels + Z scaled)."""
    if end <= start:
        return None
    angles = elbow_angles_3d(
        (arm["shoulder_x"], arm["shoulder_y"], arm["shoulder_z"]),
        (arm["elbow_x"], arm["elbow_y"], arm["elbow_z"]),
        (arm["wrist_x"], arm["wrist_y"], arm["wrist_z"]),
        start,
        end,
    )
    if len(angles) < 8:
        return None

    sx, sy, sz = arm["shoulder_x"], arm["shoulder_y"], arm["shoulder_z"]
    ex, ey, ez = arm["elbow_x"], arm["elbow_y"], arm["elbow_z"]
    wx, wy, wz = arm["wrist_x"], arm["wrist_y"], arm["wrist_z"]
    ua = np.linalg.norm(
        np.column_stack([
            ex[start : end + 1] - sx[start : end + 1],
            ey[start : end + 1] - sy[start : end + 1],
            ez[start : end + 1] - sz[start : end + 1],
        ]),
        axis=1,
    )
    fa = np.linalg.norm(
        np.column_stack([
            wx[start : end + 1] - ex[start : end + 1],
            wy[start : end + 1] - ey[start : end + 1],
            wz[start : end + 1] - ez[start : end + 1],
        ]),
        axis=1,
    )
    reliable = elbow_angle_reliable(angles, ua, fa, coord_space=coord_space)
    return {
        "mean": float(np.mean(angles)),
        "min": float(np.min(angles)),
        "max": float(np.max(angles)),
        "reliable": bool(reliable),
    }


def elbow_angle_2d_frame(
    shoulder_x: float,
    shoulder_y: float,
    elbow_x: float,
    elbow_y: float,
    wrist_x: float,
    wrist_y: float,
) -> float:
    """Interior angle at elbow (shoulder–elbow–wrist) in the image plane (Track-UL / Kinovea)."""
    v1 = np.array([shoulder_x - elbow_x, shoulder_y - elbow_y], dtype=float)
    v2 = np.array([wrist_x - elbow_x, wrist_y - elbow_y], dtype=float)
    m1, m2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if m1 < 1e-6 or m2 < 1e-6:
        return float("nan")
    cos_a = np.clip(float(np.dot(v1, v2) / (m1 * m2)), -1.0, 1.0)
    return float(np.arccos(cos_a) * 180.0 / np.pi)


def compute_elbow_reach_2d(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    start: int,
    end: int,
) -> Optional[Dict[str, float]]:
    """
    Peak elbow extension during outbound reach (2D image plane).

    Aligns with stroke video kinematics literature:
    - Track-UL / Kinovea: 2D shoulder–elbow–wrist dot product (JMIR Rehab 2026)
    - Max interior angle during forward reach phase (reach-and-grasp kinematics)
    - IoEE at peak shoulder–wrist frame as cross-arm robustness check (Exp Brain Res 2025)
    """
    if end <= start:
        return None

    angles = []
    ua = []
    fa = []
    sw_dist = []
    for i in range(start, end + 1):
        ang = elbow_angle_2d_frame(
            shoulder_x[i], shoulder_y[i],
            elbow_x[i], elbow_y[i],
            wrist_x[i], wrist_y[i],
        )
        if not np.isfinite(ang):
            continue
        angles.append(ang)
        ua.append(float(np.hypot(elbow_x[i] - shoulder_x[i], elbow_y[i] - shoulder_y[i])))
        fa.append(float(np.hypot(wrist_x[i] - elbow_x[i], wrist_y[i] - elbow_y[i])))
        sw_dist.append(float(np.hypot(wrist_x[i] - shoulder_x[i], wrist_y[i] - shoulder_y[i])))

    if len(angles) < 8:
        return None

    ang_arr = np.array(angles, dtype=float)
    ua_arr = np.array(ua, dtype=float)
    fa_arr = np.array(fa, dtype=float)
    sw_arr = np.array(sw_dist, dtype=float)
    peak_local = int(np.argmax(sw_arr))
    peak_frame = start + peak_local
    ua_pk = ua_arr[peak_local]
    fa_pk = fa_arr[peak_local]
    sw_pk = sw_arr[peak_local]
    ioee = float(sw_pk / max(ua_pk + fa_pk, 1e-6))
    angle_at_peak = float(ang_arr[peak_local])
    reliable = elbow_angle_reliable(ang_arr, ua_arr, fa_arr, coord_space="2d_px")

    return {
        "mean": float(np.mean(ang_arr)),
        "median": float(np.median(ang_arr)),
        "p95": float(np.percentile(ang_arr, 95)),
        "min": float(np.min(ang_arr)),
        "max": float(np.max(ang_arr)),
        "angle_at_peak_reach": angle_at_peak,
        "extension_index": ioee,
        "peak_frame": int(peak_frame),
        "reliable": bool(reliable),
    }


def compute_elbow_reach_metric(
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    start: int,
    end: int,
    *,
    arm3d: Optional[Dict[str, np.ndarray]] = None,
    camera_view: str = "unknown",
) -> Optional[Dict[str, float]]:
    """
    View-adaptive peak elbow extension during outbound reach.

    - Side/stable views: 2D Track-UL angle (robust p95 or peak).
    - Oblique / foreshortened 2D / 2D spike: MediaPipe X,Y,Z at peak reach frame.
    """
    r2 = compute_elbow_reach_2d(
        shoulder_x, shoulder_y, elbow_x, elbow_y, wrist_x, wrist_y, start, end,
    )
    if not r2:
        return None

    peak_frame = int(r2["peak_frame"])
    ioee = float(r2["extension_index"])
    med2 = float(r2["median"])
    max2 = float(r2["max"])
    peak2 = float(r2["angle_at_peak_reach"])
    p952 = float(r2["p95"])

    a3d_peak = float("nan")
    a3d_p95 = float("nan")
    if arm3d is not None:
        ang3 = elbow_angles_3d(
            (arm3d["shoulder_x"], arm3d["shoulder_y"], arm3d["shoulder_z"]),
            (arm3d["elbow_x"], arm3d["elbow_y"], arm3d["elbow_z"]),
            (arm3d["wrist_x"], arm3d["wrist_y"], arm3d["wrist_z"]),
            start,
            end,
        )
        if len(ang3) >= 8:
            local = int(np.clip(peak_frame - start, 0, len(ang3) - 1))
            a3d_peak = float(ang3[local])
            a3d_p95 = float(np.percentile(ang3, 95))

    oblique = camera_view == "oblique"
    spike_2d = (max2 - med2) > 35.0
    foreshort_2d = max2 < 70.0 and ioee >= 0.52
    # 3D only when 2D is clearly wrong (foreshortening / very low oblique angles).
    # Oblique label alone is not enough — Zeinab oblique 2D is valid; Kurusal left arm is not.
    use_3d = (
        arm3d is not None
        and np.isfinite(a3d_peak)
        and (foreshort_2d or (oblique and max2 < 90.0))
    )

    if use_3d:
        primary = a3d_peak
        method = "mediapipe_3d_peak_reach"
    elif spike_2d and max2 > 150.0 and med2 < 120.0 and np.isfinite(a3d_peak):
        primary = a3d_peak
        method = "mediapipe_3d_peak_reach"
    elif spike_2d and ioee >= 0.75:
        # High IoEE + 2D spike → trust peak-reach frame, not window max (Kurusal healthy artifact).
        primary = peak2
        method = "2d_image_plane_peak_reach"
    else:
        primary = float(max(peak2, p952))
        method = "2d_image_plane_outbound"

    return {
        **r2,
        "primary": primary,
        "method": method,
        "angle_3d_at_peak": a3d_peak,
        "angle_3d_p95": a3d_p95,
        "camera_view_used": camera_view,
        "used_3d": bool(use_3d),
    }


def reach_only_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    rest_fraction: float = 0.12,
    disp_on_sw: float = 0.08,
    min_segment_frames: int = 10,
    max_reach_s: float = 2.5,
    post_peak_max_s: float = 0.35,
) -> Tuple[int, int, int]:
    """
    Reach-only: rest → first displacement peak (+ brief deceleration). No return phase.

    Onset/peak search matches table_reach_window; offset stops at peak — does not
    extend through return-to-rest (unlike full reach-return cycle).
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    if n < min_segment_frames:
        return 0, max(0, n - 1), 0

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    spd = np.sqrt(vx**2 + vy**2)

    n_prefix = max(5, int(min(rest_fraction, 0.12) * n))
    x0 = float(np.median(px[:n_prefix]))
    y0 = float(np.median(py[:n_prefix]))
    disp = np.hypot(px - x0, py - y0) / sw
    if float(np.max(disp)) < disp_on_sw:
        return 0, n - 1, 0

    half = max(n_prefix + 1, n // 2)
    spd_ref = float(np.percentile(spd[:half], 85))
    spd_thr = max(spd_ref * 0.20, 0.08 * float(np.max(spd[:half])))
    disp_thr = max(float(disp_on_sw), 0.05)

    onset = n_prefix
    for i in range(n_prefix, n):
        if disp[i] >= disp_thr and spd[i] >= spd_thr:
            onset = i
            break
    else:
        for i in range(n_prefix, n):
            if disp[i] >= disp_thr:
                onset = i
                break
        else:
            return 0, n - 1, 0

    search_end = min(n - 1, onset + int(max_reach_s * fs))
    peak_i = onset
    peak_d = float(disp[onset])
    for i in range(onset + 1, search_end + 1):
        if disp[i] >= peak_d:
            peak_d = float(disp[i])
            peak_i = i
        elif peak_d > 0 and disp[i] < peak_d * 0.85:
            break

    seg_spd = spd[onset : peak_i + 1]
    if len(seg_spd) < 1:
        return int(onset), int(peak_i), int(peak_i)
    spd_peak_frame = onset + int(np.argmax(seg_spd))
    spd_peak_val = float(spd[spd_peak_frame])

    valley_thr = max(0.05 * spd_peak_val, 1e-6)
    decel_cap = min(search_end, spd_peak_frame + int(post_peak_max_s * fs))
    offset = peak_i
    for i in range(spd_peak_frame + 1, decel_cap + 1):
        if spd[i] <= valley_thr:
            offset = i
            break

    offset = max(offset, peak_i)
    if offset - onset + 1 < min_segment_frames:
        offset = min(n - 1, onset + min_segment_frames - 1)
    return int(onset), int(offset), int(peak_i)


def table_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    rest_fraction: float = 0.2,
    disp_on_sw: float = 0.08,
    min_segment_frames: int = 10,
) -> Tuple[int, int]:
    """
    First reach-return cycle for table-top reaching (multi-attempt safe).

    Rest = low-speed prefix; onset/offset = first displacement peak from rest,
    then return toward rest. Avoids picking the last cumulative drift in long videos.
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    if n < min_segment_frames:
        return 0, max(0, n - 1)

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    spd = np.sqrt(vx**2 + vy**2)

    # Rest pose from the opening quiet prefix (not a late low-speed segment).
    n_prefix = max(5, int(min(rest_fraction, 0.12) * n))
    x0 = float(np.median(px[:n_prefix]))
    y0 = float(np.median(py[:n_prefix]))

    disp = np.hypot(px - x0, py - y0) / sw
    if float(np.max(disp)) < disp_on_sw:
        return 0, n - 1

    half = max(n_prefix + 1, n // 2)
    spd_ref = float(np.percentile(spd[:half], 85))
    spd_thr = max(spd_ref * 0.20, 0.08 * float(np.max(spd[:half])))
    disp_thr = max(float(disp_on_sw), 0.05)

    onset = n_prefix
    for i in range(n_prefix, n):
        if disp[i] >= disp_thr and spd[i] >= spd_thr:
            onset = i
            break
    else:
        for i in range(n_prefix, n):
            if disp[i] >= disp_thr:
                onset = i
                break
        else:
            return 0, n - 1

    # First reach peak only (cap search so later attempts are ignored).
    search_end = min(n - 1, onset + int(2.5 * fs))
    peak_i = onset
    peak_d = float(disp[onset])
    for i in range(onset + 1, search_end + 1):
        if disp[i] >= peak_d:
            peak_d = float(disp[i])
            peak_i = i
        elif peak_d > 0 and disp[i] < peak_d * 0.85:
            break

    seg_spd_peak = float(np.max(spd[onset : peak_i + 1]))
    rest_disp_thr = max(0.05, 0.25 * peak_d)
    rest_spd_thr = max(0.12 * seg_spd_peak, 0.05 * float(np.max(spd)))
    offset = peak_i
    offset_cap = min(n - 1, peak_i + int(1.2 * fs))
    for i in range(peak_i, offset_cap + 1):
        # Require return toward rest in BOTH displacement and speed (not speed-only dip).
        if disp[i] <= rest_disp_thr and spd[i] <= rest_spd_thr:
            offset = i
            break
    else:
        offset = min(n - 1, peak_i + max(min_segment_frames, int(0.35 * fs)))

    if offset - onset + 1 < min_segment_frames:
        offset = min(n - 1, max(onset + min_segment_frames - 1, peak_i))
    if offset - onset + 1 < min_segment_frames:
        return 0, n - 1
    return int(onset), int(offset)


def forward_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    rest_fraction: float = 0.12,
    disp_on_sw: float = 0.08,
    min_segment_frames: int = 10,
    max_forward_s: float = 3.5,
) -> Tuple[int, int, int]:
    """
    Forward reach only (rest → target): excludes wipe and return phases.

    Onset = leave rest (same as table_reach). Offset = displacement peak toward
    the target, extended only through the immediate post-peak deceleration valley
    (≤0.25 s). Stops before a second speed burst while displacement stays high
    (wipe guard).

    Returns (onset, offset, displacement_peak_frame).
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    if n < min_segment_frames:
        return 0, max(0, n - 1), 0

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    spd = np.sqrt(vx**2 + vy**2)

    n_prefix = max(5, int(min(rest_fraction, 0.12) * n))
    x0 = float(np.median(px[:n_prefix]))
    y0 = float(np.median(py[:n_prefix]))
    disp = np.hypot(px - x0, py - y0) / sw
    if float(np.max(disp)) < disp_on_sw:
        return 0, n - 1, 0

    half = max(n_prefix + 1, n // 2)
    spd_ref = float(np.percentile(spd[:half], 85))
    spd_thr = max(spd_ref * 0.20, 0.08 * float(np.max(spd[:half])))
    disp_thr = max(float(disp_on_sw), 0.05)

    onset = n_prefix
    for i in range(n_prefix, n):
        if disp[i] >= disp_thr and spd[i] >= spd_thr:
            onset = i
            break
    else:
        for i in range(n_prefix, n):
            if disp[i] >= disp_thr:
                onset = i
                break
        else:
            return 0, n - 1, 0

    search_end = min(n - 1, onset + int(max_forward_s * fs))
    peak_i = onset
    peak_d = float(disp[onset])
    for i in range(onset + 1, search_end + 1):
        if disp[i] >= peak_d:
            peak_d = float(disp[i])
            peak_i = i

    seg_spd_full = spd[onset : search_end + 1]
    if len(seg_spd_full) < 1:
        return int(onset), int(onset), int(onset)
    spd_peak_rel = int(np.argmax(seg_spd_full))
    spd_peak_frame = onset + spd_peak_rel
    spd_peak_val = float(spd[spd_peak_frame])

    # Extend through post-peak deceleration valley (Balasubramanian 5% speed threshold).
    valley_thr = max(0.05 * spd_peak_val, 1e-6)
    decel_cap = min(search_end, spd_peak_frame + int(1.05 * fs))
    offset = spd_peak_frame
    for i in range(spd_peak_frame + 1, decel_cap + 1):
        if spd[i] <= valley_thr:
            offset = i
            break
    else:
        offset = decel_cap

    offset = max(offset, peak_i)

    # Wipe guard: second speed burst while still at target displacement.
    wipe_cap = min(search_end, peak_i + int(0.90 * fs))
    for i in range(peak_i + 2, wipe_cap):
        if disp[i] >= 0.82 * peak_d and spd[i] >= 0.32 * spd_peak_val:
            if spd[i] >= spd[i - 1] and spd[i] >= spd[i + 1]:
                offset = min(offset, max(onset + min_segment_frames - 1, i - 2))
                break

    if offset - onset + 1 < min_segment_frames:
        offset = min(n - 1, onset + min_segment_frames - 1)
    return int(onset), int(offset), int(peak_i)


def _first_speed_peak_in_segment(
    spd: np.ndarray,
    ps: int,
    pe: int,
    *,
    search_fraction: float = 0.55,
    peak_frac: float = 0.50,
) -> int:
    """Dominant speed peak in the opening fraction of a reach (ignore tracking blips)."""
    ps, pe = int(ps), int(pe)
    seg = np.asarray(spd[ps : pe + 1], dtype=float)
    if len(seg) < 3:
        return ps
    limit = max(3, int(len(seg) * search_fraction))
    sub = seg[:limit]
    gmax = float(np.max(sub))
    if gmax <= 1e-9:
        return ps + int(np.argmax(seg))
    thr = peak_frac * gmax
    for j in range(1, len(sub) - 1):
        if (
            sub[j] >= sub[j - 1]
            and sub[j] >= sub[j + 1]
            and sub[j] >= thr
        ):
            return ps + j
    return ps + int(np.argmax(sub))


def _trim_outbound_in_segment(
    px: np.ndarray,
    py: np.ndarray,
    spd: np.ndarray,
    ps: int,
    pe: int,
    fs: float,
    sw: float,
    analysis_profile: str,
    min_segment_frames: int = 10,
) -> Tuple[int, int, int]:
    """First reach bout → outbound only (first speed peak through decel, before wipe)."""
    profile = (analysis_profile or "affected").lower()
    if profile == "reference":
        decel_max_s, post_peak_cap_s, wipe_disp_frac = 0.85, 0.45, 0.70
    else:
        decel_max_s, post_peak_cap_s, wipe_disp_frac = 0.90, 0.55, 0.75

    ps, pe = int(ps), int(min(len(spd) - 1, pe))
    n_prefix = max(5, int(0.12 * len(px)))
    x0 = float(np.median(px[:n_prefix]))
    y0 = float(np.median(py[:n_prefix]))
    disp = np.hypot(px - x0, py - y0) / sw

    spd_peak_frame = _first_speed_peak_in_segment(spd, ps, pe)
    spd_peak_val = float(spd[spd_peak_frame])

    valley_thr = max(0.05 * spd_peak_val, 1e-6)
    decel_cap = min(pe, spd_peak_frame + int(decel_max_s * fs))
    offset = spd_peak_frame
    for i in range(spd_peak_frame + 1, decel_cap + 1):
        if spd[i] <= valley_thr:
            offset = i
            break
    else:
        offset = min(decel_cap, spd_peak_frame + int(post_peak_cap_s * fs))

    disp_seg = disp[ps : pe + 1]
    peak_disp_i = ps + int(np.argmax(disp_seg))
    offset = min(offset, peak_disp_i + int(0.20 * fs))

    peak_d = float(np.max(disp_seg))
    wipe_cap = min(pe, spd_peak_frame + int(1.0 * fs))
    for i in range(spd_peak_frame + 3, wipe_cap):
        if disp[i] >= wipe_disp_frac * peak_d and spd[i] >= 0.30 * spd_peak_val:
            if spd[i] >= spd[i - 1] and spd[i] >= spd[i + 1]:
                offset = min(offset, max(ps + min_segment_frames - 1, i - 3))
                break

    if offset - ps + 1 < min_segment_frames:
        offset = min(pe, ps + min_segment_frames - 1)
    return int(ps), int(offset), int(spd_peak_frame)


def outbound_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    rest_fraction: float = 0.12,
    disp_on_sw: float = 0.08,
    min_segment_frames: int = 10,
    analysis_profile: str = "affected",
) -> Tuple[int, int, int]:
    """
    Outbound reach only: rest → first target contact (excludes wipe/return).

    1. First clinically valid reach bout (primary_reach_window).
    2. First speed peak in the opening of that bout + deceleration (not wipe burst).
    3. Cap at displacement peak toward target (Balasubramanian reach phase).

    Returns (onset, offset, first_speed_peak_frame).
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    if n < min_segment_frames:
        return 0, max(0, n - 1), 0

    profile = (analysis_profile or "affected").lower()
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )
    spd = palm_image_speed(px, py, fs)

    min_amp = 0.15 if profile == "reference" else 0.12
    ps, pe = primary_reach_window(
        spd,
        px,
        py,
        fs,
        velocity_threshold=3.0,
        shoulder_width=shoulder_width,
        min_segment_frames=min_segment_frames,
        coords_in_sw=True,
        min_path_sw=0.08,
        min_amp_sw=min_amp,
    )
    # Frontal short reaches (e.g. Murat healthy): first bout may be <0.15 SW.
    if profile == "reference":
        early_cap = int(3.0 * fs)
        segs = _list_segments(
            spd, px, py, fs, velocity_threshold=3.0, min_segment_frames=min_segment_frames
        )
        early_ok = [
            s
            for s in segs
            if s["start"] < early_cap
            and 0.30 <= s["dur"] <= 2.5
            and (s["disp"] / sw if sw else s["disp"]) >= 0.04
        ]
        amp_ok = (pe - ps + 1) > 0 and (
            float(np.hypot(px[pe] - px[ps], py[pe] - py[ps])) / sw >= min_amp
        )
        if early_ok and not amp_ok:
            best = min(early_ok, key=lambda x: (x["start"], -x["disp"]))
            ps, pe = int(best["start"]), int(best["end"])
    return _trim_outbound_in_segment(
        px, py, spd, ps, pe, fs, sw, profile, min_segment_frames=min_segment_frames
    )


def sparc_motion_window(
    speed: np.ndarray,
    move_start: int,
    move_end: int,
    min_segment_frames: int = 10,
    speed_frac: float = 0.30,
) -> Tuple[int, int]:
    """
    SPARC segment: main velocity burst from threshold crossing to peak speed.
    Excludes pre-movement creep and post-peak deceleration/jitter.
    """
    move_start = int(max(0, move_start))
    move_end = int(min(len(speed) - 1, move_end))
    if move_end <= move_start:
        return move_start, move_end

    seg = speed[move_start : move_end + 1]
    if len(seg) < 3:
        return move_start, move_end

    peak_local = int(np.argmax(seg))
    peak_val = float(seg[peak_local])
    if peak_val <= 1e-9:
        return move_start, move_end

    thr = speed_frac * peak_val
    start_local = 0
    for i in range(peak_local, -1, -1):
        if seg[i] < thr:
            start_local = min(i + 1, peak_local)
            break

    if peak_local - start_local + 1 < min_segment_frames:
        start_local = max(0, peak_local - min_segment_frames + 1)

    s = move_start + start_local
    e = move_start + peak_local
    while e < move_end and (e - s + 1) < min_segment_frames:
        e += 1
    return int(s), int(e)


def literature_reach_window(
    speed: np.ndarray,
    fs: float,
    v_frac: float = 0.05,
    search_start: int = 0,
    search_end: Optional[int] = None,
    min_segment_frames: int = 10,
) -> Tuple[int, int]:
    """
    Balasubramanian et al. movement window: onset/offset at v_frac × peak
    tangential speed (default 5%). Used for SPARC, trunk, and shoulder on
    the same segment.
    """
    n = len(speed)
    if n < min_segment_frames:
        return 0, max(0, n - 1)
    i0 = max(0, int(search_start))
    i1 = n if search_end is None else min(n, int(search_end) + 1)
    if i1 - i0 < min_segment_frames:
        return i0, min(n - 1, i0 + min_segment_frames - 1)

    seg = np.asarray(speed[i0:i1], dtype=float)
    gmax = float(np.max(seg))
    if gmax <= 1e-9:
        return i0, min(n - 1, i0 + min_segment_frames - 1)

    # First dominant local peak (reach-wipe: do not jump to later wipe/return burst).
    peak_rel = 0
    for j in range(1, len(seg) - 1):
        if seg[j] >= seg[j - 1] and seg[j] >= seg[j + 1] and seg[j] >= 0.25 * gmax:
            peak_rel = j
            break
    else:
        peak_rel = int(np.argmax(seg))

    peak = float(seg[peak_rel])
    thr = v_frac * peak

    rel_on = peak_rel
    for j in range(peak_rel, -1, -1):
        if seg[j] >= thr:
            rel_on = j
    rel_off = peak_rel
    for j in range(peak_rel, len(seg)):
        if seg[j] >= thr:
            rel_off = j

    onset = i0 + rel_on
    offset = i0 + rel_off
    if offset - onset + 1 < min_segment_frames:
        offset = min(n - 1, onset + min_segment_frames - 1)
    return int(onset), int(offset)


def sparc_bell_window(
    speed: np.ndarray,
    move_start: int,
    move_end: int,
    min_segment_frames: int = 10,
    speed_frac: float = 0.30,
) -> Tuple[int, int]:
    """
    SPARC segment: symmetric speed bell from 30% peak on accel through deceleration.
    Includes the full reach velocity profile (not accel-only), per Balasubramanian et al.
    """
    move_start = int(max(0, move_start))
    move_end = int(min(len(speed) - 1, move_end))
    if move_end <= move_start:
        return move_start, move_end

    seg = speed[move_start : move_end + 1]
    if len(seg) < 3:
        return move_start, move_end

    peak_local = int(np.argmax(seg))
    peak_val = float(seg[peak_local])
    if peak_val <= 1e-9:
        return move_start, move_end

    thr = speed_frac * peak_val
    start_local = 0
    for i in range(peak_local, -1, -1):
        if seg[i] < thr:
            start_local = min(i + 1, peak_local)
            break

    end_local = peak_local
    for i in range(peak_local, len(seg)):
        if seg[i] < thr:
            end_local = max(i - 1, peak_local)
            break
    else:
        end_local = len(seg) - 1

    if end_local - start_local + 1 < min_segment_frames:
        start_local = max(0, peak_local - min_segment_frames // 2)
        end_local = min(len(seg) - 1, start_local + min_segment_frames - 1)

    return move_start + start_local, move_start + end_local


def _extend_reach_to_speed_peak(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    onset: int,
    offset: int,
    *,
    search_s: float = 4.0,
    valley_s: float = 1.05,
) -> int:
    """
    Extend a short table-style window through the main speed peak deceleration.

    Reference (healthy) trials often pause briefly before the main reach bell;
    stopping at the first low-speed frame truncates SPARC and inflates trunk ratio.
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    onset = int(max(0, onset))
    offset = int(min(n - 1, offset))
    if offset <= onset:
        return offset

    spd = palm_image_speed(px, py, fs)
    search_end = min(n - 1, onset + int(search_s * fs))
    seg = spd[onset : search_end + 1]
    if len(seg) < 3:
        return offset

    peak_rel = int(np.argmax(seg))
    peak_frame = onset + peak_rel
    if peak_frame <= offset:
        return offset

    peak_val = float(spd[peak_frame])
    valley_thr = max(0.05 * peak_val, 1e-6)
    decel_cap = min(search_end, peak_frame + int(valley_s * fs))
    ext = peak_frame
    for i in range(peak_frame + 1, decel_cap + 1):
        if spd[i] <= valley_thr:
            ext = i
            break
    else:
        ext = min(decel_cap, peak_frame + int(0.45 * fs))
    return int(max(offset, ext))


def kinematic_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    min_segment_frames: int = 10,
    analysis_profile: str = "affected",
    min_dur_s: float = 0.20,
) -> Tuple[int, int]:
    """
    Reach window for trunk, shoulder, elbow (forward reach phase).

    SPARC uses the shorter outbound bell window; trunk metrics follow
    displacement-based forward reach (Balasubramanian reach phase).
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else None
    profile = (analysis_profile or "affected").lower()

    onset, offset, _peak = forward_reach_window(
        px, py, fs,
        shoulder_width=shoulder_width,
        min_segment_frames=min_segment_frames,
    )

    if profile == "reference":
        dur_fwd = (offset - onset + 1) / fs
        amp_fwd_sw = (
            float(np.hypot(px[offset] - px[onset], py[offset] - py[onset])) / sw
            if sw
            else float(np.hypot(px[offset] - px[onset], py[offset] - py[onset])) / 50.0
        )
        if dur_fwd < 0.55 or amp_fwd_sw < 0.12:
            picked = False
            if sw:
                spd = palm_image_speed(px, py, fs)
                segs = _list_segments(
                    spd, px, py, fs, velocity_threshold=3.0, min_segment_frames=min_segment_frames
                )
                early_cap = int(3.0 * fs)
                early_ok = [
                    s
                    for s in segs
                    if s["start"] < early_cap
                    and 0.30 <= s["dur"] <= 2.5
                    and (s["disp"] / sw) >= 0.04
                ]
                if early_ok:
                    best = min(early_ok, key=lambda x: (x["start"], -x["disp"]))
                    onset, offset = int(best["start"]), int(best["end"])
                    picked = True
            if not picked:
                t_on, t_off = table_reach_window(
                    px, py, fs, shoulder_width=shoulder_width, min_segment_frames=min_segment_frames
                )
                if (t_off - t_on + 1) / fs >= min_dur_s:
                    onset, offset = t_on, _extend_reach_to_speed_peak(px, py, fs, t_on, t_off)
    else:
        spd = palm_image_speed(px, py, fs)
        ps, pe = primary_reach_window(
            spd,
            px,
            py,
            fs,
            velocity_threshold=3.0,
            shoulder_width=shoulder_width,
            min_segment_frames=min_segment_frames,
            coords_in_sw=True,
            min_path_sw=0.08,
            min_amp_sw=0.12,
        )
        offset = min(offset, pe)

    return int(onset), int(offset)


def _lowpass_filter_speed(speed: np.ndarray, fs: float, cutoff_hz: float = 10.0) -> np.ndarray:
    """Smooth speed profile with zero-phase low-pass filter (Balasubramanian 10 Hz)."""
    from scipy.signal import butter, filtfilt

    arr = np.asarray(speed, dtype=float)
    n = len(arr)
    if n < 7 or fs <= 0 or cutoff_hz <= 0:
        return arr
    nyq = 0.5 * fs
    wn = min(cutoff_hz / nyq, 0.99)
    if wn <= 0:
        return arr
    b, a = butter(2, wn, btype="low")
    try:
        return filtfilt(b, a, arr)
    except ValueError:
        return arr


def select_literature_matched_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    reference_amplitude_sw: Optional[float] = None,
    velocity_threshold_frac: float = 0.05,
    min_duration_s: float = 0.50,
    min_amplitude_sw: float = 0.12,
    amplitude_tolerance: float = 0.20,
    max_search_s: float = 4.0,
    speed_cutoff_hz: float = 10.0,
) -> Tuple[int, int]:
    """
    Literature-backed uniform reach window (Balasubramanian et al.).

    Steps:
      1. Body-frame palm coordinates (shoulder-centered, SW-normalized).
      2. Tangential speed, low-pass filtered at 10 Hz before differentiation.
      3. Detect all speed segments above 5% of global peak (default v_frac).
      4. Keep clinically valid reaches: duration >= 0.5 s, amplitude >= 0.12 SW.
      5. If a reference (healthy) amplitude is supplied, pick the early reach
         whose amplitude is closest to the reference (within +/-tolerance).
      6. Otherwise pick the first valid reach bout.
      7. Trim onset/offset at v_frac * segment peak speed.

    The same algorithm is used for healthy, pre, and post so that differences
    in SPARC reflect neuromotor control, not window-selection bias.
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    if n < 10:
        return 0, max(0, n - 1)

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else float(
        max(np.ptp(px), np.ptp(py), 50.0)
    )

    # Body-frame palm for view-stable speed and amplitude
    x0, y0 = float(np.median(px[: max(3, int(0.12 * n))])), float(np.median(py[: max(3, int(0.12 * n))]))
    bx = (px - x0) / sw
    by = (py - y0) / sw

    # Speed computed on filtered body-frame coordinates
    bx_s = smooth_series(bx, fs, window_s=0.10)
    by_s = smooth_series(by, fs, window_s=0.10)
    vx = np.gradient(bx_s) * fs
    vy = np.gradient(by_s) * fs
    speed = np.sqrt(vx**2 + vy**2)
    speed = _lowpass_filter_speed(speed, fs, cutoff_hz=speed_cutoff_hz)

    # List speed segments above threshold
    peak_speed = float(np.max(speed))
    if peak_speed <= 1e-9:
        return 0, max(0, n - 1)

    thr = max(velocity_threshold_frac * peak_speed, 1e-6)
    segs = _list_segments(
        speed, px, py, fs,
        velocity_threshold=thr,
        max_gap_frames=6,
        min_segment_frames=max(5, int(min_duration_s * fs * 0.5)),
    )
    if not segs:
        return 0, max(0, n - 1)

    # Restrict to early reaches (ignore late recovery/wipe)
    early_cap = int(max_search_s * fs)
    valid = []
    for s in segs:
        if s["start"] >= early_cap:
            continue
        amp_sw = float(s["disp"]) / sw
        dur_s = float(s["dur"])
        if dur_s >= min_duration_s and amp_sw >= min_amplitude_sw:
            valid.append({**s, "amplitude_sw": amp_sw})

    # Fallback: relaxed criteria
    if not valid:
        for s in segs:
            if s["start"] >= early_cap:
                continue
            amp_sw = float(s["disp"]) / sw
            dur_s = float(s["dur"])
            if dur_s >= max(0.35, min_duration_s * 0.7) and amp_sw >= max(0.08, min_amplitude_sw * 0.67):
                valid.append({**s, "amplitude_sw": amp_sw})

    if not valid:
        # Last resort: first segment
        best = min(segs, key=lambda x: x["start"])
        valid = [{**best, "amplitude_sw": float(best["disp"]) / sw}]

    # If reference amplitude given, pick closest match within tolerance.
    # Otherwise (healthy reference trial) pick the first valid early reach.
    chosen = valid[0]
    if reference_amplitude_sw is not None and np.isfinite(reference_amplitude_sw) and reference_amplitude_sw > 0:
        ref = float(reference_amplitude_sw)
        matched = [s for s in valid if abs(s["amplitude_sw"] - ref) / ref <= amplitude_tolerance]
        if matched:
            chosen = min(matched, key=lambda s: abs(s["amplitude_sw"] - ref))
        else:
            # Pick closest overall if none within tolerance
            chosen = min(valid, key=lambda s: abs(s["amplitude_sw"] - ref))

    onset = int(chosen["start"])
    offset = int(chosen["end"])

    # Refine with literature 5% peak-velocity trimming inside the chosen segment.
    # For SPARC we additionally cap at the first forward-reach displacement peak
    # to avoid including return/wipe/secondary bursts in the smoothness metric.
    refined_on, refined_off = literature_reach_window(
        speed, fs, v_frac=velocity_threshold_frac,
        search_start=onset, search_end=offset, min_segment_frames=10,
    )

    if refined_off - refined_on + 1 >= max(5, int(min_duration_s * fs * 0.5)):
        return int(refined_on), int(refined_off)
    return int(onset), int(offset)


def amplitude_matched_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    onset: int,
    offset: int,
    target_amplitude_sw: float,
    shoulder_width: float,
    shoulder_x: Optional[np.ndarray] = None,
    shoulder_y: Optional[np.ndarray] = None,
    min_segment_frames: int = 10,
) -> Tuple[int, int]:
    """
    Truncate a reach window so all conditions end at the same body-frame displacement.

    Literature (Balasubramanian; Rohrer et al. 2002; Krebs et al. 1999) shows
    that SPARC is only comparable when reaches have similar amplitude and
    movement time. If one reach travels much farther than another, the longer
    window can include deceleration/wipe phases that change SPARC independently
    of smoothness.

    The match is performed in the shoulder-centered (body-frame) coordinate
    system because SPARC itself is computed on body-frame speed.
    target_amplitude_sw is in shoulder-width units.
    """
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    n = len(px)
    onset = int(max(0, min(onset, n - 1)))
    offset = int(max(onset, min(offset, n - 1)))
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else 1.0

    if target_amplitude_sw <= 0 or onset == offset:
        return onset, offset

    # Body-frame palm relative to shoulder position at movement onset.
    sx0 = float(shoulder_x[onset]) if shoulder_x is not None and len(shoulder_x) == n else 0.0
    sy0 = float(shoulder_y[onset]) if shoulder_y is not None and len(shoulder_y) == n else 0.0
    bx = (px - sx0) / sw
    by = (py - sy0) / sw

    # Cumulative body-frame displacement; enforce monotonicity against tracking jitter.
    cum = np.maximum.accumulate(
        np.hypot(bx[onset:offset + 1] - bx[onset], by[onset:offset + 1] - by[onset])
    )
    idx = np.searchsorted(cum, float(target_amplitude_sw), side="right")
    if idx == 0:
        idx = 1
    matched_offset = onset + idx - 1
    matched_offset = int(max(onset + min_segment_frames - 1, min(matched_offset, offset)))
    return onset, matched_offset


def select_reach_window(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    shoulder_width: Optional[float] = None,
    velocity_threshold: float = 5.0,
    min_segment_frames: int = 10,
    min_dur_s: float = 0.20,
    min_amp_sw: float = 0.06,
    phase_search_s: float = 2.5,
    body_speed: Optional[np.ndarray] = None,
    forward_only: bool = True,
    analysis_profile: str = "affected",
) -> Tuple[int, int]:
    """
    Primary reach window for SPARC / reach amplitude (native fps, before upsampling).

    reference: displacement-based forward reach (full velocity bell for SPARC).
    affected: first reach bout → outbound trim.
    """
    _ = body_speed, phase_search_s, velocity_threshold, min_amp_sw  # legacy kwargs
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else None
    profile = (analysis_profile or "affected").lower()

    if forward_only:
        if profile == "reference":
            onset, offset, _peak = forward_reach_window(
                px, py, fs,
                shoulder_width=shoulder_width,
                min_segment_frames=min_segment_frames,
            )
            dur_fwd = (offset - onset + 1) / fs
            amp_fwd = float(np.hypot(px[offset] - px[onset], py[offset] - py[onset]))
            amp_fwd_sw = amp_fwd / sw if sw else amp_fwd / 50.0
            if dur_fwd < 0.55 or amp_fwd_sw < 0.12:
                picked = False
                if sw:
                    spd = palm_image_speed(px, py, fs)
                    segs = _list_segments(
                        spd, px, py, fs, velocity_threshold=3.0, min_segment_frames=min_segment_frames
                    )
                    early_cap = int(3.0 * fs)
                    early_ok = [
                        s
                        for s in segs
                        if s["start"] < early_cap
                        and 0.30 <= s["dur"] <= 2.5
                        and (s["disp"] / sw) >= 0.04
                    ]
                    if early_ok:
                        best = min(early_ok, key=lambda x: (x["start"], -x["disp"]))
                        onset, offset = int(best["start"]), int(best["end"])
                        picked = True
                if not picked:
                    t_on, t_off = table_reach_window(
                        px, py, fs, shoulder_width=shoulder_width, min_segment_frames=min_segment_frames
                    )
                    if (t_off - t_on + 1) / fs >= min_dur_s:
                        onset, offset = t_on, _extend_reach_to_speed_peak(px, py, fs, t_on, t_off)
        else:
            onset, offset, _peak = outbound_reach_window(
                px, py, fs,
                shoulder_width=shoulder_width,
                min_segment_frames=min_segment_frames,
                analysis_profile=profile,
            )
    else:
        pix_speed = reach_speed_series(px, py, None, fs)
        onset, offset = primary_reach_window(
            pix_speed,
            px,
            py,
            fs,
            velocity_threshold=3.0,
            shoulder_width=shoulder_width,
            min_segment_frames=min_segment_frames,
            coords_in_sw=True,
            min_path_sw=0.08,
            min_amp_sw=0.12,
        )

    dur_s = (offset - onset + 1) / fs
    disp_px = float(np.hypot(px[offset] - px[onset], py[offset] - py[onset]))
    amp_sw = disp_px / sw if sw else disp_px / 50.0
    if dur_s >= min_dur_s:
        return int(onset), int(offset)

    pix_speed = reach_speed_series(px, py, None, fs)
    ps, pe = primary_reach_window(
        pix_speed,
        px,
        py,
        fs,
        velocity_threshold=3.0,
        shoulder_width=shoulder_width,
        min_segment_frames=min_segment_frames,
        coords_in_sw=True,
        min_path_sw=0.08,
        min_amp_sw=0.12 if profile != "reference" else 0.15,
    )
    return int(ps), int(pe)


def reach_amplitude_sw(bx: np.ndarray, by: np.ndarray, bz: Optional[np.ndarray], start: int, end: int) -> float:
    seg_x = bx[start : end + 1]
    seg_y = by[start : end + 1]
    if bz is not None:
        seg_z = bz[start : end + 1]
        disp = np.sqrt((seg_x[-1] - seg_x[0]) ** 2 + (seg_y[-1] - seg_y[0]) ** 2 + (seg_z[-1] - seg_z[0]) ** 2)
    else:
        disp = np.sqrt((seg_x[-1] - seg_x[0]) ** 2 + (seg_y[-1] - seg_y[0]) ** 2)
    return float(disp)


def compute_hand_reach_displacement(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    shoulder_x: np.ndarray,
    shoulder_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    shoulder_width: Optional[float],
    start: int,
    end: int,
    *,
    palm_z: Optional[np.ndarray] = None,
    shoulder_z: Optional[np.ndarray] = None,
) -> Optional[Dict[str, float]]:
    """
    Literature-aligned hand reach during forward-reach window.

    Primary (de Bruin et al. 2019; Balasubramanian SPARC frame):
      peak + endpoint displacement of the palm in a shoulder-centered frame,
      normalized by shoulder width (SW units).

    Anti-cheat audit (trunk compensation literature):
      peak palm displacement relative to trunk proxy — reported separately.

    Optional limb normalization (Kinect stroke compensatory studies):
      peak reach / upper-arm + forearm length.
    """
    if end <= start or (end - start) < 10:
        return None

    bx, by, bz, sw = body_frame_palm(
        palm_x, palm_y, shoulder_x, shoulder_y, shoulder_width,
        palm_z=palm_z, shoulder_z=shoulder_z,
    )

    dx = bx[start : end + 1] - bx[start]
    dy = by[start : end + 1] - by[start]
    dists = np.hypot(dx, dy)
    peak_sw = float(np.max(dists)) if len(dists) else float("nan")
    endpoint_sw = float(np.hypot(bx[end] - bx[start], by[end] - by[start]))

    ua = np.hypot(
        elbow_x[start : end + 1] - shoulder_x[start : end + 1],
        elbow_y[start : end + 1] - shoulder_y[start : end + 1],
    )
    fa = np.hypot(
        wrist_x[start : end + 1] - elbow_x[start : end + 1],
        wrist_y[start : end + 1] - elbow_y[start : end + 1],
    )
    limb_px = float(np.median(ua + fa))
    peak_limb_norm = peak_sw * sw / max(limb_px, 1e-6) if np.isfinite(peak_sw) else float("nan")

    rel_x = palm_x - trunk_x
    rel_y = palm_y - trunk_y
    trunk_dists = np.hypot(
        rel_x[start : end + 1] - rel_x[start],
        rel_y[start : end + 1] - rel_y[start],
    )
    trunk_peak_px = float(np.max(trunk_dists)) if len(trunk_dists) else float("nan")
    trunk_peak_sw = trunk_peak_px / sw if np.isfinite(sw) and sw > 0 else float("nan")

    palm_raw_px = float(
        np.hypot(palm_x[end] - palm_x[start], palm_y[end] - palm_y[start])
    )
    cheat_ratio = (
        palm_raw_px / max(trunk_peak_px, 1e-6)
        if np.isfinite(palm_raw_px) and np.isfinite(trunk_peak_px) and trunk_peak_px > 1e-6
        else float("nan")
    )

    return {
        "peak_sw": peak_sw,
        "endpoint_sw": endpoint_sw,
        "limb_norm": peak_limb_norm,
        "trunk_peak_sw": trunk_peak_sw,
        "trunk_peak_px": trunk_peak_px,
        "palm_raw_px": palm_raw_px,
        "trunk_cheat_ratio": cheat_ratio,
    }


def compute_forward_reach_cm(
    trunk_x: np.ndarray,
    trunk_y: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    start: int,
    end: int,
    cm_per_px: Optional[float],
) -> Optional[Dict[str, float]]:
    """
    Forward reach (cm) during outbound window only.

    Trunk-relative displacement projected onto the initial reach axis (rest → early
    movement). Excludes lateral wipe motion that inflates 2D peak magnitude.
    """
    if end <= start or (end - start) < 5:
        return None
    if not cm_per_px or cm_per_px <= 0:
        return None

    rel_x = np.asarray(palm_x, dtype=float) - np.asarray(trunk_x, dtype=float)
    rel_y = np.asarray(palm_y, dtype=float) - np.asarray(trunk_y, dtype=float)
    rx0 = float(rel_x[start])
    ry0 = float(rel_y[start])

    span = end - start
    early_i = start + max(3, min(int(0.15 * span), 12))
    ax = float(rel_x[early_i] - rel_x[start])
    ay = float(rel_y[early_i] - rel_y[start])
    am = float(np.hypot(ax, ay))
    if am < 2.0:
        seg_x = rel_x[start : end + 1] - rx0
        seg_y = rel_y[start : end + 1] - ry0
        peak_2d_px = float(np.max(np.hypot(seg_x, seg_y)))
        peak_fwd_px = peak_2d_px
        reach_axis_deg = float("nan")
    else:
        ux, uy = ax / am, ay / am
        seg_x = rel_x[start : end + 1] - rx0
        seg_y = rel_y[start : end + 1] - ry0
        proj = seg_x * ux + seg_y * uy
        peak_fwd_px = float(np.max(proj))
        if peak_fwd_px < 0:
            peak_fwd_px = float(np.max(np.hypot(seg_x, seg_y)))
        reach_axis_deg = float(np.degrees(np.arctan2(uy, ux)))

    peak_2d_px = float(
        np.max(np.hypot(rel_x[start : end + 1] - rx0, rel_y[start : end + 1] - ry0))
    )
    endpoint_fwd_px = float(
        np.hypot(rel_x[end] - rx0, rel_y[end] - ry0)
    )

    peak_cm = float(peak_fwd_px * cm_per_px)
    endpoint_cm = float(
        np.hypot(rel_x[end] - rel_x[start], rel_y[end] - rel_y[start]) * cm_per_px
    )

    return {
        "peak_cm": peak_cm,
        "endpoint_cm": endpoint_cm,
        "peak_fwd_px": peak_fwd_px,
        "peak_2d_px": peak_2d_px,
        "reach_axis_deg": reach_axis_deg,
    }


def sparc_quality_ok(
    amplitude_sw: float,
    active_frames: int,
    fs: float,
    movement_duration_s: Optional[float] = None,
    *,
    min_amplitude_sw: float = 0.15,
    min_duration_s: float = 0.35,
) -> bool:
    """SPARC comparable: outbound reach ≥0.15 SW and movement ≥0.35 s."""
    dur_s = float(movement_duration_s) if movement_duration_s is not None else active_frames / fs
    return (
        np.isfinite(amplitude_sw)
        and amplitude_sw >= min_amplitude_sw
        and dur_s >= min_duration_s
    )


def amplitude_matched(
    amplitude_sw: float,
    reference_amplitude_sw: float,
    tolerance: float = 0.15,
) -> bool:
    """Within ±tolerance of reference reach amplitude (literature amplitude matching)."""
    if not (np.isfinite(amplitude_sw) and np.isfinite(reference_amplitude_sw)):
        return False
    if reference_amplitude_sw <= 0:
        return False
    return abs(amplitude_sw - reference_amplitude_sw) / reference_amplitude_sw <= tolerance


def infer_trial_role(csv_path: str, affected_side: str = "auto") -> str:
    """Infer pre / post / healthy from filename for comparison reporting."""
    stem = Path(csv_path).stem.lower()
    if any(k in stem for k in ("baseline", "healthy", "healthyside", "unaffected", "control")):
        return "healthy"
    if "post" in stem:
        return "post"
    if "pre" in stem:
        return "pre"
    if affected_side in ("left", "right"):
        return "paretic"
    return "unknown"


def assess_trial_quality(
    *,
    amplitude_sw: float,
    movement_frames: int,
    movement_duration_s: float,
    fs: float,
    trunk_ratio: float,
    trunk_disp_px: float,
    palm_disp_px: float,
    shoulder_width: Optional[float],
    sparc_comparable: bool,
    sparc_value: float,
    forward_reach: bool = True,
    frame_quality_pct: Optional[float] = None,
    min_amplitude_sw: float = 0.12,
    min_movement_s: float = 0.20,
    max_forward_s: float = 4.0,
    min_trunk_ratio: float = 0.015,
    max_trunk_ratio: float = 1.50,
) -> Dict[str, object]:
    """
    Quality gates for stroke reaching trials (forward-reach phase).

    Returns flags + trial_valid (safe for group comparison).
    """
    flags: List[str] = []
    issues: List[str] = []

    sw = float(shoulder_width) if shoulder_width and shoulder_width > 0 else None
    palm_sw = (palm_disp_px / sw) if sw and palm_disp_px else None

    reach_amp_ok = np.isfinite(amplitude_sw) and amplitude_sw >= min_amplitude_sw
    if not reach_amp_ok:
        flags.append("low_reach_amplitude")
        issues.append(f"reach amplitude {amplitude_sw:.2f} SW < {min_amplitude_sw:.2f}")

    dur_ok = movement_duration_s >= min_movement_s
    if not dur_ok:
        flags.append("short_movement")
        issues.append(f"movement {movement_duration_s:.2f}s < {min_movement_s:.2f}s")

    if forward_reach and movement_duration_s > max_forward_s:
        flags.append("window_includes_wipe_or_return")
        issues.append(f"forward window {movement_duration_s:.2f}s > {max_forward_s:.2f}s")

    frames_ok = movement_frames >= max(8, int(min_movement_s * fs))
    if not frames_ok:
        flags.append("insufficient_frames")
        issues.append(f"only {movement_frames} movement frames")

    trunk_ok = True
    if np.isfinite(trunk_ratio):
        if trunk_ratio < min_trunk_ratio and (palm_sw is None or palm_sw >= 0.05):
            trunk_ok = False
            flags.append("trunk_suspiciously_low")
            issues.append(f"trunk ratio {trunk_ratio:.1%} with meaningful palm motion")
        # Large reach with almost no trunk displacement → tracking or window error.
        if np.isfinite(amplitude_sw) and amplitude_sw >= 0.20 and trunk_ratio < 0.03:
            trunk_ok = False
            if "trunk_suspiciously_low" not in flags:
                flags.append("trunk_suspiciously_low")
                issues.append(
                    f"trunk {trunk_ratio:.1%} too low for reach amplitude {amplitude_sw:.2f} SW"
                )
        if trunk_ratio > max_trunk_ratio:
            trunk_ok = False
            flags.append("trunk_suspiciously_high")
            issues.append(f"trunk ratio {trunk_ratio:.1%} > {max_trunk_ratio:.0%}")
    else:
        trunk_ok = False
        flags.append("trunk_nan")

    if sw and palm_disp_px < 0.05 * sw:
        flags.append("low_palm_displacement")
        issues.append("palm displacement < 5% shoulder width")

    if not sparc_comparable:
        flags.append("sparc_not_comparable")
        issues.append("SPARC: reach <0.25 SW or movement <1.0 s (literature gate)")

    if np.isfinite(sparc_value) and sparc_value > -0.5:
        flags.append("sparc_atypical")
        issues.append("SPARC near zero (check window or tracking)")

    if frame_quality_pct is not None and frame_quality_pct < 70.0:
        flags.append("low_tracking_quality")
        issues.append(f"tracking quality {frame_quality_pct:.0f}% < 70%")

    reach_valid = reach_amp_ok and dur_ok and frames_ok and (
        palm_sw is None or palm_sw >= 0.05
    )
    metrics_comparable = reach_valid and trunk_ok and sparc_comparable and not (
        "window_includes_wipe_or_return" in flags
    )
    trial_valid = metrics_comparable and "low_tracking_quality" not in flags

    return {
        "trial_valid": bool(trial_valid),
        "metrics_comparable": bool(metrics_comparable),
        "reach_valid": bool(reach_valid),
        "trunk_valid": bool(trunk_ok),
        "sparc_valid": bool(sparc_comparable and np.isfinite(sparc_value)),
        "forward_reach_only": bool(forward_reach),
        "quality_flags": flags,
        "quality_issues": issues,
    }
