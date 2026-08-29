"""
Lightweight overlay data for browser-side validation video rendering.

Returns per-frame landmarks + metrics so the frontend can draw the skeleton,
trajectory, and metric labels on top of the original video without waiting for
server-side video encoding.
"""

import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import cv2

from unified_kinematics import _interpolate_small_gaps, _butter_lowpass_filter
from table_calibrator import find_video_for_csv

# Shown on validation overlay (reach window + optional ADL transport phase).
OVERLAY_JOINT_METRIC_KEYS = (
    "shoulder_abduction_mean_deg",
    "shoulder_abduction_rom_deg",
    "peak_shoulder_abduction_vel_deg_s",
    "shoulder_abduction_trunk_compensation_index",
    "forearm_pronation_supination_rom_deg",
    "peak_forearm_rotation_vel_deg_s",
    "forearm_rotation_quality_index",
    "fine_motor_quality_index",
    "pinch_grasp_quality_index",
    "pinch_tremor_8_12hz_power",
    "finger_flex_ext_rom_sw",
    "finger_flex_ext_quality_index",
    "head_forward_flexion_compensation_index",
    "head_flexion_increase_deg",
    "adl_tremor_8_12hz_power",
    "tremor_index",
    "tremor_peak_freq_hz",
    "index_tremor_8_12hz_power",
    "index_tremor_peak_freq_hz",
    "adl_tremor_peak_freq_hz",
    "adl_index_tremor_8_12hz_power",
    "movement_quality_index",
    "elbow_tremor_8_12hz_power",
    "shoulder_flexion_tremor_8_12hz_power",
    "adl_tremor_8_12hz_power",
    "sparc_shoulder_flexion",
    "sparc_shoulder_abduction",
    "sparc_forearm_rotation",
)


def _validation_phase_id_for_task(task: str) -> Optional[str]:
    """Phase used for extended validation metrics (transport ADL or reach & grasp)."""
    t = (task or "").strip().lower()
    if "brush" in t:
        return "transport_brush"
    if "drink" in t:
        return "transport_drink"
    if t in ("study_reach_grasp",) or "reach_grasp" in t:
        return "reach_grasp"
    return None


def _copy_joint_metrics_from_analysis(metrics: Dict[str, Any], analysis: Optional[Dict[str, Any]]) -> None:
    if not analysis:
        return
    task = str(analysis.get("clinical_task") or "")
    if task:
        metrics["clinical_task"] = task
    label = analysis.get("clinical_task_label")
    if label:
        metrics["clinical_task_label"] = str(label)
    mp = analysis.get("movement_profile")
    if isinstance(mp, dict):
        for k in OVERLAY_JOINT_METRIC_KEYS:
            if mp.get(k) is not None and metrics.get(k) is None:
                metrics[k] = mp[k]
    for k in OVERLAY_JOINT_METRIC_KEYS:
        if analysis.get(k) is not None and metrics.get(k) is None:
            metrics[k] = analysis[k]
    pick = _validation_phase_id_for_task(task)
    if not pick:
        return
    for ph in analysis.get("task_phases") or []:
        if ph.get("id") == pick:
            tm = ph.get("metrics") or {}
            metrics["validation_adl_phase_id"] = pick
            for k in OVERLAY_JOINT_METRIC_KEYS:
                if tm.get(k) is not None:
                    metrics[f"adl_{k}"] = tm[k]
            if pick == "reach_grasp" and tm.get("tremor_8_12hz_power") is not None:
                metrics["adl_tremor_8_12hz_power"] = tm["tremor_8_12hz_power"]
            for adl_tk in (
                "tremor_peak_freq_hz",
                "index_tremor_8_12hz_power",
                "index_tremor_peak_freq_hz",
            ):
                if tm.get(adl_tk) is not None:
                    metrics[f"adl_{adl_tk}"] = tm[adl_tk]
            break


def _video_orientation_and_dims(video_path: Optional[Path]) -> Tuple[int, float, float]:
    """Read orientation metadata and frame size from the exact video file used in the browser."""
    try:
        if not video_path or not Path(video_path).exists():
            return 0, 1920.0, 1080.0
        from video_orientation import probe_rotation_deg, probe_stream_size

        orient = int(probe_rotation_deg(video_path) or 0)
        raw_w, raw_h = probe_stream_size(video_path)
        if raw_w <= 0 or raw_h <= 0:
            raw_w, raw_h = 1920.0, 1080.0
        # ffprobe can report upscaled size; OpenCV matches many browser decodes for phone MP4s.
        cap_w, cap_h = _opencv_stream_size(video_path)
        if cap_w > 0 and cap_h > 0:
            probe_area = raw_w * raw_h
            cap_area = cap_w * cap_h
            if probe_area <= 0 or abs(probe_area - cap_area) / max(cap_area, 1.0) > 0.35:
                raw_w, raw_h = cap_w, cap_h
        return orient, float(raw_w), float(raw_h)
    except Exception:
        return 0, 1920.0, 1080.0


def _detect_orientation_and_dims(csv_path: str) -> Tuple[int, float, float]:
    """Legacy helper — prefer _video_orientation_and_dims with the served video path."""
    return _video_orientation_and_dims(find_video_for_csv(csv_path))


def _rotate_xy(df: pd.DataFrame, orientation: int, raw_w: float, raw_h: float) -> pd.DataFrame:
    """Rotate X/Y columns to match the video's displayed orientation.

    Handles both normalized (0..1) and pixel coordinate columns. For pixel columns
    the rotated pixel values are returned in the displayed frame; for normalized
    columns the rotated normalized values are returned.
    """
    if orientation == 0 or orientation is None or raw_w <= 0 or raw_h <= 0:
        return df
    df = df.copy()
    display_w = raw_h if orientation in (90, 270) else raw_w
    display_h = raw_w if orientation in (90, 270) else raw_h
    for col in list(df.columns):
        suffix = col[-1]
        if suffix not in ("X", "x"):
            continue
        y_col = col[:-1] + ("Y" if suffix == "X" else "y")
        if y_col not in df.columns:
            continue
        x = pd.to_numeric(df[col], errors="coerce").values
        y = pd.to_numeric(df[y_col], errors="coerce").values
        is_pixel = float(np.nanmax(np.abs(x))) > 1.5 or float(np.nanmax(np.abs(y))) > 1.5
        if is_pixel:
            xn, yn = x / raw_w, y / raw_h
        else:
            xn, yn = x, y
        if orientation == 90:
            # 90 degrees clockwise: (x, y) -> (1 - y, x)
            x2n, y2n = 1 - yn, xn
        elif orientation == 270:
            # 270 degrees clockwise / 90 CCW: (x, y) -> (y, 1 - x)
            x2n, y2n = yn, 1 - xn
        elif orientation == 180:
            x2n, y2n = 1 - xn, 1 - yn
        else:
            continue
        if is_pixel:
            df[col] = x2n * display_w
            df[y_col] = y2n * display_h
        else:
            df[col] = x2n
            df[y_col] = y2n
    return df


def _opencv_stream_size(video_path: Optional[Path]) -> Tuple[float, float]:
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        w = float(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0)
        h = float(int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0)
        cap.release()
        return w, h
    except Exception:
        return 0.0, 0.0


def _served_video_dims(orientation: int, raw_w: float, raw_h: float) -> Tuple[float, float]:
    if orientation in (90, 270):
        return float(raw_h), float(raw_w)
    return float(raw_w), float(raw_h)


def _needs_portrait_to_landscape_remap(
    analysis: Optional[Dict[str, Any]],
    orientation: int,
    served_w: float,
    served_h: float,
    raw_w: float,
    raw_h: float,
) -> bool:
    """Extract rotate_cw analyzes portrait; browser plays landscape original."""
    if served_w <= 0 or served_h <= 0:
        return False
    if orientation not in (0, 180):
        return False
    if served_w <= served_h:
        return False

    aw = float((analysis or {}).get("frame_width_px") or 0)
    ah = float((analysis or {}).get("frame_height_px") or 0)
    if aw > 0 and ah > 0 and aw < ah:
        return True

    if analysis and (analysis.get("orientation_corrected") or analysis.get("pose_rotation_applied")):
        return True

    # WhatsApp / phone clips stored landscape but analyzed after rotate_cw.
    if raw_w > raw_h * 1.15:
        return True
    return False


