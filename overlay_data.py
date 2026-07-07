"""
Lightweight overlay data for browser-side validation video rendering.

Returns per-frame landmarks + metrics so the frontend can draw the skeleton,
trajectory, and metric labels on top of the original video without waiting for
server-side video encoding.
"""

import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def _norm_series(df: pd.DataFrame, name: str, coord: str) -> pd.Series:
    """Return a normalized [0,1] series for a MediaPipe-style landmark column."""
    cols = [f"{name}_{coord}", f"{name}_{coord.upper()}", f"{name.lower()}_{coord.lower()}"]
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

        # Determine side.
        side = affected_side.lower() if affected_side else "auto"
        if side not in ("left", "right"):
            side = ((analysis or {}).get("side_analyzed") or (analysis or {}).get("affected_side") or "right").lower()
        if side not in ("left", "right"):
            side = "right"

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
            x[vis < 0.5] = np.nan
            y[vis < 0.5] = np.nan
            return _smooth_pairs(x, y, window=7)

        # Affected-side canonical points from the unified kinematics module.
        from unified_kinematics import load_canonical_landmarks, _compute_speed, _movement_window

        canon = load_canonical_landmarks(
            str(csv_path),
            affected_side=side,
            target_fs=target_fs,
            cutoff_hz=4.0,
            filter_order=4,
        )
        if len(canon) != len(new_t):
            canon_t = pd.to_numeric(canon["time"], errors="coerce").values
            for col in canon.columns:
                if col == "time":
                    continue
                canon[col] = np.interp(new_t, canon_t, pd.to_numeric(canon[col], errors="coerce").values)

        frame_w = float(pd.to_numeric(canon.get("frame_width_px", pd.Series(1920.0)), errors="coerce").iloc[0] or 1920.0)
        frame_h = float(pd.to_numeric(canon.get("frame_height_px", pd.Series(1080.0)), errors="coerce").iloc[0] or 1080.0)
        if frame_w <= 0:
            frame_w = 1920.0
        if frame_h <= 0:
            frame_h = 1080.0

        palm_x = pd.to_numeric(canon.get("palm_x", pd.Series(np.nan)), errors="coerce").values / frame_w
        palm_y = pd.to_numeric(canon.get("palm_y", pd.Series(np.nan)), errors="coerce").values / frame_h
        wrist_x = pd.to_numeric(canon.get("wrist_x", pd.Series(np.nan)), errors="coerce").values / frame_w
        wrist_y = pd.to_numeric(canon.get("wrist_y", pd.Series(np.nan)), errors="coerce").values / frame_h
        shoulder_x = pd.to_numeric(canon.get("shoulder_x", pd.Series(np.nan)), errors="coerce").values / frame_w
        shoulder_y = pd.to_numeric(canon.get("shoulder_y", pd.Series(np.nan)), errors="coerce").values / frame_h
        elbow_x = pd.to_numeric(canon.get("elbow_x", pd.Series(np.nan)), errors="coerce").values / frame_w
        elbow_y = pd.to_numeric(canon.get("elbow_y", pd.Series(np.nan)), errors="coerce").values / frame_h
        trunk_x = pd.to_numeric(canon.get("trunk_x", pd.Series(np.nan)), errors="coerce").values / frame_w
        trunk_y = pd.to_numeric(canon.get("trunk_y", pd.Series(np.nan)), errors="coerce").values / frame_h

        speed = _compute_speed(canon, fs=target_fs)
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

        onset_idx, offset_idx = _movement_window(
            speed,
            elbow_angle=elbow_angle,
            fs=target_fs,
            velocity_threshold_px_s=float(analysis.get("velocity_threshold_px_s", 5.0)) if analysis else 5.0,
        )

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

        # Fallback for hips: if MediaPipe detects them on the table/occluded, estimate
        # from the trunk/shoulder relationship (trunk = midpoint of shoulders + hips).
        trunk_x_arr = np.asarray(trunk_x, dtype=float)
        trunk_y_arr = np.asarray(trunk_y, dtype=float)
        ls_x_arr = np.asarray(ls_x, dtype=float)
        ls_y_arr = np.asarray(ls_y, dtype=float)
        rs_x_arr = np.asarray(rs_x, dtype=float)
        rs_y_arr = np.asarray(rs_y, dtype=float)
        shoulder_center_x = (ls_x_arr + rs_x_arr) / 2
        shoulder_center_y = (ls_y_arr + rs_y_arr) / 2
        est_hip_center_x = 2 * trunk_x_arr - shoulder_center_x
        est_hip_center_y = 2 * trunk_y_arr - shoulder_center_y
        est_lh_x = est_hip_center_x + (ls_x_arr - shoulder_center_x) * 0.7
        est_lh_y = est_hip_center_y + (ls_y_arr - shoulder_center_y) * 0.7
        est_rh_x = est_hip_center_x + (rs_x_arr - shoulder_center_x) * 0.7
        est_rh_y = est_hip_center_y + (rs_y_arr - shoulder_center_y) * 0.7

        def _hip_fallback(x: np.ndarray, y: np.ndarray, est_x: np.ndarray, est_y: np.ndarray):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            missing = ~(np.isfinite(x) & np.isfinite(y))
            dist = np.hypot(x - est_x, y - est_y)
            bad = dist > 0.25  # detected hip far from the expected body position
            replace = missing | bad
            x[replace] = est_x[replace]
            y[replace] = est_y[replace]
            return x, y

        lh_x, lh_y = _hip_fallback(lh_x, lh_y, est_lh_x, est_lh_y)
        rh_x, rh_y = _hip_fallback(rh_x, rh_y, est_rh_x, est_rh_y)

        # Build coordinate pairs. Missing values become null instead of clamped 0,0
        # so the frontend can skip drawing stray lines.
        def _make_pair(x: np.ndarray, y: np.ndarray) -> List[Optional[float]]:
            out = []
            for i in range(len(new_t)):
                if np.isfinite(x[i]) and np.isfinite(y[i]):
                    out.append([float(np.clip(x[i], 0.0, 1.0)), float(np.clip(y[i], 0.0, 1.0))])
                else:
                    out.append(None)
            return out

        palm_pairs = _make_pair(palm_x, palm_y)
        wrist_pairs = _make_pair(wrist_x, wrist_y)
        shoulder_pairs = _make_pair(shoulder_x, shoulder_y)
        elbow_pairs = _make_pair(elbow_x, elbow_y)
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

        start_palm = palm_pairs[onset_idx] if onset_idx < len(palm_pairs) else None
        end_palm = palm_pairs[offset_idx] if offset_idx < len(palm_pairs) else None

        # Clip speed so the chart/gauge ignore pre/post movement noise.
        for i in range(len(speed)):
            if i < onset_idx or i > offset_idx:
                speed[i] = 0.0

        frames = []
        for i in range(len(new_t)):
            frames.append({
                "time": round(float(new_t[i]), 4),
                "speed": round(float(speed[i]) if np.isfinite(speed[i]) else 0.0, 2),
                "elbow_angle": round(float(elbow_angle[i]) if elbow_angle is not None and np.isfinite(elbow_angle[i]) else 0.0, 2),
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
            })

        metrics = {}
        if analysis:
            for k in [
                "nvp", "straightness", "pause_time_sec", "number_of_stops",
                "movement_time_sec", "peak_velocity_px_s", "time_to_peak_velocity_sec",
                "elbow_angle_mean_deg", "elbow_angle_range_deg",
                "shoulder_elevation_norm", "trunk_ratio", "sparc",
                "hand_displacement_px", "hand_displacement_cm", "hand_displacement_norm",
                "shoulder_elevation_cm", "shoulder_elevation_abs_px",
                "shoulder_width_px", "shoulder_width_cm", "cm_per_px",
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

        return {
            "fps": round(float(target_fs), 2),
            "duration_sec": round(float(t1 - t0), 3),
            "affected_side": side,
            "frames": frames,
            "metrics": metrics,
            "movement_window": {"start_idx": int(onset_idx), "end_idx": int(offset_idx)},
            "peak_velocity_px_s": round(float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0, 2),
            "velocity_profile": velocity_profile,
            "elbow_angle_profile": elbow_angle_profile,
            "trunk_x_profile": trunk_x_profile,
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
