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


def _to_float_list(a: np.ndarray) -> List[float]:
    return [float(x) if np.isfinite(x) else None for x in a]


def _norm_series(df: pd.DataFrame, name: str, coord: str) -> pd.Series:
    """Return a normalized [0,1] series for a MediaPipe-style landmark column."""
    cols = [f"{name}_{coord}", f"{name}_{coord.upper()}", f"{name.lower()}_{coord.lower()}"]
    for c in cols:
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(np.nan, index=df.index)


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
              "palm": [x, y],
              "wrist": [x, y],
              "shoulder": [x, y],
              "elbow": [x, y],
              "trunk": [x, y],
              "nose": [x, y],
              "lshoulder": [x, y],
              "rshoulder": [x, y],
              "lelbow": [x, y],
              "relbow": [x, y],
              "lwrist": [x, y],
              "rwrist": [x, y],
              "lhip": [x, y],
              "rhip": [x, y],
              "lindex": [x, y],
              "rindex": [x, y],
          }],
          "metrics": {...},
          "movement_window": {"start_idx": int, "end_idx": int},
          "peak_velocity_px_s": float,
        }
    """
    try:
        csv_path = Path(csv_path)
        if not csv_path.exists():
            return {"error": f"CSV not found: {csv_path}"}

        df = pd.read_csv(csv_path)
        if len(df) < 2:
            return {"error": "Too few frames"}

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

        # Resample to target_fs.
        t0, t1 = float(t[0]), float(t[-1])
        if t1 <= t0:
            return {"error": "Invalid time range"}
        n_target = max(2, int(round((t1 - t0) * target_fs)) + 1)
        new_t = np.linspace(t0, t1, n_target)

        def _resample(col: pd.Series) -> np.ndarray:
            y = pd.to_numeric(col, errors="coerce").values
            if np.all(np.isnan(y)):
                return np.full(len(new_t), np.nan)
            mask = np.isfinite(y)
            if mask.sum() < 2:
                return np.full(len(new_t), np.nan)
            return np.interp(new_t, t[mask], y[mask])

        def _pair(name: str):
            x = _resample(_norm_series(df, name, "x"))
            y = _resample(_norm_series(df, name, "y"))
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
        if len(canon) != len(new_t):
            # Interpolate canonical columns to new_t as well.
            canon_t = pd.to_numeric(canon["time"], errors="coerce").values
            for col in canon.columns:
                if col == "time":
                    continue
                canon[col] = np.interp(new_t, canon_t, pd.to_numeric(canon[col], errors="coerce").values)

        # Canonical columns are in pixels; normalize to [0,1].
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
        onset_idx, offset_idx = _movement_window(
            speed, fs=target_fs, velocity_threshold_px_s=float(analysis.get("velocity_threshold_px_s", 5.0)) if analysis else 5.0
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
        li_x, li_y = _pair("LEFT_INDEX")
        ri_x, ri_y = _pair("RIGHT_INDEX")

        # Clamp coordinates to [0,1].
        def _clamp01(a: np.ndarray) -> np.ndarray:
            return np.clip(np.nan_to_num(a, nan=0.0), 0.0, 1.0)

        def _make_pair(x: np.ndarray, y: np.ndarray) -> List[Optional[float]]:
            return [[float(_clamp01(x[i])), float(_clamp01(y[i]))] for i in range(len(new_t))]

        frames = []
        for i in range(len(new_t)):
            frames.append({
                "time": round(float(new_t[i]), 4),
                "speed": round(float(speed[i]) if np.isfinite(speed[i]) else 0.0, 2),
                "palm": [float(_clamp01(palm_x[i])), float(_clamp01(palm_y[i]))],
                "wrist": [float(_clamp01(wrist_x[i])), float(_clamp01(wrist_y[i]))],
                "shoulder": [float(_clamp01(shoulder_x[i])), float(_clamp01(shoulder_y[i]))],
                "elbow": [float(_clamp01(elbow_x[i])), float(_clamp01(elbow_y[i]))],
                "trunk": [float(_clamp01(trunk_x[i])), float(_clamp01(trunk_y[i]))],
                "nose": [float(_clamp01(nose_x[i])), float(_clamp01(nose_y[i]))],
                "lshoulder": [float(_clamp01(ls_x[i])), float(_clamp01(ls_y[i]))],
                "rshoulder": [float(_clamp01(rs_x[i])), float(_clamp01(rs_y[i]))],
                "lelbow": [float(_clamp01(le_x[i])), float(_clamp01(le_y[i]))],
                "relbow": [float(_clamp01(re_x[i])), float(_clamp01(re_y[i]))],
                "lwrist": [float(_clamp01(lw_x[i])), float(_clamp01(lw_y[i]))],
                "rwrist": [float(_clamp01(rw_x[i])), float(_clamp01(rw_y[i]))],
                "lhip": [float(_clamp01(lh_x[i])), float(_clamp01(lh_y[i]))],
                "rhip": [float(_clamp01(rh_x[i])), float(_clamp01(rh_y[i]))],
                "lindex": [float(_clamp01(li_x[i])), float(_clamp01(li_y[i]))],
                "rindex": [float(_clamp01(ri_x[i])), float(_clamp01(ri_y[i]))],
            })

        metrics = {}
        if analysis:
            for k in [
                "nvp", "straightness", "pause_time_sec", "number_of_stops",
                "movement_time_sec", "peak_velocity_px_s", "time_to_peak_velocity_sec",
                "elbow_angle_mean_deg", "elbow_angle_range_deg",
                "shoulder_elevation_norm", "trunk_ratio", "sparc",
            ]:
                if k in analysis and analysis[k] is not None:
                    try:
                        metrics[k] = float(analysis[k]) if not isinstance(analysis[k], (str, bool)) else analysis[k]
                    except Exception:
                        pass

        return {
            "fps": round(float(target_fs), 2),
            "duration_sec": round(float(t1 - t0), 3),
            "affected_side": side,
            "frames": frames,
            "metrics": metrics,
            "movement_window": {"start_idx": int(onset_idx), "end_idx": int(offset_idx)},
            "peak_velocity_px_s": round(float(np.nanmax(speed)) if np.any(np.isfinite(speed)) else 0.0, 2),
        }
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    result = build_overlay_data(sys.argv[1])
    print(json.dumps({k: v for k, v in result.items() if k != "frames"}, indent=2))
    print("frames:", len(result.get("frames", [])))