def _portrait_norm_to_landscape_norm(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Inverse of extract rotate_cw (90° CW): portrait (xp, yp) -> landscape (xl, yl)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return y.copy(), 1.0 - x


def _remap_df_portrait_to_landscape(df: pd.DataFrame, src_w: float, src_h: float) -> pd.DataFrame:
    df = df.copy()
    src_w = max(float(src_w), 1.0)
    src_h = max(float(src_h), 1.0)
    pairs: List[Tuple[str, str]] = []
    for col in list(df.columns):
        if col.endswith("_imgX"):
            y_col = col[:-5] + "_imgY"
            if y_col in df.columns:
                pairs.append((col, y_col))
        elif col.endswith("_imgx"):
            y_col = col[:-5] + "_imgy"
            if y_col in df.columns:
                pairs.append((col, y_col))
        elif col.endswith("_X"):
            y_col = col[:-1] + "Y"
            if y_col in df.columns:
                pairs.append((col, y_col))
        elif col.endswith("_x") and not col.endswith("_imgx"):
            y_col = col[:-1] + "y"
            if y_col in df.columns:
                pairs.append((col, y_col))
    seen = set()
    for x_col, y_col in pairs:
        key = (x_col, y_col)
        if key in seen:
            continue
        seen.add(key)
        x = pd.to_numeric(df[x_col], errors="coerce").values.astype(float)
        y = pd.to_numeric(df[y_col], errors="coerce").values.astype(float)
        is_pixel = np.nanmax(np.abs(x)) > 1.5 or np.nanmax(np.abs(y)) > 1.5
        if is_pixel:
            xn = x / src_w
            yn = y / src_h
        else:
            xn, yn = x, y
        x2, y2 = _portrait_norm_to_landscape_norm(xn, yn)
        df[x_col] = x2
        df[y_col] = y2
    return df


def _remap_xy_norm_portrait_to_landscape(
    x: np.ndarray,
    y: np.ndarray,
    *,
    src_w: float,
    src_h: float,
) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    src_w = max(float(src_w), 1.0)
    src_h = max(float(src_h), 1.0)
    if np.nanmax(np.abs(x)) > 1.5 or np.nanmax(np.abs(y)) > 1.5:
        x = x / src_w
        y = y / src_h
    return _portrait_norm_to_landscape_norm(x, y)


def _rotate_frame_to_display(frame: np.ndarray, orientation: int) -> np.ndarray:
    """Rotate a raw video frame to the displayed orientation."""
    if orientation == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if orientation == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if orientation == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    return frame


def _frame_to_display(frame: np.ndarray, orientation: int) -> np.ndarray:
    """Return the frame in displayed orientation.

    Handles OpenCV/FFmpeg backends that auto-rotate based on orientation metadata.
    For 90/270 videos, if the frame is already portrait we leave it as-is; otherwise
    we rotate it manually.
    """
    h, w = frame.shape[:2]
    if orientation in (90, 270):
        # Displayed orientation is portrait (h > w); raw is landscape.
        if h > w:
            return frame
        return _rotate_frame_to_display(frame, orientation)
    # For 0/180, the displayed orientation matches the raw frame orientation.
    return _rotate_frame_to_display(frame, orientation)


def _detect_table_front_edge(
    video_path: str,
    orientation: int,
    raw_w: float,
    raw_h: float,
    n_samples: int = 5,
) -> Optional[Dict[str, Any]]:
    """Detect the blue table top and return its front (camera-side) edge.

    Returns a dict with:
        - edge_y: np.ndarray of normalized front-edge y indexed by column.
        - display_w, display_h: dimensions of the displayed frame.
        - mask: binary mask of the table top (last sampled frame).
        - front_edge_y: representative global front-edge y.
    Returns None if the table cannot be detected.
    """
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    try:
        # Disable backend auto-rotation; we handle orientation manually.
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    except Exception:
        pass
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if n <= 0:
        cap.release()
        return None
    indices = sorted({0, max(1, n // 4), max(2, n // 2), max(3, (3 * n) // 4), max(0, n - 1)})

    edge_arrays = []
    last_mask: Optional[np.ndarray] = None
    display_w: Optional[int] = None
    display_h: Optional[int] = None

    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        disp = _frame_to_display(frame, orientation)
        h, w = disp.shape[:2]
        display_w, display_h = w, h
        hsv = cv2.cvtColor(disp, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([90, 40, 40]), np.array([140, 255, 255]))
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        min_area = (h * w) * 0.03
        candidates = [c for c in contours if cv2.contourArea(c) >= min_area]
        if not candidates:
            continue
        cnt = max(candidates, key=cv2.contourArea)
        cmask = np.zeros_like(mask)
        cv2.drawContours(cmask, [cnt], -1, 255, -1)
        ys, xs = np.where(cmask > 0)
        if len(xs) == 0:
            continue
        edge_y = np.full(w, -1, dtype=float)
        np.maximum.at(edge_y, xs, ys)
        edge_arrays.append(edge_y)
        last_mask = cmask
    cap.release()

    if not edge_arrays or last_mask is None or display_w is None or display_h is None:
        return None

    edge_stack = np.where(np.stack(edge_arrays, axis=0) >= 0, np.stack(edge_arrays, axis=0), np.nan)
    with np.errstate(invalid="ignore"):
        median_edge = np.nanmedian(edge_stack, axis=0)
    edge_y_norm = median_edge / display_h
    global_y = float(np.nanmedian(edge_y_norm))
    return {
        "edge_y": edge_y_norm,
        "display_w": display_w,
        "display_h": display_h,
        "mask": last_mask,
        "front_edge_y": global_y,
    }


def _detect_side_from_table(
    raw_df: pd.DataFrame,
    table_mask: np.ndarray,
    display_w: int,
    display_h: int,
) -> Optional[str]:
    """Pick the side whose wrist/elbow lies on the blue table top.

    That side is the one nearest to the camera for the reach-to-wipe task.
    """
    if table_mask is None or table_mask.size == 0 or display_w <= 0 or display_h <= 0:
        return None
    best_score = -1
    best_side: Optional[str] = None

    def _med(s: pd.Series) -> float:
        arr = pd.to_numeric(s, errors="coerce").values
        return float(np.nanmedian(arr)) if np.any(np.isfinite(arr)) else float("nan")

    for side in ("LEFT", "RIGHT"):
        ex = _med(_norm_series(raw_df, f"{side}_ELBOW", "x"))
        ey = _med(_norm_series(raw_df, f"{side}_ELBOW", "y"))
        wx = _med(_norm_series(raw_df, f"{side}_WRIST", "x"))
        wy = _med(_norm_series(raw_df, f"{side}_WRIST", "y"))
        if not np.isfinite(wx) or not np.isfinite(wy):
            continue
        score = 0
        xi = int(np.clip(round(wx * display_w), 0, display_w - 1))
        yi = int(np.clip(round(wy * display_h), 0, display_h - 1))
        if table_mask[yi, xi] > 0:
            score += 3
        if np.isfinite(ex) and np.isfinite(ey):
            xie = int(np.clip(round(ex * display_w), 0, display_w - 1))
            yie = int(np.clip(round(ey * display_h), 0, display_h - 1))
            if table_mask[yie, xie] > 0:
                score += 1
        if score > best_score:
            best_score = score
            best_side = side.lower()
    return best_side


def _norm_series(df: pd.DataFrame, name: str, coord: str) -> pd.Series:
    """Return normalized [0,1] image-space series for a MediaPipe-style landmark."""
    c_upper = coord.upper()
    c_lower = coord.lower()
    img_cols = [f"{name}_img{c_upper}", f"{name}_img{c_lower}"]
    for c in img_cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    cols = [f"{name}_{coord}", f"{name}_{c_upper}", f"{name.lower()}_{c_lower}"]
    for c in cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def _visibility(df: pd.DataFrame, name: str) -> pd.Series:
    """Return a visibility / presence score for a landmark (0..1)."""
    cols = [f"{name}_visibility", f"{name}_VISIBILITY", f"{name.lower()}_visibility"]
    for c in cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(1.0, index=df.index)


def _resample(col: pd.Series, old_t: np.ndarray, new_t: np.ndarray) -> np.ndarray:
    y = pd.to_numeric(col, errors="coerce").values
    if np.all(np.isnan(y)):
        return np.full(len(new_t), np.nan)
    mask = np.isfinite(y)
    if mask.sum() < 2:
        return np.full(len(new_t), np.nan)
    return np.interp(new_t, old_t[mask], y[mask])


def _hl_column_present(df: pd.DataFrame, aff: str, tip: str) -> bool:
    name = f"{aff}_HL_{tip}"
    return any(c in df.columns for c in (f"{name}_X", f"{name}_x"))


def _hl_overlay_pair(
    raw_df: pd.DataFrame,
    aff: str,
    tip: str,
    old_t: np.ndarray,
    new_t: np.ndarray,
    target_fs: float,
    frame_w: float,
    frame_h: float,
    *,
    filter_hz: float = 6.0,
    gap_max: int = 15,
) -> Tuple[np.ndarray, np.ndarray]:
    """Resample Hand Landmarker tip to overlay timeline (normalized 0–1)."""
    name = f"{aff}_HL_{tip}"
    x = _resample(_norm_series(raw_df, name, "x"), old_t, new_t)
    y = _resample(_norm_series(raw_df, name, "y"), old_t, new_t)
    if gap_max > 0:
        x = _interpolate_small_gaps(x, max_gap=gap_max)
        y = _interpolate_small_gaps(y, max_gap=gap_max)
    if filter_hz > 0:
        x = _butter_lowpass_filter(x, cutoff_hz=filter_hz, fs=target_fs, order=2)
        y = _butter_lowpass_filter(y, cutoff_hz=filter_hz, fs=target_fs, order=2)
    fw = max(float(frame_w), 1.0)
    fh = max(float(frame_h), 1.0)
    # Legacy CSVs stored pixel coords (lm * frame size); new CSVs store 0–1 normalized.
    if np.nanmax(x) > 1.5 or np.nanmax(y) > 1.5:
        x = x / fw
        y = y / fh
    return x, y


def _anchor_hl_tips_to_palm(
    tip_x: np.ndarray,
    tip_y: np.ndarray,
    hl_wrist_x: np.ndarray,
    hl_wrist_y: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    *,
    max_finger_len: float = 0.14,
    min_finger_len: float = 0.006,
    max_down_stretch: float = 0.12,
) -> Tuple[np.ndarray, np.ndarray]:
    """Anchor HL finger geometry to kinematic palm (pose/canon space)."""
    tx = np.asarray(tip_x, dtype=float).copy()
    ty = np.asarray(tip_y, dtype=float).copy()
    px = np.asarray(palm_x, dtype=float)
    py = np.asarray(palm_y, dtype=float)
    wx = np.asarray(hl_wrist_x, dtype=float)
    wy = np.asarray(hl_wrist_y, dtype=float)
    for i in range(len(tx)):
        if not (np.isfinite(px[i]) and np.isfinite(py[i])):
            tx[i] = np.nan
            ty[i] = np.nan
            continue
        if not (np.isfinite(tx[i]) and np.isfinite(ty[i])):
            continue
        if np.isfinite(wx[i]) and np.isfinite(wy[i]):
            dx = float(tx[i] - wx[i])
            dy = float(ty[i] - wy[i])
        else:
            dx = float(tx[i] - px[i])
            dy = float(ty[i] - py[i])
        dist = float(np.hypot(dx, dy))
        if dist > max_finger_len or dist < min_finger_len:
            tx[i] = np.nan
            ty[i] = np.nan
            continue
        tip_xn = float(px[i] + dx)
        tip_yn = float(py[i] + dy)
        if tip_yn - float(py[i]) > max_down_stretch:
            tx[i] = np.nan
            ty[i] = np.nan
            continue
        if not (0.0 <= tip_xn <= 1.0 and 0.0 <= tip_yn <= 1.0):
            tx[i] = np.nan
            ty[i] = np.nan
            continue
        tx[i] = tip_xn
        ty[i] = tip_yn
    return tx, ty


def _ema_smooth_array(x: np.ndarray, alpha: float = 0.38) -> np.ndarray:
    out = np.asarray(x, dtype=float).copy()
    prev = np.nan
    for i in range(len(out)):
        if not np.isfinite(out[i]):
            continue
        if np.isfinite(prev):
            out[i] = alpha * out[i] + (1.0 - alpha) * prev
        prev = out[i]
    return out


def _forward_hold_array(x: np.ndarray, max_hold: int = 14) -> np.ndarray:
    out = np.asarray(x, dtype=float).copy()
    last = np.nan
    hold = 0
    for i in range(len(out)):
        if np.isfinite(out[i]):
            last = out[i]
            hold = 0
        elif np.isfinite(last) and hold < max_hold:
            out[i] = last
            hold += 1
    return out


def _hl_offset_series(
    tip_x: np.ndarray,
    tip_y: np.ndarray,
    ref_x: np.ndarray,
    ref_y: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    *,
    max_finger_len: float = 0.16,
    min_finger_len: float = 0.005,
    max_down_stretch: float = 0.13,
    max_down_per_frame: Optional[np.ndarray] = None,
    max_wrist_palm_dist: float = 0.095,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """HL tip offset from palm; per-frame validity 1=accepted raw HL."""
    n = len(palm_x)
    dx = np.full(n, np.nan)
    dy = np.full(n, np.nan)
    valid = np.zeros(n)
    for i in range(n):
        if not (
            np.isfinite(tip_x[i])
            and np.isfinite(tip_y[i])
            and np.isfinite(palm_x[i])
            and np.isfinite(palm_y[i])
        ):
            continue
        px = float(palm_x[i])
        py = float(palm_y[i])
        rx = float(ref_x[i]) if np.isfinite(ref_x[i]) else px
        ry = float(ref_y[i]) if np.isfinite(ref_y[i]) else py
        if np.isfinite(ref_x[i]) and np.isfinite(ref_y[i]):
            if float(np.hypot(rx - px, ry - py)) > max_wrist_palm_dist:
                continue
            rx = 0.35 * px + 0.65 * rx
            ry = 0.35 * py + 0.65 * ry
        odx = float(tip_x[i] - rx)
        ody = float(tip_y[i] - ry)
        dist = float(np.hypot(odx, ody))
        if dist > max_finger_len or dist < min_finger_len:
            continue
        tip_xn = px + odx
        tip_yn = py + ody
        down_lim = float(max_down_stretch)
        if max_down_per_frame is not None and i < len(max_down_per_frame) and np.isfinite(max_down_per_frame[i]):
            down_lim = float(max_down_per_frame[i])
        if tip_yn - py > down_lim:
            continue
        if not (0.0 <= tip_xn <= 1.0 and 0.0 <= tip_yn <= 1.0):
            continue
        dx[i] = odx
        dy[i] = ody
        valid[i] = 1.0
    return dx, dy, valid


def _palm_step_speed(palm_x: np.ndarray, palm_y: np.ndarray) -> np.ndarray:
    n = len(palm_x)
    speed = np.zeros(n)
    for i in range(1, n):
        if np.isfinite(palm_x[i]) and np.isfinite(palm_y[i]) and np.isfinite(palm_x[i - 1]) and np.isfinite(palm_y[i - 1]):
            speed[i] = float(np.hypot(palm_x[i] - palm_x[i - 1], palm_y[i] - palm_y[i - 1]))
    return speed


def _adaptive_down_stretch(
    palm_y: np.ndarray,
    table_surface_y: Optional[float],
) -> np.ndarray:
    n = len(palm_y)
    out = np.full(n, 0.11)
    if table_surface_y is None or not np.isfinite(table_surface_y):
        return out
    table_y = float(table_surface_y)
    for i in range(n):
        if not np.isfinite(palm_y[i]):
            continue
        py = float(palm_y[i])
        if py < table_y - 0.10:
            out[i] = 0.055
        elif abs(py - table_y) < 0.07:
            out[i] = 0.14
        else:
            out[i] = 0.09
    return out


def _adaptive_hold_frames(palm_speed: np.ndarray, base: int = 12) -> np.ndarray:
    holds = np.full(len(palm_speed), base, dtype=int)
    for i, sp in enumerate(palm_speed):
        if sp > 0.014:
            holds[i] = 2
        elif sp > 0.008:
            holds[i] = 5
        elif sp > 0.004:
            holds[i] = 8
    return holds


def _forward_hold_variable(x: np.ndarray, max_hold_arr: np.ndarray) -> np.ndarray:
    out = np.asarray(x, dtype=float).copy()
    last = np.nan
    hold = 0
    limit = 12
    for i in range(len(out)):
        limit = int(max_hold_arr[i]) if i < len(max_hold_arr) else 12
        if np.isfinite(out[i]):
            last = out[i]
            hold = 0
        elif np.isfinite(last) and hold < limit:
            out[i] = last
            hold += 1
    return out


def _stabilize_hl_finger_tip(
    hl_tip_x: np.ndarray,
    hl_tip_y: np.ndarray,
    hl_wx: np.ndarray,
    hl_wy: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    pose_tip_x: np.ndarray,
    pose_tip_y: np.ndarray,
    *,
    ema_alpha: float = 0.38,
    max_hold: int = 12,
    gap_interp: int = 15,
    max_down_per_frame: Optional[np.ndarray] = None,
    hold_per_frame: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Smooth HL offsets anchored to palm; pose fallback when HL missing."""
    raw_dx, raw_dy, hl_valid = _hl_offset_series(
        hl_tip_x, hl_tip_y, hl_wx, hl_wy, palm_x, palm_y,
        max_down_per_frame=max_down_per_frame,
    )
    raw_dx = _interpolate_small_gaps(raw_dx, max_gap=gap_interp)
    raw_dy = _interpolate_small_gaps(raw_dy, max_gap=gap_interp)
    if hold_per_frame is not None:
        smooth_dx = _forward_hold_variable(_ema_smooth_array(raw_dx, ema_alpha), hold_per_frame)
        smooth_dy = _forward_hold_variable(_ema_smooth_array(raw_dy, ema_alpha), hold_per_frame)
    else:
        smooth_dx = _forward_hold_array(_ema_smooth_array(raw_dx, ema_alpha), max_hold)
        smooth_dy = _forward_hold_array(_ema_smooth_array(raw_dy, ema_alpha), max_hold)

    pose_dx = np.asarray(pose_tip_x, dtype=float) - np.asarray(palm_x, dtype=float)
    pose_dy = np.asarray(pose_tip_y, dtype=float) - np.asarray(palm_y, dtype=float)
    pose_dx = _forward_hold_array(
        _ema_smooth_array(_interpolate_small_gaps(pose_dx, max_gap=gap_interp), 0.45),
        6,
    )
    pose_dy = _forward_hold_array(
        _ema_smooth_array(_interpolate_small_gaps(pose_dy, max_gap=gap_interp), 0.45),
        6,
    )

    n = len(palm_x)
    out_x = np.full(n, np.nan)
    out_y = np.full(n, np.nan)
    conf = np.zeros(n)
    for i in range(n):
        if not (np.isfinite(palm_x[i]) and np.isfinite(palm_y[i])):
            continue
        if np.isfinite(smooth_dx[i]) and np.isfinite(smooth_dy[i]):
            out_x[i] = palm_x[i] + smooth_dx[i]
            out_y[i] = palm_y[i] + smooth_dy[i]
            conf[i] = 1.0 if hl_valid[i] > 0 else 0.72
        elif np.isfinite(pose_dx[i]) and np.isfinite(pose_dy[i]):
            out_x[i] = palm_x[i] + pose_dx[i]
            out_y[i] = palm_y[i] + pose_dy[i]
            conf[i] = 0.42
    return out_x, out_y, conf


def _direct_hl_joint(
    hl_x: np.ndarray,
    hl_y: np.ndarray,
    hl_wx: np.ndarray,
    hl_wy: np.ndarray,
    anchor_x: np.ndarray,
    anchor_y: np.ndarray,
    *,
    joint_kind: str = "tip",
    max_hl_anchor_dist: float = 0.12,
    ema_alpha: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """HL joint offset from HL wrist, anchored to pose wrist (same space as imgX body)."""
    reach = {
        "mcp": (0.002, 0.12),
        "ip": (0.002, 0.17),
        "tip": (0.003, 0.22),
    }
    min_len, max_len = reach.get(joint_kind, reach["tip"])
    n = len(hl_x)
    out_x = np.full(n, np.nan)
    out_y = np.full(n, np.nan)
    conf = np.zeros(n)
    prev_x = np.nan
    prev_y = np.nan
    for i in range(n):
        jx_raw = float(hl_x[i]) if np.isfinite(hl_x[i]) else np.nan
        jy_raw = float(hl_y[i]) if np.isfinite(hl_y[i]) else np.nan
        if not (np.isfinite(jx_raw) and np.isfinite(jy_raw)):
            prev_x = np.nan
            prev_y = np.nan
            continue
        if not (np.isfinite(anchor_x[i]) and np.isfinite(anchor_y[i])):
            prev_x = np.nan
            prev_y = np.nan
            continue
        if not (np.isfinite(hl_wx[i]) and np.isfinite(hl_wy[i])):
            prev_x = np.nan
            prev_y = np.nan
            continue
        if float(np.hypot(hl_wx[i] - anchor_x[i], hl_wy[i] - anchor_y[i])) > max_hl_anchor_dist:
            prev_x = np.nan
            prev_y = np.nan
            continue
        dist = float(np.hypot(jx_raw - hl_wx[i], jy_raw - hl_wy[i]))
        if dist > max_len or dist < min_len:
            prev_x = np.nan
            prev_y = np.nan
            continue
        jx = float(anchor_x[i] + (jx_raw - hl_wx[i]))
        jy = float(anchor_y[i] + (jy_raw - hl_wy[i]))
        if not (0.001 <= jx <= 0.999 and 0.001 <= jy <= 0.999):
            prev_x = np.nan
            prev_y = np.nan
            continue
        if np.isfinite(prev_x) and np.isfinite(prev_y):
            jx = ema_alpha * jx + (1.0 - ema_alpha) * prev_x
            jy = ema_alpha * jy + (1.0 - ema_alpha) * prev_y
        out_x[i] = jx
        out_y[i] = jy
        conf[i] = 1.0
        prev_x, prev_y = jx, jy
    return out_x, out_y, conf


def _direct_hl_finger_tip(
    hl_tip_x: np.ndarray,
    hl_tip_y: np.ndarray,
    hl_wx: np.ndarray,
    hl_wy: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    **kwargs,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _direct_hl_joint(
        hl_tip_x, hl_tip_y, hl_wx, hl_wy, palm_x, palm_y, joint_kind="tip", **kwargs,
    )


_FINGER_HL_JOINTS: Dict[str, list] = {
    "thumb": [("mcp", "THUMB_MCP"), ("ip", "THUMB_IP"), ("tip", "THUMB_TIP")],
    "index": [("mcp", "INDEX_MCP"), ("ip", "INDEX_PIP"), ("tip", "INDEX_TIP")],
    "middle": [("mcp", "MIDDLE_MCP"), ("ip", "MIDDLE_PIP"), ("tip", "MIDDLE_TIP")],
    "ring": [("mcp", "RING_MCP"), ("ip", "RING_PIP"), ("tip", "RING_TIP")],
    "pinky": [("mcp", "PINKY_MCP"), ("ip", "PINKY_PIP"), ("tip", "PINKY_TIP")],
}

_HL_GAP_MAX = 5


def _pick_hl_side_window(
    raw_df: pd.DataFrame,
    aff: str,
    opp: str,
    old_t: np.ndarray,
    new_t: np.ndarray,
    target_fs: float,
    frame_w: float,
    frame_h: float,
    start: int,
    end: int,
    palm_x: Optional[np.ndarray] = None,
    palm_y: Optional[np.ndarray] = None,
    wrist_x: Optional[np.ndarray] = None,
    wrist_y: Optional[np.ndarray] = None,
) -> Tuple[Optional[str], float]:
    """Lock HL handedness — prefer affected side when wrist proximity agrees."""
    best_side = None
    best_score = -1e9
    for cand in (aff, opp):
        if not _hl_column_present(raw_df, cand, "INDEX_TIP"):
            continue
        cx, cy = _hl_overlay_pair(
            raw_df, cand, "INDEX_TIP", old_t, new_t, target_fs, frame_w, frame_h, filter_hz=0.0,
        )
        cov = _hl_overlay_coverage(cx, cy, start, end)
        score = cov
        if wrist_x is not None and wrist_y is not None and _hl_column_present(raw_df, cand, "WRIST"):
            wx, wy = _hl_overlay_pair(
                raw_df, cand, "WRIST", old_t, new_t, target_fs, frame_w, frame_h, filter_hz=0.0,
            )
            dists = []
            seg = slice(max(0, start), min(len(wrist_x), end + 1))
            for i in range(seg.start, seg.stop):
                if not (np.isfinite(wx[i]) and np.isfinite(wy[i]) and np.isfinite(wrist_x[i]) and np.isfinite(wrist_y[i])):
                    continue
                dists.append(float(np.hypot(wx[i] - wrist_x[i], wy[i] - wrist_y[i])))
            if dists:
                med = float(np.median(dists))
                if med <= 0.07:
                    score += 0.35
                elif med > 0.12:
                    score -= 0.45
        if cand == aff:
            score += 0.08
        if score > best_score:
            best_score = score
            best_side = cand
    best_cov = 0.0
    if best_side:
        cx, cy = _hl_overlay_pair(
            raw_df, best_side, "INDEX_TIP", old_t, new_t, target_fs, frame_w, frame_h, filter_hz=0.0,
        )
        best_cov = _hl_overlay_coverage(cx, cy, start, end)
    return best_side, best_cov


def _stabilize_hl_finger_overlay(
    raw_df: pd.DataFrame,
    hl_side: str,
    old_t: np.ndarray,
    new_t: np.ndarray,
    target_fs: float,
    frame_w: float,
    frame_h: float,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    pose_fingers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    wrist_x: np.ndarray,
    wrist_y: np.ndarray,
    *,
    table_surface_y: Optional[float] = None,
    start: int = 0,
    end: int = 0,
    shoulder_width_norm: Optional[float] = None,
) -> Tuple[
    Dict[str, Tuple[np.ndarray, np.ndarray]],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    Dict[str, np.ndarray],
    Dict[str, Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]],
]:
    """Direct HL joints (MCP, IP, TIP) — no synthetic bones; short gap fill only."""
    hl_wx = np.asarray(palm_x, dtype=float)
    hl_wy = np.asarray(palm_y, dtype=float)
    if _hl_column_present(raw_df, hl_side, "WRIST"):
        hl_wx, hl_wy = _hl_overlay_pair(
            raw_df, hl_side, "WRIST", old_t, new_t, target_fs, frame_w, frame_h,
            filter_hz=0.0, gap_max=_HL_GAP_MAX,
        )

    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    vis: Dict[str, np.ndarray] = {}
    joints: Dict[str, Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    conf_stack = []
    index_conf = np.zeros(len(palm_x))

    for finger_id, joint_specs in _FINGER_HL_JOINTS.items():
        joints[finger_id] = {}
        tip_x = np.full(len(palm_x), np.nan)
        tip_y = np.full(len(palm_y), np.nan)
        tip_c = np.zeros(len(palm_x))
        for jname, hl_name in joint_specs:
            if _hl_column_present(raw_df, hl_side, hl_name):
                jx, jy = _hl_overlay_pair(
                    raw_df, hl_side, hl_name, old_t, new_t, target_fs, frame_w, frame_h,
                    filter_hz=0.0, gap_max=_HL_GAP_MAX,
                )
            elif jname == "tip" and _hl_column_present(raw_df, hl_side, hl_name):
                jx, jy = _hl_overlay_pair(
                    raw_df, hl_side, hl_name, old_t, new_t, target_fs, frame_w, frame_h,
                    filter_hz=0.0, gap_max=_HL_GAP_MAX,
                )
            else:
                jx = np.full(len(palm_x), np.nan)
                jy = np.full(len(palm_y), np.nan)
            ox, oy, c = _direct_hl_joint(
                jx, jy, hl_wx, hl_wy, wrist_x, wrist_y, joint_kind=jname,
            )
            joints[finger_id][jname] = (ox, oy, c)
            if jname == "tip":
                tip_x, tip_y, tip_c = ox, oy, c
        out[finger_id] = (tip_x, tip_y)
        vis[finger_id] = tip_c.copy()
        conf_stack.append(tip_c)
        if finger_id == "index":
            index_conf = tip_c

    if conf_stack:
        finger_track_conf = np.mean(np.stack(conf_stack, axis=0), axis=0)
    else:
        finger_track_conf = np.zeros(len(palm_x))
    return out, finger_track_conf, index_conf, hl_wx, hl_wy, vis, joints


def _clamp_finger_bone_lengths(
    fingers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    conf: np.ndarray,
    *,
    start: int,
    end: int,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Clamp only excessive finger reach; never shrink valid spread toward palm."""
    keys = ("index", "middle", "ring", "pinky", "thumb")
    lens: Dict[str, list] = {k: [] for k in keys}
    seg = slice(max(0, start), min(len(palm_x), end + 1))
    for i in range(seg.start, seg.stop):
        if conf[i] < 0.72:
            continue
        if not (np.isfinite(palm_x[i]) and np.isfinite(palm_y[i])):
            continue
        for key in keys:
            ox, oy = fingers[key]
            if np.isfinite(ox[i]) and np.isfinite(oy[i]):
                d = float(np.hypot(ox[i] - palm_x[i], oy[i] - palm_y[i]))
                if d >= 0.035:
                    lens[key].append(d)
    med = {}
    for key in keys:
        if lens[key]:
            med[key] = float(np.median(lens[key]))
    if not med:
        return fingers
    out = {k: (np.asarray(v[0], dtype=float).copy(), np.asarray(v[1], dtype=float).copy()) for k, v in fingers.items()}
    for key in keys:
        if key not in med:
            continue
        target = med[key]
        ox, oy = out[key]
        for i in range(len(palm_x)):
            if not (np.isfinite(ox[i]) and np.isfinite(oy[i]) and np.isfinite(palm_x[i]) and np.isfinite(palm_y[i])):
                continue
            dx = ox[i] - palm_x[i]
            dy = oy[i] - palm_y[i]
            dist = float(np.hypot(dx, dy))
            if dist <= 1e-6:
                continue
            if dist > target * 1.45:
                scale = (target * 1.45) / dist
                ox[i] = palm_x[i] + dx * scale
                oy[i] = palm_y[i] + dy * scale
    return out


_ANATOMY_FINGER_BONES: Dict[str, Dict[str, float]] = {
    "thumb": {"angle": -0.72, "mcp": 0.032, "pip": 0.024, "dip": 0.020, "tip": 0.018},
    "index": {"angle": -0.20, "mcp": 0.042, "pip": 0.036, "dip": 0.030, "tip": 0.028},
    "middle": {"angle": 0.0, "mcp": 0.046, "pip": 0.040, "dip": 0.034, "tip": 0.032},
    "ring": {"angle": 0.18, "mcp": 0.044, "pip": 0.038, "dip": 0.032, "tip": 0.030},
    "pinky": {"angle": 0.36, "mcp": 0.038, "pip": 0.032, "dip": 0.028, "tip": 0.024},
}


def _rotate_unit_xy(fx: float, fy: float, ang: float) -> Tuple[float, float]:
    c = float(np.cos(ang))
    s = float(np.sin(ang))
    return fx * c - fy * s, fx * s + fy * c


def _hand_forward_axes(ex: float, ey: float, px: float, py: float) -> Optional[Tuple[float, float, float, float]]:
    fx = px - ex
    fy = py - ey
    norm = float(np.hypot(fx, fy))
    if norm < 1e-6:
        return None
    fx /= norm
    fy /= norm
    return fx, fy, -fy, fx


def _finger_spread_at(
    fingers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    i: int,
) -> float:
    best = 0.0
    for key in _ANATOMY_FINGER_BONES:
        ox, oy = fingers[key]
        if np.isfinite(ox[i]) and np.isfinite(oy[i]) and np.isfinite(palm_x[i]) and np.isfinite(palm_y[i]):
            best = max(best, float(np.hypot(ox[i] - palm_x[i], oy[i] - palm_y[i])))
    return best


def _expand_collapsed_hand_anatomy(
    fingers: Dict[str, Tuple[np.ndarray, np.ndarray]],
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    elbow_x: np.ndarray,
    elbow_y: np.ndarray,
    *,
    min_spread: float = 0.038,
    shoulder_width_norm: Optional[float] = None,
    finger_track_conf: Optional[np.ndarray] = None,
) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Fill collapsed finger tips using open-hand skeleton template (clinical anatomy ref)."""
    out = {k: (np.asarray(v[0], dtype=float).copy(), np.asarray(v[1], dtype=float).copy()) for k, v in fingers.items()}
    scale_base = 1.0
    if shoulder_width_norm and shoulder_width_norm > 0:
        scale_base = float(np.clip(shoulder_width_norm * 0.55, 0.78, 1.22))
    for i in range(len(palm_x)):
        if not (np.isfinite(palm_x[i]) and np.isfinite(palm_y[i])):
            continue
        if finger_track_conf is not None and i < len(finger_track_conf) and np.isfinite(finger_track_conf[i]):
            if float(finger_track_conf[i]) >= 0.48:
                continue
        if _finger_spread_at(out, palm_x, palm_y, i) >= min_spread:
            continue
        if not (np.isfinite(elbow_x[i]) and np.isfinite(elbow_y[i])):
            continue
        axes = _hand_forward_axes(float(elbow_x[i]), float(elbow_y[i]), float(palm_x[i]), float(palm_y[i]))
        if axes is None:
            continue
        fx, fy, px, py = axes
        for key, spec in _ANATOMY_FINGER_BONES.items():
            dx, dy = _rotate_unit_xy(fx, fy, spec["angle"])
            span = (spec["mcp"] + spec["pip"] + spec["dip"] + spec["tip"]) * scale_base
            ox, oy = out[key]
            ox[i] = float(palm_x[i] + dx * span + px * spec["angle"] * 0.015 * scale_base)
            oy[i] = float(palm_y[i] + dy * span + py * spec["angle"] * 0.015 * scale_base)
    return out


def _pose_finger_overlay_pair(
    raw_df: pd.DataFrame,
    lm_name: str,
    old_t: np.ndarray,
    new_t: np.ndarray,
    target_fs: float,
    frame_w: float,
    frame_h: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Pose INDEX/THUMB/PINKY in normalized image space (prefer *_imgX columns)."""
    img_x = f"{lm_name}_imgX"
    img_y = f"{lm_name}_imgY"
    if img_x in raw_df.columns and img_y in raw_df.columns:
        x = _resample(pd.to_numeric(raw_df[img_x], errors="coerce"), old_t, new_t)
        y = _resample(pd.to_numeric(raw_df[img_y], errors="coerce"), old_t, new_t)
    else:
        x = _resample(_norm_series(raw_df, lm_name, "x"), old_t, new_t)
        y = _resample(_norm_series(raw_df, lm_name, "y"), old_t, new_t)
        fw = max(float(frame_w), 1.0)
        fh = max(float(frame_h), 1.0)
        if np.nanmax(np.abs(x)) > 1.5 or np.nanmax(np.abs(y)) > 1.5:
            x = x / fw
            y = y / fh
        else:
            x = np.clip(x, 0.0, 1.0)
            y = np.clip(y, 0.0, 1.0)
    x = _interpolate_small_gaps(x, max_gap=15)
    y = _interpolate_small_gaps(y, max_gap=15)
    return x, y


def _hl_overlay_coverage(x: np.ndarray, y: np.ndarray, start: int = 0, end: Optional[int] = None) -> float:
    if len(x) == 0:
        return 0.0
    if end is None:
        end = len(x) - 1
    seg = np.isfinite(x[start : end + 1]) & np.isfinite(y[start : end + 1])
    if len(seg) == 0:
        return 0.0
    return float(seg.mean())


def _smooth_pairs(x: np.ndarray, y: np.ndarray, window: int = 5):
    """Apply a simple centered moving average to reduce skeleton jitter."""
    if len(x) < window or window < 2:
        return x, y
    kernel = np.ones(window) / window
    sx = np.convolve(x, kernel, mode="same")
    sy = np.convolve(y, kernel, mode="same")
    # Preserve endpoints to avoid boundary drift.
    sx[: window // 2] = x[: window // 2]
    sx[-(window // 2) :] = x[-(window // 2) :]
    sy[: window // 2] = y[: window // 2]
    sy[-(window // 2) :] = y[-(window // 2) :]
    return sx, sy


def build_overlay_data(
    csv_path: str,
    analysis: Optional[Dict[str, Any]] = None,
    affected_side: str = "auto",
    target_fs: float = 60.0,
    video_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build compact per-frame overlay data from a landmarks CSV.

    Returns:
        {
          "fps": float,
          "duration_sec": float,
          "affected_side": str,
          "frames": [{
              "time": float,
              "speed": float,
              "palm": [x, y] | null,
              "wrist": [x, y] | null,
              "shoulder": [x, y] | null,
              "elbow": [x, y] | null,
              "trunk": [x, y] | null,
              "nose": [x, y] | null,
              ...
          }],
          "metrics": {...},
          "movement_window": {"start_idx": int, "end_idx": int},
          "peak_velocity_px_s": float,
          "velocity_profile": {"t": [...], "v": [...]},
          "start_palm": [x, y] | null,
          "end_palm": [x, y] | null,
        }
    """
    try:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            return {"error": f"CSV not found: {csv_path}"}

        df = pd.read_csv(csv_path)
        if len(df) < 2:
            return {"error": "Too few frames"}

        # Use raw pose CSV (if available) for full skeleton landmarks; otherwise
        # fall back to the provided CSV (which may already be the raw pose file).
        raw_csv_path = csv_path.with_name(csv_path.name.replace(".csv", "_raw_pose.csv"))
        if raw_csv_path == csv_path:
            raw_csv_path = csv_path.with_name(csv_path.name.replace("_raw_pose.csv", "_raw_pose.csv"))
        if not raw_csv_path.exists():
            raw_csv_path = csv_path
        raw_df = pd.read_csv(raw_csv_path) if raw_csv_path.exists() else df

        resolved_video_path = None
        if video_path:
            resolved_video_path = Path(video_path)
        else:
            resolved_video_path = find_video_for_csv(str(csv_path))

        # Use the SAME video file the browser plays (usually post-rotation MP4).
        orientation, raw_w, raw_h = _video_orientation_and_dims(resolved_video_path)
        raw_df = _rotate_xy(raw_df, orientation, raw_w, raw_h)
        display_swapped = orientation in (90, 270)
        analysis_src_w = float((analysis or {}).get("frame_width_px") or 0)
        analysis_src_h = float((analysis or {}).get("frame_height_px") or 0)
        served_w, served_h = _served_video_dims(orientation, raw_w, raw_h)
        from overlay_coord_diag import (
            apply_transform_df,
            apply_transform_df_hl_only,
            apply_transform_norm,
            detect_hl_coord_transform,
            detect_overlay_coord_transform,
        )

        transform_diag = detect_overlay_coord_transform(
            raw_df,
            orientation=orientation,
            raw_w=raw_w,
            raw_h=raw_h,
            served_w=served_w,
            served_h=served_h,
            analysis=analysis,
        )
        coord_transform = transform_diag.get("best_transform") or "none"
        coord_remap = None if coord_transform == "none" else coord_transform
        if coord_transform != "none":
            remap_src_w = analysis_src_w if analysis_src_w > 0 else float(raw_h)
            remap_src_h = analysis_src_h if analysis_src_h > 0 else float(raw_w)
            raw_df = apply_transform_df(raw_df, coord_transform, remap_src_w, remap_src_h)
        table_edge = None
        if resolved_video_path and resolved_video_path.exists():
            table_edge = _detect_table_front_edge(str(resolved_video_path), orientation, raw_w, raw_h)

        # Determine side — analysis result, kinematic fusion, then table tie-break.
        side = affected_side.lower() if affected_side else "auto"
        side_detection: Dict[str, Any] = {}
        if side not in ("left", "right"):
            analysis_side = (
                (analysis or {}).get("side_analyzed")
                or (analysis or {}).get("affected_side")
            )
            if analysis_side and str(analysis_side).lower() in ("left", "right"):
                side = str(analysis_side).lower()
                side_detection = {
                    "method": "analysis_result",
                    "confidence": float((analysis or {}).get("side_detection_confidence") or 1.0),
                }
        if side not in ("left", "right"):
            try:
                from mediapipe_csv_extractor import detect_active_arm_with_meta

                det = detect_active_arm_with_meta(
                    raw_df,
                    int(table_edge["display_w"]) if table_edge else 1920,
                    int(table_edge["display_h"]) if table_edge else 1080,
                    fs=target_fs,
                )
                side = det["side"]
                side_detection = {
                    "method": det.get("method", "kinematic_fusion"),
                    "confidence": det.get("confidence"),
                    "scores": det.get("scores"),
                }
                if float(det.get("confidence") or 0) < 0.2 and table_edge is not None:
                    table_side = _detect_side_from_table(
                        raw_df, table_edge["mask"], table_edge["display_w"], table_edge["display_h"]
                    )
                    if table_side in ("left", "right"):
                        side = table_side
                        side_detection["method"] = "table_contact_tiebreak"
            except Exception:
                pass
        if side not in ("left", "right"):
            side = "right"

        remap_src_w = analysis_src_w if analysis_src_w > 0 else float(raw_h if raw_w > raw_h else raw_w)
        remap_src_h = analysis_src_h if analysis_src_h > 0 else float(raw_w if raw_w > raw_h else raw_h)
        hl_aff = "RIGHT" if side == "right" else "LEFT"
        hl_transform_diag = detect_hl_coord_transform(
            raw_df,
            side=hl_aff,
            body_transform=coord_transform,
            analysis_src_w=analysis_src_w,
            analysis_src_h=analysis_src_h,
            raw_w=raw_w,
            raw_h=raw_h,
            served_w=served_w,
            served_h=served_h,
            analysis=analysis,
        )
        hl_coord_transform = hl_transform_diag.get("best_transform") or "none"
        if hl_coord_transform != "none" and hl_coord_transform != coord_transform:
            raw_df = apply_transform_df_hl_only(raw_df, hl_coord_transform, remap_src_w, remap_src_h)

        # Canonical time.
        if "time" in df.columns:
            t = pd.to_numeric(df["time"], errors="coerce").values
        else:
            t = np.arange(len(df)) / target_fs
        if np.isnan(t).any():
            t = np.arange(len(df)) / target_fs

        t0, t1 = float(t[0]), float(t[-1])
        if t1 <= t0:
            return {"error": "Invalid time range"}
        n_target = max(2, int(round((t1 - t0) * target_fs)) + 1)
        new_t = np.linspace(t0, t1, n_target)

        def _pair(name: str):
            x = _resample(_norm_series(raw_df, name, "x"), t, new_t)
            y = _resample(_norm_series(raw_df, name, "y"), t, new_t)
            vis = _resample(_visibility(raw_df, name), t, new_t)
            x = _interpolate_small_gaps(x, max_gap=15)
            y = _interpolate_small_gaps(y, max_gap=15)
            # No low-pass on overlay landmarks — Butterworth adds visible lag vs video.
            x[vis < 0.5] = np.nan
            y[vis < 0.5] = np.nan
            return x, y

        # Affected-side canonical points from the unified kinematics module.
        from unified_kinematics import load_canonical_landmarks, _compute_speed, _movement_window

        canon = load_canonical_landmarks(
            str(csv_path),
            affected_side=side,
            target_fs=target_fs,
            cutoff_hz=4.0,
            filter_order=4,
        )
        canon_tremor = load_canonical_landmarks(
            str(csv_path),
            affected_side=side,
            target_fs=target_fs,
            cutoff_hz=0.0,
            filter_order=4,
        )
        if len(canon) != len(new_t):
            canon_t = pd.to_numeric(canon["time"], errors="coerce").values
            for col in canon.columns:
                if col == "time":
                    continue
                canon[col] = np.interp(new_t, canon_t, pd.to_numeric(canon[col], errors="coerce").values)
        if len(canon_tremor) != len(new_t):
            ct_t = pd.to_numeric(canon_tremor["time"], errors="coerce").values
            for col in canon_tremor.columns:
                if col == "time":
                    continue
                canon_tremor[col] = np.interp(
                    new_t, ct_t, pd.to_numeric(canon_tremor[col], errors="coerce").values
                )

        canon = _rotate_xy(canon, orientation, raw_w, raw_h)
        canon_tremor = _rotate_xy(canon_tremor, orientation, raw_w, raw_h)

        # Overlay JSON frame size must match the video file the browser plays.
        frame_w = float(served_w)
        frame_h = float(served_h)
        if frame_w <= 0:
            frame_w = 640.0
        if frame_h <= 0:
            frame_h = 480.0

        palm_x_px = pd.to_numeric(canon.get("palm_x", pd.Series(np.nan)), errors="coerce").values
        palm_y_px = pd.to_numeric(canon.get("palm_y", pd.Series(np.nan)), errors="coerce").values
        shoulder_x_px = pd.to_numeric(canon.get("shoulder_x", pd.Series(np.nan)), errors="coerce").values
        shoulder_y_px = pd.to_numeric(canon.get("shoulder_y", pd.Series(np.nan)), errors="coerce").values

        remap_src_w = analysis_src_w if analysis_src_w > 0 else float(raw_h if raw_w > raw_h else raw_w)
        remap_src_h = analysis_src_h if analysis_src_h > 0 else float(raw_w if raw_w > raw_h else raw_h)

        if coord_transform != "none":
            palm_x, palm_y = apply_transform_norm(
                palm_x_px, palm_y_px, coord_transform, src_w=remap_src_w, src_h=remap_src_h,
            )
            wrist_x, wrist_y = apply_transform_norm(
                pd.to_numeric(canon.get("wrist_x", pd.Series(np.nan)), errors="coerce").values,
                pd.to_numeric(canon.get("wrist_y", pd.Series(np.nan)), errors="coerce").values,
                coord_transform,
                src_w=remap_src_w,
                src_h=remap_src_h,
            )
            shoulder_x, shoulder_y = apply_transform_norm(
                shoulder_x_px, shoulder_y_px, coord_transform, src_w=remap_src_w, src_h=remap_src_h,
            )
            elbow_x, elbow_y = apply_transform_norm(
                pd.to_numeric(canon.get("elbow_x", pd.Series(np.nan)), errors="coerce").values,
                pd.to_numeric(canon.get("elbow_y", pd.Series(np.nan)), errors="coerce").values,
                coord_transform,
                src_w=remap_src_w,
                src_h=remap_src_h,
            )
            trunk_x, trunk_y = apply_transform_norm(
                pd.to_numeric(canon.get("trunk_x", pd.Series(np.nan)), errors="coerce").values,
                pd.to_numeric(canon.get("trunk_y", pd.Series(np.nan)), errors="coerce").values,
                coord_transform,
                src_w=remap_src_w,
                src_h=remap_src_h,
            )
        else:
            palm_x = palm_x_px / frame_w
            palm_y = palm_y_px / frame_h
            wrist_x = pd.to_numeric(canon.get("wrist_x", pd.Series(np.nan)), errors="coerce").values / frame_w
            wrist_y = pd.to_numeric(canon.get("wrist_y", pd.Series(np.nan)), errors="coerce").values / frame_h
            shoulder_x = shoulder_x_px / frame_w
            shoulder_y = shoulder_y_px / frame_h
            elbow_x = pd.to_numeric(canon.get("elbow_x", pd.Series(np.nan)), errors="coerce").values / frame_w
            elbow_y = pd.to_numeric(canon.get("elbow_y", pd.Series(np.nan)), errors="coerce").values / frame_h
            trunk_x = pd.to_numeric(canon.get("trunk_x", pd.Series(np.nan)), errors="coerce").values / frame_w
            trunk_y = pd.to_numeric(canon.get("trunk_y", pd.Series(np.nan)), errors="coerce").values / frame_h

        # Keep shoulder_y_px in display-pixel units for elevation calculations.
        shoulder_y_px = shoulder_y_px

        speed = _compute_speed(canon, fs=target_fs)
        speed_tremor = _compute_speed(canon_tremor, fs=target_fs)
        tremor_palm_x = pd.to_numeric(canon_tremor.get("palm_x", pd.Series(np.nan)), errors="coerce").values
        tremor_palm_y = pd.to_numeric(canon_tremor.get("palm_y", pd.Series(np.nan)), errors="coerce").values
        tremor_index_x = None
        tremor_index_y = None
        if "index_x" in canon_tremor.columns:
            tremor_index_x = pd.to_numeric(canon_tremor["index_x"], errors="coerce").values
            tremor_index_y = pd.to_numeric(canon_tremor["index_y"], errors="coerce").values
        elbow_angle = None
        if {"shoulder_x", "shoulder_y", "elbow_x", "elbow_y", "wrist_x", "wrist_y"}.issubset(set(canon.columns)):
            sx = pd.to_numeric(canon["shoulder_x"], errors="coerce").values
            sy = pd.to_numeric(canon["shoulder_y"], errors="coerce").values
            ex = pd.to_numeric(canon["elbow_x"], errors="coerce").values
            ey = pd.to_numeric(canon["elbow_y"], errors="coerce").values
            wx = pd.to_numeric(canon["wrist_x"], errors="coerce").values
            wy = pd.to_numeric(canon["wrist_y"], errors="coerce").values
            v1x, v1y = sx - ex, sy - ey
            v2x, v2y = wx - ex, wy - ey
            dot = v1x * v2x + v1y * v2y
            norm1 = np.hypot(v1x, v1y)
            norm2 = np.hypot(v2x, v2y)
            cosang = dot / (norm1 * norm2 + 1e-9)
            cosang = np.clip(cosang, -1.0, 1.0)
            elbow_angle = np.degrees(np.arccos(cosang))

        shoulder_flexion = None
        if {"trunk_x", "trunk_y", "shoulder_x", "shoulder_y", "elbow_x", "elbow_y"}.issubset(set(canon.columns)):
            tx = pd.to_numeric(canon["trunk_x"], errors="coerce").values
            ty = pd.to_numeric(canon["trunk_y"], errors="coerce").values
            sx = pd.to_numeric(canon["shoulder_x"], errors="coerce").values
            sy = pd.to_numeric(canon["shoulder_y"], errors="coerce").values
            ex = pd.to_numeric(canon["elbow_x"], errors="coerce").values
            ey = pd.to_numeric(canon["elbow_y"], errors="coerce").values
            v1x, v1y = tx - sx, ty - sy
            v2x, v2y = ex - sx, ey - sy
            bad = (~np.isfinite(v1x)) | (~np.isfinite(v1y))
            v1x = np.where(bad, sx, v1x)
            v1y = np.where(bad, sy + 0.12 * frame_h, v1y)
            dot = v1x * v2x + v1y * v2y
            norm1 = np.hypot(v1x, v1y)
            norm2 = np.hypot(v2x, v2y)
            cosang = dot / (norm1 * norm2 + 1e-9)
            cosang = np.clip(cosang, -1.0, 1.0)
            shoulder_flexion = np.degrees(np.arccos(cosang))

        onset_idx, offset_idx = _movement_window(
            speed,
            elbow_angle=elbow_angle,
            fs=target_fs,
            velocity_threshold_px_s=float(analysis.get("velocity_threshold_px_s", 5.0)) if analysis else 5.0,
        )

        # Early table-surface estimate for seated pelvis placement (before hip pairs).
        rest_idx = int(onset_idx)
        rest_window = max(1, min(10, rest_idx + 1))
        rest_elbow_x_early = float(np.nanmedian(elbow_x[:rest_window])) if len(elbow_x) else float("nan")
        rest_palm_y_early = float(np.nanmedian(palm_y[:rest_window])) if len(palm_y) else float("nan")
        table_surface_y_early = None
        if table_edge is not None and np.isfinite(rest_elbow_x_early):
            edge_y = table_edge["edge_y"]
            display_w = table_edge["display_w"]
            x_idx = int(np.clip(round(rest_elbow_x_early * display_w), 0, display_w - 1))
            if 0 <= x_idx < len(edge_y) and np.isfinite(edge_y[x_idx]):
                table_surface_y_early = float(edge_y[x_idx])
            else:
                table_surface_y_early = float(np.nanmedian(edge_y))
        if (table_surface_y_early is None or not np.isfinite(table_surface_y_early)) and np.isfinite(rest_palm_y_early):
            table_surface_y_early = rest_palm_y_early

        # Full skeleton points (all normalized).
        nose_x, nose_y = _pair("NOSE")
        ls_x, ls_y = _pair("LEFT_SHOULDER")
        rs_x, rs_y = _pair("RIGHT_SHOULDER")
        le_x, le_y = _pair("LEFT_ELBOW")
        re_x, re_y = _pair("RIGHT_ELBOW")
        lw_x, lw_y = _pair("LEFT_WRIST")
        rw_x, rw_y = _pair("RIGHT_WRIST")
        lh_x, lh_y = _pair("LEFT_HIP")
        rh_x, rh_y = _pair("RIGHT_HIP")
        lk_x, lk_y = _pair("LEFT_KNEE")
        rk_x, rk_y = _pair("RIGHT_KNEE")
        la_x, la_y = _pair("LEFT_ANKLE")
        ra_x, ra_y = _pair("RIGHT_ANKLE")
        hl_pose_wx, hl_pose_wy = (rw_x, rw_y) if side == "right" else (lw_x, lw_y)

        # Fallback for hips: MediaPipe often places hips on the table/occluded area. The
        # trunk in the cleaned CSV is actually the shoulder-girdle midpoint, so we estimate
        # the hip from the shoulder and knee instead (closer to real anatomy for seated poses).
        ls_x_arr = np.asarray(ls_x, dtype=float)
        ls_y_arr = np.asarray(ls_y, dtype=float)
        rs_x_arr = np.asarray(rs_x, dtype=float)
        rs_y_arr = np.asarray(rs_y, dtype=float)
        lk_x_arr = np.asarray(lk_x, dtype=float)
        lk_y_arr = np.asarray(lk_y, dtype=float)
        rk_x_arr = np.asarray(rk_x, dtype=float)
        rk_y_arr = np.asarray(rk_y, dtype=float)
        shoulder_center_x = (ls_x_arr + rs_x_arr) / 2

        if table_surface_y_early is not None and np.isfinite(table_surface_y_early):
            # Seated reach: anchor pelvis between shoulder line and table (MediaPipe hips/knees are noisy).
            shoulder_mid_y = (ls_y_arr + rs_y_arr) / 2.0
            table_y = float(table_surface_y_early)
            pelvis_y = shoulder_mid_y + 0.36 * (table_y - shoulder_mid_y)
            pelvis_y = np.clip(pelvis_y, shoulder_mid_y + 0.04, table_y - 0.01)
            hip_half = np.abs(ls_x_arr - rs_x_arr) * 0.22
            hip_half = np.clip(hip_half, 0.03, 0.12)
            lh_x = shoulder_center_x - hip_half
            rh_x = shoulder_center_x + hip_half
            lh_y = pelvis_y
            rh_y = pelvis_y
        else:
            def _hip_estimate(sx, sy, kx, ky, center_x):
                """Estimate hip from shoulder and knee (40% of the way from shoulder to knee)."""
                sx = np.asarray(sx, dtype=float)
                sy = np.asarray(sy, dtype=float)
                kx = np.asarray(kx, dtype=float)
                ky = np.asarray(ky, dtype=float)
                est_x = sx + (kx - sx) * 0.40
                est_y = sy + (ky - sy) * 0.40
                est_x = center_x + (est_x - center_x) * 0.75
                return est_x, est_y

            est_lh_x, est_lh_y = _hip_estimate(ls_x_arr, ls_y_arr, lk_x_arr, lk_y_arr, shoulder_center_x)
            est_rh_x, est_rh_y = _hip_estimate(rs_x_arr, rs_y_arr, rk_x_arr, rk_y_arr, shoulder_center_x)

            def _hip_fallback(x, y, est_x, est_y, shoulder_y, knee_y):
                x = np.asarray(x, dtype=float)
                y = np.asarray(y, dtype=float)
                missing = ~(np.isfinite(x) & np.isfinite(y))
                reasonable = (y > shoulder_y + 0.05) & (y < knee_y - 0.05)
                replace = missing | ~reasonable
                x[replace] = est_x[replace]
                y[replace] = est_y[replace]
                return x, y

            lh_x, lh_y = _hip_fallback(lh_x, lh_y, est_lh_x, est_lh_y, ls_y_arr, lk_y_arr)
            rh_x, rh_y = _hip_fallback(rh_x, rh_y, est_rh_x, est_rh_y, rs_y_arr, rk_y_arr)

        # Build coordinate pairs. Missing values become null instead of clamped 0,0
        # so the frontend can skip drawing stray lines.
        def _make_pair(x: np.ndarray, y: np.ndarray) -> List[Optional[float]]:
            out = []
            for i in range(len(new_t)):
                if np.isfinite(x[i]) and np.isfinite(y[i]):
                    xi = float(x[i])
                    yi = float(y[i])
                    # Do not clamp to edges — out-of-range becomes null (avoids lines stuck to video border).
                    if 0.0 <= xi <= 1.0 and 0.0 <= yi <= 1.0:
                        out.append([xi, yi])
                    else:
                        out.append(None)
                else:
                    out.append(None)
            return out

        trunk_pairs = _make_pair(trunk_x, trunk_y)
        nose_pairs = _make_pair(nose_x, nose_y)
        ls_pairs = _make_pair(ls_x, ls_y)
        rs_pairs = _make_pair(rs_x, rs_y)
        le_pairs = _make_pair(le_x, le_y)
        re_pairs = _make_pair(re_x, re_y)
        lw_pairs = _make_pair(lw_x, lw_y)
        rw_pairs = _make_pair(rw_x, rw_y)
        lh_pairs = _make_pair(lh_x, lh_y)
        rh_pairs = _make_pair(rh_x, rh_y)

        lk_pairs = _make_pair(lk_x, lk_y)
        rk_pairs = _make_pair(rk_x, rk_y)
        la_pairs = _make_pair(la_x, la_y)
        ra_pairs = _make_pair(ra_x, ra_y)

        shoulder_width_px = 0.0
        if analysis and analysis.get("shoulder_width_px"):
            shoulder_width_px = float(analysis["shoulder_width_px"])
        else:
            try:
                lsx = _norm_series(raw_df, "LEFT_SHOULDER", "x").values
                rsx = _norm_series(raw_df, "RIGHT_SHOULDER", "x").values
                lsy = _norm_series(raw_df, "LEFT_SHOULDER", "y").values
                rsy = _norm_series(raw_df, "RIGHT_SHOULDER", "y").values
                sw = np.nanmedian(np.hypot(lsx - rsx, lsy - rsy)) * frame_w
                if np.isfinite(sw) and sw > 0:
                    shoulder_width_px = float(sw)
            except Exception:
                pass

        aff = "RIGHT" if side == "right" else "LEFT"
        opp = "LEFT" if aff == "RIGHT" else "RIGHT"
        pose_index_x, pose_index_y = _pose_finger_overlay_pair(raw_df, f"{aff}_INDEX", t, new_t, target_fs, frame_w, frame_h)
        pose_thumb_x, pose_thumb_y = _pose_finger_overlay_pair(raw_df, f"{aff}_THUMB", t, new_t, target_fs, frame_w, frame_h)
        pose_pinky_x, pose_pinky_y = _pose_finger_overlay_pair(raw_df, f"{aff}_PINKY", t, new_t, target_fs, frame_w, frame_h)
        index_x, index_y = pose_index_x, pose_index_y
        thumb_x, thumb_y = pose_thumb_x, pose_thumb_y
        pinky_x, pinky_y = pose_pinky_x, pose_pinky_y
        hand_landmarker_overlay = False
        hl_side = aff
        middle_x, middle_y = index_x, index_y
        ring_x, ring_y = pinky_x, pinky_y
        finger_track_conf = np.zeros(len(new_t))
        index_track_conf = np.zeros(len(new_t))
        finger_vis = {k: np.zeros(len(new_t)) for k in ("thumb", "index", "middle", "ring", "pinky")}
        finger_joints_arr: Dict[str, Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}

        hl_side, hl_cov = _pick_hl_side_window(
            raw_df, aff, opp, t, new_t, target_fs, frame_w, frame_h, int(onset_idx), int(offset_idx),
            palm_x=palm_x, palm_y=palm_y, wrist_x=hl_pose_wx, wrist_y=hl_pose_wy,
        )
        hl_wrist_x, hl_wrist_y = palm_x, palm_y
        if hl_side and hl_cov >= 0.20:
            hand_landmarker_overlay = True
            stabilized, finger_track_conf, index_track_conf, hl_wrist_x, hl_wrist_y, finger_vis, finger_joints_arr = _stabilize_hl_finger_overlay(
                raw_df,
                hl_side,
                t,
                new_t,
                target_fs,
                frame_w,
                frame_h,
                palm_x,
                palm_y,
                {
                    "index": (pose_index_x, pose_index_y),
                    "thumb": (pose_thumb_x, pose_thumb_y),
                    "pinky": (pose_pinky_x, pose_pinky_y),
                    "middle": (index_x, index_y),
                    "ring": (pinky_x, pinky_y),
                },
                elbow_x,
                elbow_y,
                hl_pose_wx,
                hl_pose_wy,
                table_surface_y=table_surface_y_early,
                start=int(onset_idx),
                end=int(offset_idx),
                shoulder_width_norm=(
                    float(shoulder_width_px) / max(float(frame_w), 1.0)
                    if shoulder_width_px and shoulder_width_px > 0
                    else None
                ),
            )
            index_x, index_y = stabilized["index"]
            thumb_x, thumb_y = stabilized["thumb"]
            pinky_x, pinky_y = stabilized["pinky"]
            middle_x, middle_y = stabilized["middle"]
            ring_x, ring_y = stabilized["ring"]
            hl_wrist_x = np.asarray(hl_wrist_x, dtype=float)
            hl_wrist_y = np.asarray(hl_wrist_y, dtype=float)
        else:
            pose_map = {
                "index": (index_x, index_y),
                "thumb": (thumb_x, thumb_y),
                "pinky": (pinky_x, pinky_y),
                "middle": (middle_x, middle_y),
                "ring": (ring_x, ring_y),
            }
            for key, (ox, oy) in pose_map.items():
                vis = finger_vis[key]
                for i in range(len(new_t)):
                    if np.isfinite(ox[i]) and np.isfinite(oy[i]) and np.isfinite(palm_x[i]) and np.isfinite(palm_y[i]):
                        d = float(np.hypot(ox[i] - palm_x[i], oy[i] - palm_y[i]))
                        if 0.004 <= d <= 0.18:
                            vis[i] = 1.0

        index_pairs = _make_pair(index_x, index_y)
        thumb_pairs = _make_pair(thumb_x, thumb_y)
        pinky_pairs = _make_pair(pinky_x, pinky_y)
        middle_pairs = _make_pair(middle_x, middle_y)
        ring_pairs = _make_pair(ring_x, ring_y)
        hl_wrist_pairs = _make_pair(hl_wrist_x, hl_wrist_y)

        # Affected-arm overlay uses live imgX (same space as video) — no filtered canon lag.
        if side == "right":
            disp_sh_x, disp_sh_y = rs_x, rs_y
            disp_el_x, disp_el_y = re_x, re_y
            disp_wr_x, disp_wr_y = rw_x, rw_y
        else:
            disp_sh_x, disp_sh_y = ls_x, ls_y
            disp_el_x, disp_el_y = le_x, le_y
            disp_wr_x, disp_wr_y = lw_x, lw_y
        disp_pa_x = np.asarray(index_x, dtype=float)
        disp_pa_y = np.asarray(index_y, dtype=float)
        miss_idx = ~np.isfinite(disp_pa_x) | ~np.isfinite(disp_pa_y)
        disp_pa_x = np.where(miss_idx, disp_wr_x, disp_pa_x)
        disp_pa_y = np.where(miss_idx, disp_wr_y, disp_pa_y)
        shoulder_pairs = _make_pair(disp_sh_x, disp_sh_y)
        elbow_pairs = _make_pair(disp_el_x, disp_el_y)
        wrist_pairs = _make_pair(disp_wr_x, disp_wr_y)
        palm_pairs = _make_pair(disp_pa_x, disp_pa_y)

        if hand_landmarker_overlay and hl_side and _hl_column_present(raw_df, hl_side, "INDEX_TIP"):
            tremor_index_x = index_x * frame_w
            tremor_index_y = index_y * frame_h

        opp_sh_x = np.asarray(ls_x if side == "right" else rs_x, dtype=float)
        opp_sh_y = np.asarray(ls_y if side == "right" else rs_y, dtype=float)
        sh_abd_deg = np.full(len(new_t), np.nan)
        for i in range(len(new_t)):
            ox, oy = opp_sh_x[i], opp_sh_y[i]
            sx, sy = shoulder_x[i], shoulder_y[i]
            ex, ey = elbow_x[i], elbow_y[i]
            if not all(np.isfinite(v) for v in (ox, oy, sx, sy, ex, ey)):
                continue
            v1x, v1y = ox - sx, oy - sy
            v2x, v2y = ex - sx, ey - sy
            m1, m2 = np.hypot(v1x, v1y), np.hypot(v2x, v2y)
            if m1 < 1e-6 or m2 < 1e-6:
                continue
            cos_a = np.clip((v1x * v2x + v1y * v2y) / (m1 * m2), -1.0, 1.0)
            sh_abd_deg[i] = float(np.degrees(np.arccos(cos_a)))

        adl_window = None
        if analysis:
            task_str = str(analysis.get("clinical_task") or "")
            adl_pick = _validation_phase_id_for_task(task_str)
            if adl_pick:
                canon_n = len(canon) if canon is not None else len(new_t)
                scale = len(new_t) / max(1, canon_n)
                for ph in analysis.get("task_phases") or []:
                    if ph.get("id") != adl_pick:
                        continue
                    sf = int(ph.get("start_frame") or 0)
                    ef = int(ph.get("end_frame") or len(new_t) - 1)
                    if scale != 1.0:
                        sf = int(round(sf * scale))
                        ef = int(round(ef * scale))
                    adl_window = {
                        "phase_id": adl_pick,
                        "start_idx": int(max(0, min(sf, len(new_t) - 1))),
                        "end_idx": int(max(0, min(ef, len(new_t) - 1))),
                    }
                    break
                if adl_window is None and adl_pick == "reach_grasp":
                    adl_window = {
                        "phase_id": "reach_grasp",
                        "start_idx": int(onset_idx),
                        "end_idx": int(offset_idx),
                    }

        start_palm = palm_pairs[onset_idx] if onset_idx < len(palm_pairs) else None
        end_palm = palm_pairs[offset_idx] if offset_idx < len(palm_pairs) else None

        # Compute per-frame shoulder elevation as affected shoulder height above shoulder midpoint.
        shoulder_y_px = pd.to_numeric(canon.get("shoulder_y", pd.Series(np.nan)), errors="coerce").values
        elbow_x_px = pd.to_numeric(canon.get("elbow_x", pd.Series(np.nan)), errors="coerce").values
        elbow_y_px = pd.to_numeric(canon.get("elbow_y", pd.Series(np.nan)), errors="coerce").values
        ls_y_px = np.asarray(ls_y) * frame_h
        rs_y_px = np.asarray(rs_y) * frame_h
        shoulder_mid_y_px = (ls_y_px + rs_y_px) / 2.0
        shoulder_elevation_px = shoulder_mid_y_px - shoulder_y_px

        trunk_x_px = pd.to_numeric(canon.get("trunk_x", pd.Series(np.nan)), errors="coerce").values
        trunk_baseline_x = float(trunk_x_px[int(onset_idx)]) if int(onset_idx) < len(trunk_x_px) and np.isfinite(trunk_x_px[int(onset_idx)]) else float(np.nanmedian(trunk_x_px))
        trunk_displacement_px = np.abs(trunk_x_px - trunk_baseline_x)

        if shoulder_width_px and shoulder_width_px > 0:
            shoulder_elevation_norm = shoulder_elevation_px / shoulder_width_px
            trunk_displacement_norm = trunk_displacement_px / shoulder_width_px
        else:
            shoulder_elevation_norm = shoulder_elevation_px / frame_h
            trunk_displacement_norm = trunk_displacement_px / frame_h

        # Table surface reference: detected front edge of the blue table top
        # directly under the elbow of the affected side (nearest to the camera).
        rest_shoulder_x = float(np.nanmedian(shoulder_x[:rest_window])) if len(shoulder_x) else float("nan")
        rest_shoulder_y_px = float(np.nanmedian(shoulder_y_px[:rest_window])) if len(shoulder_y_px) else float("nan")
        rest_elbow_x = float(np.nanmedian(elbow_x[:rest_window])) if len(elbow_x) else float("nan")

        table_surface_y = table_surface_y_early
        table_surface_fallback = table_surface_y is not None and table_edge is None

        # Compute per-frame table-referenced shoulder elevation ratio.
        shoulder_elevation_table_ratio = np.full(len(new_t), np.nan)
        if table_surface_y is not None and np.isfinite(table_surface_y) and np.isfinite(rest_shoulder_y_px):
            anchor_y_px = float(table_surface_y) * frame_h
            denom = abs(anchor_y_px - rest_shoulder_y_px)
            if np.isfinite(denom) and denom > 1e-6:
                shoulder_elevation_table_ratio = (rest_shoulder_y_px - shoulder_y_px) / denom

        # Fixed reference line from the affected shoulder down to the table surface
        # under the elbow (vertical line, anchor x = shoulder rest x).
        shoulder_elevation_palm_ratio = np.full(len(new_t), np.nan)
        shoulder_palm_anchor = None
        if np.isfinite(rest_shoulder_x) and np.isfinite(table_surface_y):
            anchor_x = round(float(rest_shoulder_x), 4)
            anchor_y = round(float(table_surface_y), 4)
            anchor_y_px = float(table_surface_y) * frame_h
            denom = abs(anchor_y_px - rest_shoulder_y_px)
            if np.isfinite(denom) and denom > 1e-6:
                shoulder_elevation_palm_ratio = (rest_shoulder_y_px - shoulder_y_px) / denom
            shoulder_palm_anchor = [anchor_x, anchor_y]

        # Clip speed so the chart/gauge ignore pre/post movement noise.
        speed_for_tremor = np.asarray(speed, dtype=float).copy()
        win_spd = speed_for_tremor[onset_idx : offset_idx + 1]
        win_elbow = None
        if elbow_angle is not None:
            win_elbow = np.asarray(elbow_angle[onset_idx : offset_idx + 1], dtype=float)
        win_sh_flex = None
        if shoulder_flexion is not None:
            win_sh_flex = np.asarray(shoulder_flexion[onset_idx : offset_idx + 1], dtype=float)

        for i in range(len(speed)):
            if i < onset_idx or i > offset_idx:
                speed[i] = 0.0

        sw_px = float(shoulder_width_px) if shoulder_width_px and shoulder_width_px > 0 else float(frame_w) * 0.25
        finger_open_sw = np.full(len(new_t), np.nan)
        wx_arr = np.asarray(hl_wrist_x if hand_landmarker_overlay else wrist_x, dtype=float)
        wy_arr = np.asarray(hl_wrist_y if hand_landmarker_overlay else wrist_y, dtype=float)
        for i in range(len(new_t)):
            if not (np.isfinite(wx_arr[i]) and np.isfinite(wy_arr[i])):
                continue
            dists: List[float] = []
            for tx, ty in (
                (index_x[i], index_y[i]),
                (thumb_x[i], thumb_y[i]),
                (middle_x[i], middle_y[i]),
                (ring_x[i], ring_y[i]),
                (pinky_x[i], pinky_y[i]),
            ):
                if np.isfinite(tx) and np.isfinite(ty):
                    dpx = float(np.hypot((tx - wx_arr[i]) * frame_w, (ty - wy_arr[i]) * frame_h))
                    dists.append(dpx / sw_px)
            if dists:
                finger_open_sw[i] = float(np.nanmean(dists))

        frames = []
        for i in range(len(new_t)):
            frame_finger_joints = {}
            for fid, jdata in finger_joints_arr.items():
                entry = {"vis": {}}
                for jname in ("mcp", "ip", "tip"):
                    ox, oy, cv = jdata[jname]
                    ok = bool(cv[i] >= 0.5 and np.isfinite(ox[i]) and np.isfinite(oy[i]))
                    entry["vis"][jname] = ok
                    entry[jname] = [round(float(ox[i]), 6), round(float(oy[i]), 6)] if ok else None
                frame_finger_joints[fid] = entry

            frames.append({
                "time": round(float(new_t[i]), 4),
                "speed": round(float(speed[i]) if np.isfinite(speed[i]) else 0.0, 2),
                "speed_tremor": round(float(speed_tremor[i]) if np.isfinite(speed_tremor[i]) else 0.0, 3),
                "elbow_angle": round(float(elbow_angle[i]) if elbow_angle is not None and np.isfinite(elbow_angle[i]) else 0.0, 2),
                "shoulder_flexion_deg": round(float(shoulder_flexion[i]) if shoulder_flexion is not None and np.isfinite(shoulder_flexion[i]) else 0.0, 2),
                "shoulder_elevation_norm": round(float(shoulder_elevation_norm[i]) if i < len(shoulder_elevation_norm) and np.isfinite(shoulder_elevation_norm[i]) else 0.0, 3),
                "shoulder_elevation_table_ratio": round(float(shoulder_elevation_table_ratio[i]) if i < len(shoulder_elevation_table_ratio) and np.isfinite(shoulder_elevation_table_ratio[i]) else 0.0, 3),
                "shoulder_elevation_palm_ratio": round(float(shoulder_elevation_palm_ratio[i]) if i < len(shoulder_elevation_palm_ratio) and np.isfinite(shoulder_elevation_palm_ratio[i]) else 0.0, 3),
                "trunk_displacement_norm": round(float(trunk_displacement_norm[i]) if i < len(trunk_displacement_norm) and np.isfinite(trunk_displacement_norm[i]) else 0.0, 3),
                "palm": palm_pairs[i],
                "wrist": wrist_pairs[i],
                "shoulder": shoulder_pairs[i],
                "elbow": elbow_pairs[i],
                "trunk": trunk_pairs[i],
                "nose": nose_pairs[i],
                "lshoulder": ls_pairs[i],
                "rshoulder": rs_pairs[i],
                "lelbow": le_pairs[i],
                "relbow": re_pairs[i],
                "lwrist": lw_pairs[i],
                "rwrist": rw_pairs[i],
                "lhip": lh_pairs[i],
                "rhip": rh_pairs[i],
                "lknee": lk_pairs[i],
                "rknee": rk_pairs[i],
                "lankle": la_pairs[i],
                "rankle": ra_pairs[i],
                "index": index_pairs[i],
                "thumb": thumb_pairs[i],
                "pinky": pinky_pairs[i],
                "middle": middle_pairs[i],
                "ring": ring_pairs[i],
                "hl_wrist": hl_wrist_pairs[i],
                "hand_hl": hand_landmarker_overlay,
                "shoulder_abduction_deg": round(float(sh_abd_deg[i]), 1) if np.isfinite(sh_abd_deg[i]) else 0.0,
                "finger_open_sw": round(float(finger_open_sw[i]), 4) if np.isfinite(finger_open_sw[i]) else 0.0,
                "finger_track_conf": round(float(finger_track_conf[i]), 2) if np.isfinite(finger_track_conf[i]) else 0.0,
                "finger_vis": {
                    "thumb": bool(finger_vis["thumb"][i] >= 0.5),
                    "index": bool(finger_vis["index"][i] >= 0.5),
                    "middle": bool(finger_vis["middle"][i] >= 0.5),
                    "ring": bool(finger_vis["ring"][i] >= 0.5),
                    "pinky": bool(finger_vis["pinky"][i] >= 0.5),
                },
                "finger_joints": frame_finger_joints,
            })

        metrics = {}
        if analysis:
            for k in [
                "nvp", "straightness", "pause_time_sec", "number_of_stops",
                "movement_time_sec", "peak_velocity_px_s", "peak_velocity_cm_s",
                "time_to_peak_velocity_sec", "relative_time_to_peak_pct",
                "elbow_angle_mean_deg", "elbow_angle_range_deg",
                "shoulder_flexion_mean_deg", "peak_shoulder_flexion_vel_deg_s",
                "shoulder_elevation_norm", "trunk_ratio", "sparc",
                "hand_displacement_px", "hand_displacement_cm", "hand_displacement_norm",
                "shoulder_elevation_cm", "shoulder_elevation_abs_px",
                "shoulder_width_px", "shoulder_width_cm", "cm_per_px",
                "shoulder_elevation_table_ratio",
            ]:
                if k in analysis and analysis[k] is not None:
                    try:
                        metrics[k] = float(analysis[k]) if not isinstance(analysis[k], (str, bool)) else analysis[k]
                    except Exception:
                        pass

        # Compute NVP peaks on the resampled speed so indices match the frames array.
        from unified_kinematics import _compute_nvp

        _, peak_arr = _compute_nvp(speed, prominence_frac=0.30)
        nvp_peaks = [int(x) for x in peak_arr]

        # Ensure nvp is always present in metrics even if analysis is missing.
        if ("nvp" not in metrics or metrics["nvp"] is None) and len(nvp_peaks):
            metrics["nvp"] = len(nvp_peaks)

        velocity_profile = None
        if fs := float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", target_fs))) if analysis else target_fs:
            velocity_profile = {
                "t": (np.arange(len(speed)) / fs).tolist(),
                "v": [float(v) if np.isfinite(v) else 0.0 for v in speed],
            }

        elbow_angle_profile = None
        if fs and elbow_angle is not None:
            elbow_angle_profile = {
                "t": (np.arange(len(elbow_angle)) / fs).tolist(),
                "v": [float(v) if np.isfinite(v) else 0.0 for v in elbow_angle],
            }

        trunk_x_profile = None
        if fs and "trunk_x" in canon.columns:
            trunk_x = pd.to_numeric(canon["trunk_x"], errors="coerce").values
            trunk_x_profile = {
                "t": (np.arange(len(trunk_x)) / fs).tolist(),
                "v": [float(v) if np.isfinite(v) else 0.0 for v in trunk_x],
            }

        # Prefer final SPARC from the analysis JSON if available.
        if analysis and "sparc" in analysis and analysis["sparc"] is not None:
            try:
                metrics["sparc"] = float(analysis["sparc"])
            except Exception:
                pass

        fs_overlay = float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", target_fs))) if analysis else float(target_fs)
        try:
            import sys

            _ran = Path(__file__).resolve().parent.parent / "R an"
            if (_ran / "motion_invariants.py").exists() and str(_ran) not in sys.path:
                sys.path.insert(0, str(_ran))
            elif Path(__file__).resolve().parent.joinpath("motion_invariants.py").exists():
                _ran = Path(__file__).resolve().parent
                if str(_ran) not in sys.path:
                    sys.path.insert(0, str(_ran))
            from motion_invariants import compute_tremor_metrics_block, tremor_envelope_series

            sw_tremor = float(shoulder_width_px) if shoulder_width_px and shoulder_width_px > 0 else None
            tremor_block = compute_tremor_metrics_block(
                fs=fs_overlay,
                start=int(onset_idx),
                end=int(offset_idx),
                palm_x=tremor_palm_x,
                palm_y=tremor_palm_y,
                elbow_angles=elbow_angle,
                shoulder_flex_angles=shoulder_flexion,
                index_x=tremor_index_x,
                index_y=tremor_index_y,
                shoulder_width=sw_tremor,
            )
            for tk, tv in tremor_block.items():
                if tv is not None:
                    metrics[tk] = tv

            mp = analysis.get("movement_profile") if analysis else None
            if isinstance(mp, dict):
                for tk in (
                    "tremor_8_12hz_power",
                    "tremor_index",
                    "tremor_peak_freq_hz",
                    "hand_speed_tremor_8_12hz_power",
                    "index_tremor_8_12hz_power",
                    "index_tremor_peak_freq_hz",
                    "elbow_tremor_8_12hz_power",
                    "shoulder_flexion_tremor_8_12hz_power",
                    "pinch_tremor_8_12hz_power",
                ):
                    if mp.get(tk) is not None:
                        metrics[tk] = mp[tk]

            if analysis and analysis.get("movement_quality_index") is not None:
                metrics["movement_quality_index"] = analysis["movement_quality_index"]

            if hand_landmarker_overlay and hl_side:
                win_seg = slice(int(onset_idx), int(offset_idx) + 1)
                track_seg = finger_track_conf[win_seg]
                index_seg = index_track_conf[win_seg]
                if len(track_seg):
                    metrics["hl_side_locked"] = hl_side
                    metrics["hl_finger_track_pct"] = round(float(np.mean(track_seg >= 0.42) * 100.0), 1)
                    metrics["hl_index_fresh_pct"] = round(float(np.mean(index_seg >= 0.85) * 100.0), 1)
                    metrics["hl_index_coverage_pct"] = round(float(np.mean(index_seg >= 0.72) * 100.0), 1)

            if adl_window:
                adl_s = int(adl_window.get("start_idx", onset_idx))
                adl_e = int(adl_window.get("end_idx", offset_idx))
                adl_block = compute_tremor_metrics_block(
                    fs=fs_overlay,
                    start=adl_s,
                    end=adl_e,
                    palm_x=tremor_palm_x,
                    palm_y=tremor_palm_y,
                    elbow_angles=elbow_angle,
                    shoulder_flex_angles=shoulder_flexion,
                    index_x=tremor_index_x,
                    index_y=tremor_index_y,
                    shoulder_width=sw_tremor,
                )
                if adl_block.get("tremor_8_12hz_power") is not None:
                    metrics["adl_tremor_8_12hz_power"] = adl_block["tremor_8_12hz_power"]
                for adl_tk in (
                    "tremor_peak_freq_hz",
                    "index_tremor_8_12hz_power",
                    "index_tremor_peak_freq_hz",
                ):
                    if adl_block.get(adl_tk) is not None:
                        metrics[f"adl_{adl_tk}"] = adl_block[adl_tk]
        except Exception:
            traceback.print_exc()

        _copy_joint_metrics_from_analysis(metrics, analysis)

        tremor_profile = None
        win_spd_tremor = np.asarray(speed_tremor[onset_idx : offset_idx + 1], dtype=float)
        if fs_overlay > 0 and len(win_spd_tremor) >= 16:
            sw_norm = float(shoulder_width_px) if shoulder_width_px and shoulder_width_px > 0 else 1.0
            env = tremor_envelope_series(win_spd_tremor / sw_norm, fs_overlay)
            if env is not None and len(env):
                tremor_profile = {
                    "signal": "hand_speed_tremor_envelope",
                    "band_hz": [8.0, 12.0],
                    "band_power": metrics.get("tremor_8_12hz_power"),
                    "t": (np.arange(len(env)) / fs_overlay).tolist(),
                    "v": [float(v) if np.isfinite(v) else 0.0 for v in env],
                }

        return {
            "overlay_version": 36,
            "finger_overlay_mode": "joint_dots",
            "hand_landmarker_overlay": hand_landmarker_overlay,
            "fps": round(float(target_fs), 2),
            "duration_sec": round(float(t1 - t0), 3),
            "affected_side": side,
            **({"side_detection": side_detection} if side_detection else {}),
            "frame_width_px": round(float(frame_w), 2),
            "frame_height_px": round(float(frame_h), 2),
            "video_orientation_deg": int(orientation) if orientation is not None else 0,
            "video_raw_width_px": round(float(raw_w), 2) if raw_w else 0.0,
            "video_raw_height_px": round(float(raw_h), 2) if raw_h else 0.0,
            **({"coord_remap": coord_remap} if coord_remap else {}),
            **({"coord_transform": coord_transform} if coord_transform else {}),
            **({"coord_transform_diag": {
                "best_transform": transform_diag.get("best_transform"),
                "scores": transform_diag.get("scores"),
                "landmark_source": transform_diag.get("landmark_source"),
            }} if transform_diag else {}),
            **({"hl_coord_transform": hl_coord_transform} if hl_coord_transform else {}),
            **({"hl_coord_transform_diag": hl_transform_diag} if hl_transform_diag else {}),
            "shoulder_width_px": round(float(shoulder_width_px), 2) if shoulder_width_px and shoulder_width_px > 0 else 0.0,
            "frames": frames,
            "metrics": metrics,
            "movement_window": {"start_idx": int(onset_idx), "end_idx": int(offset_idx)},
            **({"adl_window": adl_window} if adl_window else {}),
            "peak_velocity_px_s": round(float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0, 2),
            "velocity_profile": velocity_profile,
            "elbow_angle_profile": elbow_angle_profile,
            "trunk_x_profile": trunk_x_profile,
            "tremor_profile": tremor_profile,
            "table_surface_y": round(table_surface_y, 4) if table_surface_y is not None else None,
            "table_surface_fallback": table_surface_fallback,
            "debug_video_path": str(resolved_video_path) if resolved_video_path else None,
            "overlay_video_filename": Path(resolved_video_path).name if resolved_video_path else None,
            "debug_table_edge_found": table_edge is not None,
            "shoulder_palm_anchor": shoulder_palm_anchor,
            "peak_frames": nvp_peaks,
            "start_palm": start_palm,
            "end_palm": end_palm,
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    result = build_overlay_data(sys.argv[1])
    print(json.dumps({k: v for k, v in result.items() if k != "frames"}, indent=2))
    print("frames:", len(result.get("frames", [])))
