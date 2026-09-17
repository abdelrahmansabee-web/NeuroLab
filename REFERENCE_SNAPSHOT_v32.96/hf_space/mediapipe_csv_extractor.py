# -*- coding: utf-8 -*-
"""
mediapipe_csv_extractor.py — Highest-quality kinematic CSV from video.

Pipeline:
  1. MediaPipe Pose Landmarker Heavy (VIDEO mode)
  2. CLAHE preprocessing + visibility gating + gap interpolation
  3. Derived analysis columns (palm, trunk, shoulder, elbow) in pixels
  4. Butterworth low-pass on coordinates (reduces SPARC jitter)
  5. Auto camera-view + affected-side detection (side / frontal / oblique)

Primary output (*_landmarks.csv): ready for stroke_kinematic_pipeline.analyze_trial
Optional output (*_raw_pose.csv): full 33-landmark audit trail
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from extract_pose_csv_robust import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    LANDMARK_NAMES,
    extract_pose_to_csv,
)

ANALYSIS_COLUMNS = [
    "frame",
    "time",
    "fps",
    "frame_width_px",
    "frame_height_px",
    "camera_view",
    "affected_side",
    "shoulder_width",
    "palm_x",
    "palm_y",
    "wrist_x",
    "wrist_y",
    "trunk_x",
    "trunk_y",
    "shoulder_x",
    "shoulder_y",
    "elbow_x",
    "elbow_y",
    "palm_visibility",
    "wrist_visibility",
    "shoulder_visibility",
    "elbow_visibility",
    "trunk_visibility",
    "frame_quality_ok",
]


def default_velocity_threshold(frame_height: int) -> float:
    if frame_height >= 1080:
        return 5.0
    if frame_height >= 720:
        return 4.0
    return 3.0


def butterworth_filter_series(
    values: np.ndarray,
    fs: float,
    cutoff_hz: float = 4.0,
    order: int = 4,
) -> np.ndarray:
    """Zero-phase Butterworth along time; skips if too short or invalid fs."""
    arr = np.asarray(values, dtype=float)
    if len(arr) < max(order * 3, 12) or fs <= 0 or cutoff_hz <= 0:
        return arr
    nyq = 0.5 * fs
    wn = min(cutoff_hz / nyq, 0.99)
    if wn <= 0:
        return arr
    b, a = butter(order, wn, btype="low")
    try:
        return filtfilt(b, a, arr)
    except ValueError:
        return arr


def _col_norm(df: pd.DataFrame, name: str, axis: str) -> np.ndarray:
    return df[f"{name}_{axis}"].astype(float).values


def _col_vis(df: pd.DataFrame, name: str) -> np.ndarray:
    key = f"{name}_VISIBILITY"
    if key in df.columns:
        return df[key].astype(float).values
    return np.ones(len(df), dtype=float)


def _bridge_gaps_mask(mask: np.ndarray, max_gap: int = 6) -> np.ndarray:
    out = mask.astype(bool).copy()
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


def _primary_reach_window(
    speed: np.ndarray,
    fs: float = 30.0,
    velocity_threshold: float = 5.0,
    max_gap_frames: int = 6,
    min_segment_frames: int = 10,
) -> tuple:
    if len(speed) == 0:
        return 0, 0
    peak = float(np.max(speed))
    thr = max(float(velocity_threshold), 0.05 * peak)
    mask = _bridge_gaps_mask(speed > thr, max_gap_frames)
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
        idx = np.where(speed > thr)[0]
        if len(idx) >= min_segment_frames:
            return int(idx[0]), int(idx[-1])
        return 0, max(0, n - 1)
    return best_s, best_e


def _palm_series(raw: pd.DataFrame, side: str, frame_width: int, frame_height: int) -> tuple:
    p = side.upper()
    wx = _col_norm(raw, f"{p}_WRIST", "X") * frame_width
    wy = _col_norm(raw, f"{p}_WRIST", "Y") * frame_height
    ix = _col_norm(raw, f"{p}_INDEX", "X") * frame_width
    iy = _col_norm(raw, f"{p}_INDEX", "Y") * frame_height
    return (wx + ix) / 2.0, (wy + iy) / 2.0


def _shoulder_series(raw: pd.DataFrame, side: str, frame_width: int, frame_height: int) -> tuple:
    p = side.upper()
    sx = _col_norm(raw, f"{p}_SHOULDER", "X") * frame_width
    sy = _col_norm(raw, f"{p}_SHOULDER", "Y") * frame_height
    return sx, sy


def _elbow_angle_series(
    raw: pd.DataFrame, side: str, frame_width: int, frame_height: int
) -> np.ndarray:
    p = side.upper()
    sx = _col_norm(raw, f"{p}_SHOULDER", "X") * frame_width
    sy = _col_norm(raw, f"{p}_SHOULDER", "Y") * frame_height
    ex = _col_norm(raw, f"{p}_ELBOW", "X") * frame_width
    ey = _col_norm(raw, f"{p}_ELBOW", "Y") * frame_height
    wx = _col_norm(raw, f"{p}_WRIST", "X") * frame_width
    wy = _col_norm(raw, f"{p}_WRIST", "Y") * frame_height
    a1 = np.arctan2(sy - ey, sx - ex)
    a2 = np.arctan2(wy - ey, wx - ex)
    ang = np.degrees(np.abs(a1 - a2))
    return np.minimum(ang, 360.0 - ang)


def detect_active_arm_with_meta(
    raw: pd.DataFrame,
    frame_width: int,
    frame_height: int,
    fs: float = 30.0,
    velocity_threshold: float = 5.0,
) -> dict:
    """
    Auto-detect the more active arm during the primary reach window.
    Each side is scored inside its own reach bout (avoids jitter on the idle arm).
    """
    if raw is None or len(raw) < 5:
        return {
            "side": "right",
            "confidence": 0.0,
            "scores": {"left": 0.0, "right": 0.0},
            "method": "kinematic_fusion",
        }

    side_speeds: dict[str, np.ndarray] = {}
    side_paths: dict[str, np.ndarray] = {}
    side_windows: dict[str, tuple] = {}
    metrics: dict[str, dict[str, float]] = {}
    rest_n = max(3, min(len(raw), int(round(0.1 * len(raw)))))

    for side in ("left", "right"):
        try:
            px, py = _palm_series(raw, side, frame_width, frame_height)
            sx, sy = _shoulder_series(raw, side, frame_width, frame_height)
            vx = np.gradient(px) * fs
            vy = np.gradient(py) * fs
            speed = np.sqrt(vx**2 + vy**2)
            side_speeds[side] = speed
            side_paths[side] = np.hypot(np.gradient(px), np.gradient(py))
            side_windows[side] = _primary_reach_window(
                speed, fs=fs, velocity_threshold=velocity_threshold
            )
        except KeyError:
            side_speeds[side] = np.zeros(len(raw))
            side_paths[side] = np.zeros(len(raw))
            side_windows[side] = (0, max(0, len(raw) - 1))

    combined = np.maximum(side_speeds["left"], side_speeds["right"])
    peak = float(np.nanmax(combined)) if len(combined) else 0.0
    thr = max(float(velocity_threshold), 0.05 * peak)

    for side in ("left", "right"):
        try:
            px, py = _palm_series(raw, side, frame_width, frame_height)
            sx, sy = _shoulder_series(raw, side, frame_width, frame_height)
            speed = side_speeds[side]
            path = side_paths[side]
            vis = float(np.nanmean(_col_vis(raw, f"{side.upper()}_WRIST")))
        except KeyError:
            metrics[side] = {k: 0.0 for k in ("path", "speed_int", "peak", "disp", "reach", "extension", "active", "elbow_rom", "trial_disp")}
            continue

        start_i, end_i = side_windows[side]
        seg = slice(start_i, end_i + 1)
        rest_x = float(np.nanmedian(px[:rest_n]))
        rest_y = float(np.nanmedian(py[:rest_n]))
        try:
            elbow_ang = _elbow_angle_series(raw, side, frame_width, frame_height)
            elbow_rom = float(np.nanmax(elbow_ang) - np.nanmin(elbow_ang))
        except KeyError:
            elbow_rom = 0.0
        trial_disp = float(
            np.nanmax(np.hypot(px - rest_x, py - rest_y))
        ) if np.isfinite(rest_x) and np.isfinite(rest_y) else 0.0
        seg_px = px[seg]
        seg_py = py[seg]
        seg_sx = sx[seg]
        seg_sy = sy[seg]
        seg_speed = speed[seg]

        path_len = float(np.nansum(path[seg]))
        speed_int = float(np.nansum(seg_speed)) / max(fs, 1e-6)
        peak_spd = float(np.nanmax(seg_speed)) if len(seg_speed) else 0.0
        if np.isfinite(rest_x) and np.isfinite(rest_y) and len(seg_px):
            disp = float(
                np.nanmax(
                    np.hypot(seg_px - rest_x, seg_py - rest_y)
                )
            )
            reach = float(
                np.nanmax(np.hypot(seg_px - seg_sx, seg_py - seg_sy))
            )
            rest_reach = float(
                np.nanmedian(np.hypot(px[:rest_n] - sx[:rest_n], py[:rest_n] - sy[:rest_n]))
            )
            extension = max(0.0, reach - rest_reach)
        else:
            disp = reach = extension = 0.0
        active = float(np.sum(seg_speed > thr))
        vis_w = max(vis, 0.1)

        metrics[side] = {
            "path": path_len * vis_w,
            "speed_int": speed_int * vis_w,
            "peak": peak_spd * vis_w,
            "disp": disp * vis_w,
            "reach": reach * vis_w,
            "extension": extension * vis_w,
            "active": active * vis_w,
            "elbow_rom": elbow_rom * vis_w,
            "trial_disp": trial_disp * vis_w,
        }

    weights = {
        "trial_disp": 0.22,
        "reach": 0.22,
        "extension": 0.14,
        "elbow_rom": 0.12,
        "disp": 0.12,
        "peak": 0.08,
        "speed_int": 0.06,
        "path": 0.04,
        "active": 0.0,
    }
    scores: dict[str, float] = {}
    for side in ("left", "right"):
        m = metrics.get(side, {})
        total = 0.0
        for key, w in weights.items():
            vals = [metrics[s].get(key, 0.0) for s in ("left", "right")]
            vmax = max(vals) if vals else 0.0
            norm = (m.get(key, 0.0) / vmax) if vmax > 1e-9 else 0.0
            total += w * norm
        scores[side] = total

    left_score = scores.get("left", 0.0)
    right_score = scores.get("right", 0.0)
    if abs(left_score - right_score) < 0.05:
        left_td = metrics.get("left", {}).get("trial_disp", 0.0)
        right_td = metrics.get("right", {}).get("trial_disp", 0.0)
        side = "right" if right_td >= left_td else "left"
    else:
        side = "left" if left_score >= right_score else "right"
    denom = left_score + right_score
    confidence = abs(left_score - right_score) / denom if denom > 1e-9 else 0.0

    win = side_windows.get(side, (0, max(0, len(raw) - 1)))
    return {
        "side": side,
        "confidence": round(float(confidence), 3),
        "scores": {k: round(float(v), 4) for k, v in scores.items()},
        "method": "kinematic_fusion",
        "window_frames": [int(win[0]), int(win[1])],
    }


def detect_active_arm(
    raw: pd.DataFrame,
    frame_width: int,
    frame_height: int,
    fs: float = 30.0,
    velocity_threshold: float = 5.0,
) -> str:
    """Auto-select the more active arm during the primary reach window."""
    return detect_active_arm_with_meta(
        raw, frame_width, frame_height, fs=fs, velocity_threshold=velocity_threshold
    )["side"]


def detect_affected_side(raw: pd.DataFrame, frame_width: int, frame_height: int) -> str:
    """Alias — auto-select the more active arm during reach."""
    fs = 30.0
    if "time" in raw.columns and len(raw) > 2:
        dt = float(np.median(np.diff(raw["time"].astype(float).values)))
        if dt > 0:
            fs = 1.0 / dt
    return detect_active_arm(raw, frame_width, frame_height, fs=fs)


# MediaPipe pose skeleton (landmark index pairs)
_POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31), (27, 31),
    (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
    (15, 17), (15, 19), (15, 21), (17, 19),
    (16, 18), (16, 20), (16, 22), (18, 20),
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
]
_LEFT_ARM_IDX = {11, 13, 15, 17, 19, 21}
_RIGHT_ARM_IDX = {12, 14, 16, 18, 20, 22}
_NAME_TO_IDX = {n: i for i, n in enumerate(LANDMARK_NAMES)}


def _row_landmark_xy(row: pd.Series, name: str, frame_width: int, frame_height: int) -> Optional[Tuple[int, int]]:
    for xs, ys in ((f"{name}_X", f"{name}_Y"), (f"{name}_x", f"{name}_y")):
        if xs in row.index and ys in row.index:
            x, y = row[xs], row[ys]
            if pd.notna(x) and pd.notna(y):
                return int(float(x) * frame_width), int(float(y) * frame_height)
    return None


def render_skeleton_validation_video(
    video_path: str,
    raw_pose_csv: str,
    output_mp4: str,
    analyzed_side: str = "auto",
    min_visibility: float = 0.25,
) -> str:
    """
    Overlay MediaPipe landmarks on the source video for visual QA.
    Analyzed arm is drawn in cyan; other landmarks in green.
    """
    import cv2

    video_path = Path(video_path)
    raw_pose_csv = Path(raw_pose_csv)
    output_mp4 = Path(output_mp4)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not raw_pose_csv.exists():
        raise FileNotFoundError(f"Raw pose CSV not found: {raw_pose_csv}")

    df = pd.read_csv(raw_pose_csv)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    side = (analyzed_side or "auto").lower()
    if side not in ("left", "right"):
        side = detect_active_arm(df, frame_width, frame_height, fs=fps)

    highlight = _LEFT_ARM_IDX if side == "left" else _RIGHT_ARM_IDX
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_mp4),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot create video writer: {output_mp4}")

    frame_i = 0
    n_rows = len(df)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        row = df.iloc[min(frame_i, n_rows - 1)] if n_rows else None
        if row is not None:
            points: Dict[int, Tuple[int, int]] = {}
            for name, idx in _NAME_TO_IDX.items():
                vis_key = f"{name}_VISIBILITY"
                if vis_key in row.index and float(row[vis_key]) < min_visibility:
                    continue
                pt = _row_landmark_xy(row, name, frame_width, frame_height)
                if pt:
                    points[idx] = pt

            for a, b in _POSE_CONNECTIONS:
                if a not in points or b not in points:
                    continue
                is_arm = a in highlight or b in highlight
                color = (255, 220, 0) if is_arm else (0, 220, 80)
                thickness = 3 if is_arm else 2
                cv2.line(frame, points[a], points[b], color, thickness, cv2.LINE_AA)

            for idx, pt in points.items():
                is_arm = idx in highlight
                color = (255, 220, 0) if is_arm else (0, 0, 255)
                radius = 5 if is_arm else 3
                cv2.circle(frame, pt, radius, color, -1, lineType=cv2.LINE_AA)

            label = f"Analyzed: {side.upper()} arm"
            cv2.rectangle(frame, (8, 8), (8 + 220, 40), (0, 0, 0), -1)
            cv2.putText(frame, label, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        writer.write(frame)
        frame_i += 1

    cap.release()
    writer.release()
    if frame_i == 0 or not output_mp4.exists() or output_mp4.stat().st_size < 1000:
        raise RuntimeError("Skeleton validation video was not written")
    return str(output_mp4)


def detect_camera_view(
    raw: pd.DataFrame,
    frame_width: int,
    frame_height: int,
) -> str:
    """
    Soft label for *body orientation in the frame* (not camera mount angle).
    Kinematic metrics use body-normalized / 3D coords and do not gate on this.
    """
    from motion_invariants import detect_body_orientation

    info = detect_body_orientation(raw, frame_width, frame_height)
    return str(info.get("label") or "unknown")


def _build_coords_from_raw(
    raw: pd.DataFrame,
    affected_side: str,
    frame_width: int,
    frame_height: int,
    *,
    refine_landmarks: bool = True,
) -> Dict[str, np.ndarray]:
    from landmark_tracker_enhance import compute_trunk_coords, infer_fps_from_df, refine_pose_landmarks_df

    side = affected_side.lower()
    if side not in ("left", "right"):
        side = detect_affected_side(raw, frame_width, frame_height)

    work = raw
    if refine_landmarks and "LEFT_SHOULDER_X" in raw.columns:
        work = refine_pose_landmarks_df(raw, fps=infer_fps_from_df(raw))

    p = side.upper()

    wrist_x = _col_norm(work, f"{p}_WRIST", "X") * frame_width
    wrist_y = _col_norm(work, f"{p}_WRIST", "Y") * frame_height
    index_x = _col_norm(work, f"{p}_INDEX", "X") * frame_width
    index_y = _col_norm(work, f"{p}_INDEX", "Y") * frame_height
    palm_x = (wrist_x + index_x) / 2.0
    palm_y = (wrist_y + index_y) / 2.0

    shoulder_x = _col_norm(work, f"{p}_SHOULDER", "X") * frame_width
    shoulder_y = _col_norm(work, f"{p}_SHOULDER", "Y") * frame_height
    elbow_x = _col_norm(work, f"{p}_ELBOW", "X") * frame_width
    elbow_y = _col_norm(work, f"{p}_ELBOW", "Y") * frame_height

    ls_x = _col_norm(work, "LEFT_SHOULDER", "X") * frame_width
    ls_y = _col_norm(work, "LEFT_SHOULDER", "Y") * frame_height
    rs_x = _col_norm(work, "RIGHT_SHOULDER", "X") * frame_width
    rs_y = _col_norm(work, "RIGHT_SHOULDER", "Y") * frame_height
    lh_x = _col_norm(work, "LEFT_HIP", "X") * frame_width
    lh_y = _col_norm(work, "LEFT_HIP", "Y") * frame_height
    rh_x = _col_norm(work, "RIGHT_HIP", "X") * frame_width
    rh_y = _col_norm(work, "RIGHT_HIP", "Y") * frame_height

    trunk_x, trunk_y = compute_trunk_coords(ls_x, ls_y, rs_x, rs_y, lh_x, lh_y, rh_x, rh_y)

    shoulder_width = float(np.nanmedian(np.hypot(rs_x - ls_x, rs_y - ls_y)))

    return {
        "affected_side": side,
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
        "palm_visibility": (_col_vis(raw, f"{p}_WRIST") + _col_vis(raw, f"{p}_INDEX")) / 2.0,
        "wrist_visibility": _col_vis(raw, f"{p}_WRIST"),
        "shoulder_visibility": _col_vis(raw, f"{p}_SHOULDER"),
        "elbow_visibility": _col_vis(raw, f"{p}_ELBOW"),
        "trunk_visibility": (
            _col_vis(raw, f"{p}_SHOULDER")
            + _col_vis(raw, "LEFT_HIP")
            + _col_vis(raw, "RIGHT_HIP")
        ) / 3.0,
    }


def build_analysis_dataframe(
    raw: pd.DataFrame,
    frame_width: int,
    frame_height: int,
    fps: float,
    affected_side: str = "auto",
    camera_view: str = "auto",
    butterworth_cutoff_hz: float = 4.0,
    butterworth_order: int = 4,
    min_visibility: float = 0.35,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    side = affected_side.lower()
    side_meta: dict = {}
    if side == "auto":
        det = detect_active_arm_with_meta(raw, frame_width, frame_height, fs=fps)
        side = det["side"]
        side_meta = {
            "side_detection_confidence": det["confidence"],
            "side_detection_scores": det["scores"],
            "side_detection_method": det["method"],
            "side_detection_window": det.get("window_frames"),
        }
    elif side not in ("left", "right"):
        det = detect_active_arm_with_meta(raw, frame_width, frame_height, fs=fps)
        side = det["side"]
        side_meta = {
            "side_detection_confidence": det["confidence"],
            "side_detection_scores": det["scores"],
            "side_detection_method": det["method"],
            "side_detection_window": det.get("window_frames"),
        }

    view = camera_view.lower()
    if view == "auto":
        view = detect_camera_view(raw, frame_width, frame_height)

    from landmark_tracker_enhance import infer_fps_from_df, refine_pose_landmarks_df

    fs = float(fps) if fps else 30.0
    raw_refined = refine_pose_landmarks_df(raw, fps=fs)

    coords = _build_coords_from_raw(raw_refined, side, frame_width, frame_height, refine_landmarks=False)
    fs = float(fps) if fps else infer_fps_from_df(raw_refined)

    coord_keys = [
        "palm_x", "palm_y", "wrist_x", "wrist_y",
        "trunk_x", "trunk_y", "shoulder_x", "shoulder_y", "elbow_x", "elbow_y",
    ]
    for key in coord_keys:
        coords[key] = butterworth_filter_series(
            coords[key], fs=fs, cutoff_hz=butterworth_cutoff_hz, order=butterworth_order
        )

    shoulder_width = coords["shoulder_width"]
    n = len(raw)
    out = pd.DataFrame({
        "frame": raw["frame"].values if "frame" in raw.columns else np.arange(n),
        "time": raw["time"].values if "time" in raw.columns else np.arange(n) / fs,
        "fps": np.full(n, fs),
        "frame_width_px": np.full(n, frame_width),
        "frame_height_px": np.full(n, frame_height),
        "camera_view": np.full(n, view),
        "affected_side": np.full(n, side),
        "shoulder_width": np.full(n, shoulder_width),
        **{k: coords[k] for k in coord_keys},
        "palm_visibility": coords["palm_visibility"],
        "wrist_visibility": coords["wrist_visibility"],
        "shoulder_visibility": coords["shoulder_visibility"],
        "elbow_visibility": coords["elbow_visibility"],
        "trunk_visibility": coords["trunk_visibility"],
    })

    out["frame_quality_ok"] = (
        (out["palm_visibility"] >= min_visibility)
        & (out["shoulder_visibility"] >= min_visibility)
        & (out["elbow_visibility"] >= min_visibility)
    ).astype(int)

    meta = {
        "affected_side": side,
        "camera_view": view,
        "shoulder_width_px": round(shoulder_width, 2) if np.isfinite(shoulder_width) else None,
        "fps": round(fs, 3),
        "frame_width_px": frame_width,
        "frame_height_px": frame_height,
        "butterworth_cutoff_hz": butterworth_cutoff_hz,
        "butterworth_order": butterworth_order,
        "velocity_threshold_px_s": default_velocity_threshold(frame_height),
        "percent_good_frames": round(float(out["frame_quality_ok"].mean()) * 100, 1),
        "mean_palm_visibility": round(float(out["palm_visibility"].mean()), 3),
        "landmark_tracking_enhanced": True,
        "trunk_proxy": "shoulder_girdle_midpoint",
        **side_meta,
    }
    return out, meta


def extract_from_video(
    video_path: str,
    output_csv: str,
    model_path: str = DEFAULT_MODEL_PATH,
    affected_side: str = "auto",
    camera_view: str = "auto",
    use_clahe: bool = True,
    max_interpolate_gap: int = 8,
    butterworth_cutoff_hz: float = 4.0,
    butterworth_order: int = 4,
    save_raw_pose: bool = True,
    show_progress: bool = True,
    legacy_format: bool = False,
    save_intermediate_frames: bool = False,
    intermediate_dir: Optional[str] = None,
    save_resampled: bool = True,
    resample_points: int = 1500,
) -> Dict[str, Any]:
    """
    Extract highest-quality analysis CSV from video.

    Returns quality report dict (also saves *_quality.json beside output).
    """
    video_path = Path(video_path)
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_path = output_path
    if save_raw_pose:
        raw_path = output_path.with_name(output_path.stem + "_raw_pose.csv")

    # Step 1: raw landmarks (MediaPipe heavy + CLAHE + interpolation)
    pose_kwargs: Dict[str, Any] = dict(
        video_path=str(video_path),
        output_csv=str(raw_path if save_raw_pose else output_path),
        model_path=model_path,
        use_clahe=use_clahe,
        smooth=True,
        max_interpolate_gap=max_interpolate_gap,
        show_progress=show_progress,
        legacy_format=legacy_format,
    )
    if save_intermediate_frames or intermediate_dir:
        inter_dir = Path(intermediate_dir) if intermediate_dir else output_path.parent / "intermediates"
        inter_dir.mkdir(parents=True, exist_ok=True)
        pose_kwargs["save_intermediate_frames"] = save_intermediate_frames
        pose_kwargs["intermediate_dir"] = str(inter_dir / "frames")
    pose_report = extract_pose_to_csv(**pose_kwargs)

    raw = pd.read_csv(raw_path if save_raw_pose else output_path)

    hand_report: Dict[str, Any] = {}
    try:
        from hand_landmarker_extract import merge_hand_landmarks_into_raw_csv

        hand_report = merge_hand_landmarks_into_raw_csv(
            str(video_path),
            str(raw_path if save_raw_pose else output_path),
            affected_side=affected_side,
            show_progress=show_progress,
        )
        if hand_report.get("hand_landmarker") == "ok":
            raw = pd.read_csv(raw_path if save_raw_pose else output_path)
    except Exception as exc:
        hand_report = {"hand_landmarker": "error", "message": str(exc)}

    import cv2

    cap = cv2.VideoCapture(str(video_path))
    cap_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    cap_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    cap.release()

    # Pose/HL run on rotate_cw-corrected frames — analysis pixels MUST use the same display size.
    frame_width = int(pose_report.get("frame_width_px") or cap_w)
    frame_height = int(pose_report.get("frame_height_px") or cap_h)

    fps = float(pose_report.get("fps") or 30.0)

    # Step 2: analysis-ready columns + Butterworth
    analysis_df, meta = build_analysis_dataframe(
        raw,
        frame_width=frame_width,
        frame_height=frame_height,
        fps=fps,
        affected_side=affected_side,
        camera_view=camera_view,
        butterworth_cutoff_hz=butterworth_cutoff_hz,
        butterworth_order=butterworth_order,
    )

    analysis_df.to_csv(output_path, index=False)

    report: Dict[str, Any] = {
        "success": True,
        "video": video_path.name,
        "output_csv": str(output_path),
        "raw_pose_csv": str(raw_path) if save_raw_pose else None,
        "frames": len(analysis_df),
        "extractor": "mediapipe_csv_extractor",
        **pose_report,
        **meta,
        **hand_report,
    }

    quality_path = output_path.with_suffix(".quality.json")
    quality_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["quality_json"] = str(quality_path)

    skeleton_path = output_path.with_name(output_path.stem + "_skeleton.mp4")
    try:
        render_skeleton_validation_video(
            video_path=str(video_path),
            raw_pose_csv=str(raw_path if save_raw_pose else output_path),
            output_mp4=str(skeleton_path),
            analyzed_side=meta.get("affected_side", affected_side),
        )
        report["validation_video"] = skeleton_path.name
        print(f"✓ Skeleton validation video: {skeleton_path.name}")
    except Exception as exc:
        print(f"  Skeleton video skipped: {exc}")
        report["validation_video"] = None

    print(f"\n✓ Analysis CSV: {output_path}")
    if save_raw_pose:
        print(f"✓ Raw pose CSV: {raw_path}")
    print(f"  Camera view: {meta['camera_view']} | Side: {meta['affected_side']}")
    print(f"  Good frames: {meta['percent_good_frames']}% | Palm vis: {meta['mean_palm_visibility']:.3f}")

    return report


def extract_landmarks_csv(*args, **kwargs) -> Dict[str, Any]:
    """Alias for analyze_trial-compatible output naming."""
    return extract_from_video(*args, **kwargs)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="High-quality MediaPipe kinematic CSV extractor")
    parser.add_argument("video", help="Input video path")
    parser.add_argument("-o", "--output", required=True, help="Output *_landmarks.csv path")
    parser.add_argument("--side", default="auto", choices=["auto", "left", "right"])
    parser.add_argument("--view", default="auto", choices=["auto", "side", "frontal", "oblique"])
    parser.add_argument("--no-clahe", action="store_true")
    parser.add_argument("--no-raw", action="store_true", help="Skip raw 33-landmark CSV")
    parser.add_argument("--cutoff", type=float, default=4.0, help="Butterworth cutoff Hz")
    parser.add_argument("--order", type=int, default=4, help="Butterworth order")
    parser.add_argument("--max-gap", type=int, default=8)
    args = parser.parse_args()

    extract_from_video(
        video_path=args.video,
        output_csv=args.output,
        affected_side=args.side,
        camera_view=args.view,
        use_clahe=not args.no_clahe,
        max_interpolate_gap=args.max_gap,
        butterworth_cutoff_hz=args.cutoff,
        butterworth_order=args.order,
        save_raw_pose=not args.no_raw,
    )


if __name__ == "__main__":
    main()
