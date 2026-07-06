"""
Unified kinematic computation.

This module provides a single source of truth for kinematic metrics.
Both the /analyze endpoint and the unified validation video renderer use
exactly the same landmark preprocessing and metric formulas so the table
and the video overlay always match.
"""

import traceback
from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks, butter, filtfilt


# ---------------------------------------------------------------------------
# Preprocessing helpers (mirrors the renderer)
# ---------------------------------------------------------------------------

def _safe_float(v):
    try:
        v = float(v)
        if np.isfinite(v):
            return v
    except Exception:
        pass
    return 0.0


def _butter_lowpass_filter(x: np.ndarray, cutoff_hz: float = 4.0, fs: float = 60.0, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth low-pass filter."""
    x = np.asarray(x, dtype=float)
    if len(x) < 5 or cutoff_hz <= 0 or fs <= 0 or cutoff_hz >= fs / 2:
        return x
    try:
        b, a = butter(order, cutoff_hz / (fs / 2), btype="low")
        padlen = min(3 * max(len(a), len(b)), len(x) - 1)
        if padlen <= 0:
            return x
        return filtfilt(b, a, x, padlen=padlen)
    except Exception:
        return x


def _interpolate_small_gaps(arr: np.ndarray, max_gap: int = 8) -> np.ndarray:
    """Linearly interpolate NaN runs up to max_gap frames."""
    arr = np.asarray(arr, dtype=float).copy()
    n = len(arr)
    if n == 0:
        return arr
    # Fill leading/trailing NaNs with nearest valid value
    if np.isnan(arr[0]):
        first_valid = np.argmax(np.isfinite(arr))
        if np.isfinite(arr[first_valid]):
            arr[:first_valid] = arr[first_valid]
    if np.isnan(arr[-1]):
        last_valid = n - 1 - np.argmax(np.isfinite(arr[::-1]))
        if np.isfinite(arr[last_valid]):
            arr[last_valid + 1 :] = arr[last_valid]
    # Interpolate internal gaps
    i = 0
    while i < n:
        if np.isnan(arr[i]):
            j = i
            while j < n and np.isnan(arr[j]):
                j += 1
            if j - i <= max_gap and i > 0 and j < n:
                arr[i:j] = np.linspace(arr[i - 1], arr[j], j - i + 2)[1:-1]
            i = j
        else:
            i += 1
    return arr


def _resample_to_fs(df: pd.DataFrame, target_fs: float = 60.0) -> pd.DataFrame:
    """Resample landmark dataframe to target_fs using linear interpolation."""
    if "time" not in df.columns or len(df) < 2:
        return df.copy()
    t = pd.to_numeric(df["time"], errors="coerce").values
    if np.isnan(t).any():
        t = np.arange(len(df)) / target_fs
    t0, t1 = t[0], t[-1]
    if t1 <= t0:
        return df.copy()
    new_t = np.arange(t0, t1 + 0.5 / target_fs, 1.0 / target_fs)
    out = {"time": new_t}
    for col in df.columns:
        if col == "time":
            continue
        y = pd.to_numeric(df[col], errors="coerce").values
        y = _interpolate_small_gaps(y)
        out[col] = np.interp(new_t, t, y)
    return pd.DataFrame(out)


def _build_analysis_columns(df: pd.DataFrame, affected_side: str = "auto") -> pd.DataFrame:
    """
    Ensure canonical analysis columns exist:
      palm_x/y, wrist_x/y, shoulder_x/y, elbow_x/y, trunk_x/y
    If the dataframe already has them, return as-is. Otherwise build from
    raw MediaPipe-style landmark columns.
    """
    required = {"palm_x", "palm_y", "wrist_x", "wrist_y",
                "shoulder_x", "shoulder_y", "elbow_x", "elbow_y", "trunk_x", "trunk_y"}
    if required.issubset(set(df.columns)):
        return df.copy()

    from mediapipe_csv_extractor import build_analysis_dataframe
    side = affected_side if affected_side in ("left", "right") else "auto"
    fps = 60.0
    if "time" in df.columns:
        t = pd.to_numeric(df["time"], errors="coerce").dropna()
        if len(t) > 1:
            fps = 1.0 / float(t.diff().mean())
    out_df, _ = build_analysis_dataframe(
        df,
        frame_width=1920,
        frame_height=1080,
        fps=fps,
        affected_side=side,
        camera_view="auto",
        butterworth_cutoff_hz=4.0,
        butterworth_order=4,
    )
    return out_df


def _filter_landmark_columns(df: pd.DataFrame, cutoff_hz: float = 4.0, fs: float = 60.0, order: int = 4) -> pd.DataFrame:
    """Apply low-pass filter to all landmark coordinate columns."""
    df = df.copy()
    landmark_cols = [c for c in df.columns if c.endswith(("_x", "_y", "_z"))]
    for col in landmark_cols:
        vals = pd.to_numeric(df[col], errors="coerce").values
        vals = _interpolate_small_gaps(vals)
        df[col] = _butter_lowpass_filter(vals, cutoff_hz=cutoff_hz, fs=fs, order=order)
    return df


def load_canonical_landmarks(
    csv_path: str,
    affected_side: str = "auto",
    target_fs: float = 60.0,
    cutoff_hz: float = 4.0,
    filter_order: int = 4,
) -> pd.DataFrame:
    """
    Load a landmarks CSV and return a canonical, analysis-ready dataframe.

    Steps:
      1. Read CSV (raw MediaPipe columns or pre-built analysis columns).
      2. Build canonical columns (palm_x/y, wrist_x/y, ...).
      3. Resample to target_fs.
      4. Apply Butterworth low-pass filter.
    """
    df = pd.read_csv(csv_path)
    df = _build_analysis_columns(df, affected_side=affected_side)
    df = _resample_to_fs(df, target_fs=target_fs)
    df = _filter_landmark_columns(df, cutoff_hz=cutoff_hz, fs=target_fs, order=filter_order)
    return df


# ---------------------------------------------------------------------------
# Metric computation (mirrors the renderer)
# ---------------------------------------------------------------------------

def _compute_speed(df: pd.DataFrame, fs: float = 60.0) -> np.ndarray:
    """Tangential palm speed in px/s."""
    if "palm_x" not in df.columns or "palm_y" not in df.columns:
        return np.zeros(len(df))
    x = pd.to_numeric(df["palm_x"], errors="coerce").values
    y = pd.to_numeric(df["palm_y"], errors="coerce").values
    dx = np.gradient(x)
    dy = np.gradient(y)
    speed = np.hypot(dx, dy) * fs
    return speed


def _compute_nvp(speed: np.ndarray, prominence_frac: float = 0.30) -> int:
    """Number of velocity peaks using renderer-style prominence."""
    speed = np.asarray(speed, dtype=float)
    if len(speed) < 5:
        return 0
    std = float(np.nanstd(speed))
    peak = float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0
    prominence = std * prominence_frac if std > 0 else peak * 0.05
    peaks, _ = find_peaks(speed, prominence=prominence)
    return int(len(peaks))


def _compute_straightness(df: pd.DataFrame) -> float:
    """Path straightness from palm trajectory."""
    if "palm_x" not in df.columns or "palm_y" not in df.columns:
        return float("nan")
    x = pd.to_numeric(df["palm_x"], errors="coerce").values
    y = pd.to_numeric(df["palm_y"], errors="coerce").values
    if len(x) < 2:
        return float("nan")
    straight = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    dx = np.gradient(x)
    dy = np.gradient(y)
    path = float(np.nansum(np.hypot(dx, dy)))
    if path <= 0 or not np.isfinite(path):
        return float("nan")
    return straight / path


def _compute_pause_time_and_stops(
    speed: np.ndarray,
    fs: float = 60.0,
    pause_threshold_frac: float = 0.05,
    min_pause_frames: int = 6,
) -> tuple:
    """Total pause time (s) and number of stops."""
    speed = np.asarray(speed, dtype=float)
    if len(speed) == 0:
        return 0.0, 0
    peak = float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0
    threshold = peak * pause_threshold_frac if peak > 0 else 1.0
    below = speed < threshold
    n_stops = 0
    total_pause_frames = 0
    in_pause = False
    run_length = 0
    for b in below:
        if b:
            run_length += 1
            if not in_pause and run_length >= min_pause_frames:
                n_stops += 1
                in_pause = True
        else:
            if in_pause:
                total_pause_frames += run_length
            in_pause = False
            run_length = 0
    if in_pause:
        total_pause_frames += run_length
    pause_time = total_pause_frames / fs
    return float(pause_time), int(n_stops)


def _compute_elbow_angle(df: pd.DataFrame) -> np.ndarray:
    """Elbow flexion angle (deg) for each frame."""
    required = {"shoulder_x", "shoulder_y", "elbow_x", "elbow_y", "wrist_x", "wrist_y"}
    if not required.issubset(set(df.columns)):
        return np.full(len(df), float("nan"))
    sx = pd.to_numeric(df["shoulder_x"], errors="coerce").values
    sy = pd.to_numeric(df["shoulder_y"], errors="coerce").values
    ex = pd.to_numeric(df["elbow_x"], errors="coerce").values
    ey = pd.to_numeric(df["elbow_y"], errors="coerce").values
    wx = pd.to_numeric(df["wrist_x"], errors="coerce").values
    wy = pd.to_numeric(df["wrist_x"], errors="coerce").values

    v1x, v1y = sx - ex, sy - ey
    v2x, v2y = wx - ex, wy - ey
    dot = v1x * v2x + v1y * v2y
    norm1 = np.hypot(v1x, v1y)
    norm2 = np.hypot(v2x, v2y)
    cosang = dot / (norm1 * norm2 + 1e-9)
    cosang = np.clip(cosang, -1.0, 1.0)
    return np.degrees(np.arccos(cosang))


def _movement_window(speed: np.ndarray, fs: float = 60.0, velocity_threshold_px_s: float = 5.0) -> tuple:
    """Return (start_idx, end_idx) of active movement."""
    speed = np.asarray(speed, dtype=float)
    above = speed >= velocity_threshold_px_s
    indices = np.where(above)[0]
    if len(indices) == 0:
        return 0, len(speed) - 1
    return int(indices[0]), int(indices[-1])


def compute_unified_kinematic_metrics(
    csv_path: str,
    affected_side: str = "auto",
    target_fs: float = 60.0,
    cutoff_hz: float = 4.0,
    filter_order: int = 4,
    velocity_threshold_px_s: float = 5.0,
    name: str = "trial",
) -> Dict[str, Any]:
    """
    Compute kinematic metrics from a landmarks CSV.

    Returns a dict with the same keys used by the validation video renderer
    and the results table:
      nvp, straightness, pause_time_sec, number_of_stops,
      movement_time_sec, peak_velocity_px_s, time_to_peak_velocity_sec,
      elbow_angle_mean_deg, elbow_angle_range_deg,
      shoulder_elevation_norm, trunk_ratio
    """
    try:
        df = load_canonical_landmarks(
            csv_path,
            affected_side=affected_side,
            target_fs=target_fs,
            cutoff_hz=cutoff_hz,
            filter_order=filter_order,
        )
        n = len(df)
        if n < 5:
            return {"error": "Too few landmark frames to compute metrics"}

        fs = target_fs
        speed = _compute_speed(df, fs=fs)
        time = np.arange(n) / fs

        start_idx, end_idx = _movement_window(speed, fs=fs, velocity_threshold_px_s=velocity_threshold_px_s)
        if end_idx <= start_idx:
            end_idx = min(n - 1, start_idx + 1)

        nvp = _compute_nvp(speed, prominence_frac=0.30)
        straightness = _compute_straightness(df)
        pause_time_sec, number_of_stops = _compute_pause_time_and_stops(speed, fs=fs)

        movement_time_sec = (end_idx - start_idx) / fs

        window_speed = speed[start_idx : end_idx + 1]
        peak_velocity_px_s = float(np.nanmax(window_speed)) if len(window_speed) else 0.0
        peak_idx = start_idx + int(np.nanargmax(window_speed)) if len(window_speed) else start_idx
        time_to_peak_velocity_sec = peak_idx / fs

        elbow_angle = _compute_elbow_angle(df)
        elbow_window = elbow_angle[start_idx : end_idx + 1]
        elbow_angle_mean_deg = float(np.nanmean(elbow_window)) if len(elbow_window) else float("nan")
        elbow_angle_range_deg = float(np.nanmax(elbow_window) - np.nanmin(elbow_window)) if len(elbow_window) else float("nan")

        # Shoulder elevation as vertical displacement of shoulder relative to movement start
        shoulder_elev_norm = float("nan")
        if "shoulder_y" in df.columns:
            shoulder_y = pd.to_numeric(df["shoulder_y"], errors="coerce").values
            if np.any(np.isfinite(shoulder_y)):
                sh_start = float(np.nanmean(shoulder_y[max(0, start_idx - 2) : start_idx + 3]))
                sh_min = float(np.nanmin(shoulder_y[start_idx : end_idx + 1]))
                # Normalize by shoulder width if available, otherwise raw px
                shoulder_width_px = float(np.nanmax(pd.to_numeric(df.get("shoulder_x", pd.Series([0])), errors="coerce")) -
                                          np.nanmin(pd.to_numeric(df.get("shoulder_x", pd.Series([0])), errors="coerce")))
                if shoulder_width_px and shoulder_width_px > 0:
                    shoulder_elev_norm = abs(sh_start - sh_min) / shoulder_width_px
                else:
                    shoulder_elev_norm = abs(sh_start - sh_min)

        # Trunk ratio: trunk displacement / palm displacement
        trunk_ratio = float("nan")
        if "trunk_x" in df.columns and "palm_x" in df.columns:
            trunk_x = pd.to_numeric(df["trunk_x"], errors="coerce").values
            palm_x = pd.to_numeric(df["palm_x"], errors="coerce").values
            palm_y = pd.to_numeric(df["palm_y"], errors="coerce").values
            if len(trunk_x) and np.any(np.isfinite(trunk_x)):
                trunk_disp = float(abs(trunk_x[end_idx] - trunk_x[start_idx]))
                palm_disp = float(np.hypot(palm_x[end_idx] - palm_x[start_idx], palm_y[end_idx] - palm_y[start_idx]))
                if palm_disp > 0:
                    trunk_ratio = trunk_disp / palm_disp

        # Velocity profile for charting (same speed signal as metrics)
        velocity_profile = None
        if fs > 0:
            velocity_profile = {
                "time": (np.arange(len(speed)) / fs).tolist(),
                "speed": speed.tolist(),
                "fs_hz": fs,
                "onset_frame": int(start_idx),
                "offset_frame": int(end_idx),
            }

        return {
            "nvp": int(nvp),
            "straightness": float(straightness) if np.isfinite(straightness) else float("nan"),
            "pause_time_sec": float(pause_time_sec),
            "number_of_stops": int(number_of_stops),
            "movement_time_sec": float(movement_time_sec),
            "peak_velocity_px_s": float(peak_velocity_px_s),
            "time_to_peak_velocity_sec": float(time_to_peak_velocity_sec),
            "elbow_angle_mean_deg": float(elbow_angle_mean_deg),
            "elbow_angle_range_deg": float(elbow_angle_range_deg),
            "shoulder_elevation_norm": float(shoulder_elev_norm),
            "shoulder_vert_norm": float(shoulder_elev_norm),
            "trunk_ratio": float(trunk_ratio),
            "velocity_profile": velocity_profile,
            "fs_hz": float(fs),
            "analysis_fs_hz": float(fs),
            "movement_onset_frame": int(start_idx),
            "movement_offset_frame": int(end_idx),
            "name": name,
            "side_analyzed": affected_side,
            "comparison_role": name.lower(),
            "camera_view": "auto",
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
