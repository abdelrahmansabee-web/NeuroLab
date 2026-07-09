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

from sparc_production import sparc_production


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


def _compute_sparc_profile(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    fs: float,
    start_idx: int,
    end_idx: int,
    min_segment_frames: int = 10,
) -> Dict[str, Any]:
    """
    Compute cumulative SPARC smoothness up to every frame from movement start.

    Returns per-frame SPARC values and verdicts.  Frames before the movement
    window or with too-short trajectories are returned as None.

    NaNs are linearly interpolated so brief tracking gaps do not prevent SPARC
    computation (the module itself auto-trims static segments).

    A final fallback SPARC is computed across the whole movement window if the
    cumulative per-frame values remain None.
    """
    palm_x = np.asarray(palm_x, dtype=float)
    palm_y = np.asarray(palm_y, dtype=float)
    n = len(palm_x)
    sparc_values: List[Optional[float]] = [None] * n
    sparc_verdicts: List[Optional[str]] = [None] * n
    debug: Dict[str, Any] = {
        "start_idx": int(start_idx),
        "end_idx": int(end_idx),
        "input_frames": n,
        "finite_x": int(np.isfinite(palm_x).sum()),
        "finite_y": int(np.isfinite(palm_y).sum()),
        "per_frame_attempts": 0,
        "per_frame_success": 0,
        "first_error": None,
    }

    start_idx = max(0, int(start_idx))
    end_idx = max(start_idx, min(n - 1, int(end_idx)))
    if n - start_idx < min_segment_frames:
        debug["short_circuit"] = "movement_window_too_short"
        return {"values": sparc_values, "verdicts": sparc_verdicts, "debug": debug}

    def _clean(arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        finite = np.isfinite(arr)
        if finite.all():
            return arr
        idx = np.arange(len(arr))
        if finite.sum() < 2:
            return arr
        arr = arr.copy()
        arr[~finite] = np.interp(idx[~finite], idx[finite], arr[finite])
        return arr

    clean_x = _clean(palm_x)
    clean_y = _clean(palm_y)

    for i in range(start_idx + min_segment_frames - 1, n):
        x_seg = clean_x[start_idx : i + 1]
        y_seg = clean_y[start_idx : i + 1]
        if len(x_seg) < min_segment_frames:
            continue
        debug["per_frame_attempts"] += 1
        try:
            result = sparc_production(
                x_seg,
                y_seg,
                fs=fs,
                n_points=100,
                auto_trim=True,
                smooth_sigma=1.5,
                speed_threshold_ratio=0.12,
                validate=True,
            )
            sparc_values[i] = result.get("sparc")
            sparc_verdicts[i] = result.get("verdict")
            if result.get("sparc") is not None:
                debug["per_frame_success"] += 1
        except Exception as exc:
            if debug["first_error"] is None:
                debug["first_error"] = f"{type(exc).__name__}: {exc}"

    # Fallback: compute SPARC across the full movement window once and use it for
    # every frame in the window if per-frame computation yielded nothing.
    if debug["per_frame_success"] == 0:
        full_x = clean_x[start_idx : end_idx + 1]
        full_y = clean_y[start_idx : end_idx + 1]
        debug["fallback_window_frames"] = len(full_x)
        if len(full_x) >= min_segment_frames:
            try:
                result = sparc_production(
                    full_x,
                    full_y,
                    fs=fs,
                    n_points=100,
                    auto_trim=True,
                    smooth_sigma=1.5,
                    speed_threshold_ratio=0.12,
                    validate=True,
                )
                fallback_sparc = result.get("sparc")
                fallback_verdict = result.get("verdict")
                debug["fallback_sparc"] = fallback_sparc
                debug["fallback_verdict"] = fallback_verdict
                for i in range(start_idx, end_idx + 1):
                    sparc_values[i] = fallback_sparc
                    sparc_verdicts[i] = fallback_verdict
            except Exception as exc:
                debug["fallback_error"] = f"{type(exc).__name__}: {exc}"
        else:
            debug["fallback_skipped"] = "window_too_short"

    return {"values": sparc_values, "verdicts": sparc_verdicts, "debug": debug}


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

        def _hip_estimate(sx, sy, kx, ky, center_x):
            """Estimate hip from shoulder and knee (40% of the way from shoulder to knee)."""
            sx = np.asarray(sx, dtype=float)
            sy = np.asarray(sy, dtype=float)
            kx = np.asarray(kx, dtype=float)
            ky = np.asarray(ky, dtype=float)
            est_x = sx + (kx - sx) * 0.40
            est_y = sy + (ky - sy) * 0.40
            # Pull x toward body center so pelvis is narrower than knees/shoulders
            est_x = center_x + (est_x - center_x) * 0.75
            return est_x, est_y

        est_lh_x, est_lh_y = _hip_estimate(ls_x_arr, ls_y_arr, lk_x_arr, lk_y_arr, shoulder_center_x)
        est_rh_x, est_rh_y = _hip_estimate(rs_x_arr, rs_y_arr, rk_x_arr, rk_y_arr, shoulder_center_x)

        def _hip_fallback(x, y, est_x, est_y, shoulder_y, knee_y):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            missing = ~(np.isfinite(x) & np.isfinite(y))
            # Hip must be below the shoulder and above the knee to be trustworthy.
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

        # Compute cumulative SPARC smoothness up to each frame for the live overlay.
        sparc_out = _compute_sparc_profile(
            palm_x, palm_y, fs=target_fs, start_idx=int(onset_idx), end_idx=int(offset_idx)
        )
        sparc_values = sparc_out["values"]
        sparc_verdicts = sparc_out["verdicts"]
        sparc_debug = sparc_out["debug"]

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
                "sparc": round(float(sparc_values[i]), 3) if sparc_values[i] is not None else None,
                "sparc_verdict": sparc_verdicts[i],
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

        sparc_profile = None
        if fs:
            sparc_profile = {
                "t": (np.arange(len(sparc_values)) / fs).tolist(),
                "v": [float(v) if v is not None and np.isfinite(v) else 0.0 for v in sparc_values],
            }

        # Prefer final SPARC from the analysis JSON if available; otherwise use the
        # last computed overlay value (at movement offset) for the metrics panel.
        final_sparc = None
        if analysis and "sparc" in analysis and analysis["sparc"] is not None:
            try:
                final_sparc = float(analysis["sparc"])
            except Exception:
                pass
        if final_sparc is None and offset_idx < len(sparc_values) and sparc_values[int(offset_idx)] is not None:
            final_sparc = float(sparc_values[int(offset_idx)])
        if final_sparc is not None:
            metrics["sparc"] = final_sparc

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
            "sparc_profile": sparc_profile,
            "sparc_debug": sparc_debug,
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
