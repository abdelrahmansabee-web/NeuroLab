# -*- coding: utf-8 -*-
"""
Optional MediaPipe Hand Landmarker pass — refines thumb/index tips for pinch metrics.

Merges columns into raw pose CSV: {SIDE}_HL_INDEX_TIP_X, {SIDE}_HL_THUMB_TIP_X, …
When the .task model is missing, extraction is skipped (pose INDEX/THUMB still used).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
import pandas as pd

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# MediaPipe hand landmark indices — MCP, IP (PIP), TIP per finger for grasp overlay.
_HAND_LM = {
    "WRIST": 0,
    "THUMB_MCP": 2,
    "THUMB_IP": 3,
    "THUMB_TIP": 4,
    "INDEX_MCP": 5,
    "INDEX_PIP": 6,
    "INDEX_TIP": 8,
    "MIDDLE_MCP": 9,
    "MIDDLE_PIP": 10,
    "MIDDLE_TIP": 12,
    "RING_MCP": 13,
    "RING_PIP": 14,
    "RING_TIP": 16,
    "PINKY_MCP": 17,
    "PINKY_PIP": 18,
    "PINKY_TIP": 20,
}


def _pose_norm_xy(raw: pd.DataFrame, frame_i: int, side: str, lm: str, axis: str = "X") -> float:
    ax = axis.upper()
    for suffix in (f"_{ax}", f"_{ax.lower()}"):
        col = f"{side}_{lm}{suffix}"
        if col in raw.columns:
            v = raw.at[frame_i, col]
            if pd.notna(v):
                return float(v)
    return float("nan")


def _resolve_roi_side(raw: pd.DataFrame, frame_i: int, affected_side: Optional[str]) -> Optional[str]:
    if affected_side and str(affected_side).upper() in ("LEFT", "RIGHT"):
        return str(affected_side).upper()
    best = None
    best_score = -1
    for side in ("LEFT", "RIGHT"):
        wx = _pose_norm_xy(raw, frame_i, side, "WRIST")
        ix = _pose_norm_xy(raw, frame_i, side, "INDEX")
        score = int(np.isfinite(wx)) + int(np.isfinite(ix))
        if score > best_score:
            best_score = score
            best = side
    return best if best_score > 0 else None


def _crop_hand_roi(
    bgr: np.ndarray,
    wx: float,
    wy: float,
    ix: float,
    iy: float,
    fw: int,
    fh: int,
    *,
    pad: float = 2.2,
    tx: Optional[float] = None,
    ty: Optional[float] = None,
) -> Tuple[np.ndarray, int, int, int, int]:
    """Crop a square ROI around wrist–index (and thumb when raised) for tighter HL detection."""
    pts_x = [wx * fw, ix * fw]
    pts_y = [wy * fh, iy * fh]
    if tx is not None and ty is not None and np.isfinite(tx) and np.isfinite(ty):
        pts_x.append(tx * fw)
        pts_y.append(ty * fh)
    cx = float(np.mean(pts_x))
    cy = float(np.mean(pts_y))
    span_x = max(abs(px - cx) for px in pts_x) if len(pts_x) > 1 else abs(ix - wx) * fw
    span_y = max(abs(py - cy) for py in pts_y) if len(pts_y) > 1 else abs(iy - wy) * fh
    span = max(span_x, span_y, abs(ix - wx) * fw, abs(iy - wy) * fh, 0.07 * min(fw, fh), 56.0)
    if wy < 0.55 or iy < 0.55:
        span *= 1.45
        pad = max(pad, 3.0)
    span *= pad
    x0 = int(max(0, round(cx - span * 0.5)))
    y0 = int(max(0, round(cy - span * 0.5)))
    x1 = int(min(fw, round(cx + span * 0.5)))
    y1 = int(min(fh, round(cy + span * 0.5)))
    if x1 - x0 < 40 or y1 - y0 < 40:
        return bgr, 0, 0, fw, fh
    return bgr[y0:y1, x0:x1], x0, y0, x1 - x0, y1 - y0


def _handedness_label(result, hand_idx: int) -> str:
    handedness = "RIGHT"
    if result.handedness and hand_idx < len(result.handedness):
        cat = result.handedness[hand_idx]
        if cat and len(cat) > 0:
            label = (cat[0].category_name or "").upper()
            if "LEFT" in label:
                handedness = "LEFT"
            elif "RIGHT" in label:
                handedness = "RIGHT"
    return handedness


def _hl_wrist_norm(
    hand_lms,
    x0: int,
    y0: int,
    cw: int,
    ch: int,
    fw: int,
    fh: int,
) -> Tuple[float, float]:
    lm = hand_lms[_HAND_LM["WRIST"]]
    return float((x0 + lm.x * cw) / fw), float((y0 + lm.y * ch) / fh)


def _pose_wrist_dist(raw: pd.DataFrame, frame_i: int, side: str, wx: float, wy: float) -> float:
    px = _pose_norm_xy(raw, frame_i, side, "WRIST", "X")
    py = _pose_norm_xy(raw, frame_i, side, "WRIST", "Y")
    if not (np.isfinite(px) and np.isfinite(py) and np.isfinite(wx) and np.isfinite(wy)):
        return float("inf")
    return float(np.hypot(wx - px, wy - py))


def _score_hand_candidate(
    result,
    hand_idx: int,
    raw: pd.DataFrame,
    frame_i: int,
    x0: int,
    y0: int,
    cw: int,
    ch: int,
    fw: int,
    fh: int,
    prefer_side: Optional[str],
) -> Tuple[float, str, float, float]:
    hand_lms = result.hand_landmarks[hand_idx]
    wx, wy = _hl_wrist_norm(hand_lms, x0, y0, cw, ch, fw, fh)
    mp_side = _handedness_label(result, hand_idx)
    best_side = None
    best_dist = float("inf")
    for side in ("LEFT", "RIGHT"):
        d = _pose_wrist_dist(raw, frame_i, side, wx, wy)
        if d < best_dist:
            best_dist = d
            best_side = side
    score = 2.5 - best_dist * 12.0
    if prefer_side and best_side == prefer_side:
        score += 1.0
    if mp_side == best_side:
        score += 0.35
    if best_dist > 0.09:
        score -= 5.0
    elif best_dist > 0.06:
        score -= 2.0
    if best_dist > 0.14:
        score -= 3.0
    store_side = best_side or mp_side
    return score, store_side, wx, wy


def _write_hand_landmarks(
    raw: pd.DataFrame,
    frame_i: int,
    store_side: str,
    hand_lms,
    x0: int,
    y0: int,
    cw: int,
    ch: int,
    fw: int,
    fh: int,
) -> None:
    for name, idx in _HAND_LM.items():
        lm = hand_lms[idx]
        raw.at[frame_i, f"{store_side}_HL_{name}_X"] = float((x0 + lm.x * cw) / fw)
        raw.at[frame_i, f"{store_side}_HL_{name}_Y"] = float((y0 + lm.y * ch) / fh)
        raw.at[frame_i, f"{store_side}_HL_{name}_Z"] = float(lm.z)


def _detect_best_hand(
    landmarker,
    bgr: np.ndarray,
    ts_ms: int,
    raw: pd.DataFrame,
    frame_i: int,
    fw: int,
    fh: int,
    prefer_side: Optional[str],
) -> Tuple[Optional[str], str]:
    """One HL pass per frame; store the hand whose wrist is nearest pose."""
    detect_bgr = bgr
    x0, y0, cw, ch = 0, 0, fw, fh
    tag = "full"
    roi_side = prefer_side or _resolve_roi_side(raw, frame_i, prefer_side)
    if roi_side:
        wx = _pose_norm_xy(raw, frame_i, roi_side, "WRIST", "X")
        wy = _pose_norm_xy(raw, frame_i, roi_side, "WRIST", "Y")
        ix = _pose_norm_xy(raw, frame_i, roi_side, "INDEX", "X")
        iy = _pose_norm_xy(raw, frame_i, roi_side, "INDEX", "Y")
        tx = _pose_norm_xy(raw, frame_i, roi_side, "THUMB", "X")
        ty = _pose_norm_xy(raw, frame_i, roi_side, "THUMB", "Y")
        if np.isfinite(wx) and np.isfinite(ix) and np.isfinite(wy) and np.isfinite(iy):
            detect_bgr, x0, y0, cw, ch = _crop_hand_roi(
                bgr, wx, wy, ix, iy, fw, fh, tx=tx, ty=ty,
            )
            if cw < fw or ch < fh:
                tag = "roi"

    rgb = cv2.cvtColor(detect_bgr, cv2.COLOR_BGR2RGB)
    result = landmarker.detect_for_video(
        mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
        timestamp_ms=int(ts_ms),
    )
    if not result.hand_landmarks:
        return None, tag

    best_score = -1e9
    best_side: Optional[str] = None
    best_lms = None
    best_dist = float("inf")
    for hi in range(len(result.hand_landmarks)):
        score, store_side, _wx, _wy = _score_hand_candidate(
            result, hi, raw, frame_i, x0, y0, cw, ch, fw, fh, roi_side,
        )
        cand_dist = min(
            _pose_wrist_dist(raw, frame_i, s, _wx, _wy) for s in ("LEFT", "RIGHT")
        )
        if score > best_score:
            best_score = score
            best_side = store_side
            best_dist = cand_dist
            best_lms = result.hand_landmarks[hi]

    if best_lms is None or best_side is None or best_score < -1.0 or best_dist > 0.11:
        return None, tag

    _write_hand_landmarks(raw, frame_i, best_side, best_lms, x0, y0, cw, ch, fw, fh)
    return best_side, tag


def resolve_hand_model_path(model_path: Optional[str] = None, auto_download: bool = True) -> Optional[Path]:
    if model_path:
        p = Path(model_path)
        if p.exists():
            return p
    candidates = [
        Path(__file__).resolve().parent.parent / "backend" / "models" / "hand_landmarker.task",
        Path(__file__).resolve().parent / "models" / "hand_landmarker.task",
        Path("/home/user/models/hand_landmarker.task"),
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 1000:
            return p
    if auto_download:
        dest = candidates[0]
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            import urllib.request

            urllib.request.urlretrieve(HAND_MODEL_URL, dest)
            if dest.exists() and dest.stat().st_size > 1000:
                return dest
        except Exception:
            pass
    return None


def merge_hand_landmarks_into_raw_csv(
    video_path: str,
    raw_csv_path: str,
    *,
    model_path: Optional[str] = None,
    affected_side: Optional[str] = None,
    show_progress: bool = False,
) -> Dict[str, Any]:
    """
    Run Hand Landmarker on video and append HL_* columns aligned by frame index.
    Returns report dict; does not raise if model missing.
    """
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    mp_path = resolve_hand_model_path(model_path)
    if mp_path is None:
        return {"hand_landmarker": "skipped", "reason": "model_not_found"}

    raw = pd.read_csv(raw_csv_path)
    if "frame" not in raw.columns:
        raw["frame"] = np.arange(len(raw))

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {"hand_landmarker": "skipped", "reason": "video_open_failed"}
    try:
        cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 0)
    except Exception:
        pass

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    stream_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
    stream_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080
    # Must match extract_pose_csv_robust.rotate_cw — pose and HL share the same image space.
    rotate_cw = stream_w > stream_h * 1.15
    fw = stream_h if rotate_cw else stream_w
    fh = stream_w if rotate_cw else stream_h

    base_options = python.BaseOptions(model_asset_path=str(mp_path))
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.30,
        min_hand_presence_confidence=0.30,
        min_tracking_confidence=0.35,
    )
    landmarker = vision.HandLandmarker.create_from_options(options)

    n_frames = len(raw)
    sides = ("LEFT", "RIGHT")
    for side in sides:
        for name in _HAND_LM:
            for ax in ("X", "Y", "Z"):
                col = f"{side}_HL_{name}_{ax}"
                if col not in raw.columns:
                    raw[col] = np.nan

    frame_i = 0
    ts_ms = 0
    detected = 0
    roi_hits = 0
    rejected_far = 0
    prefer_side = str(affected_side).upper() if affected_side and str(affected_side).lower() != "auto" else None
    while frame_i < n_frames:
        ok, bgr = cap.read()
        if not ok:
            break
        if rotate_cw:
            bgr = cv2.rotate(bgr, cv2.ROTATE_90_CLOCKWISE)

        store_side, tag = _detect_best_hand(
            landmarker, bgr, ts_ms, raw, frame_i, fw, fh, prefer_side,
        )
        ts_ms += int(round(1000.0 / max(fps, 1.0)))

        if store_side:
            detected += 1
            if tag == "roi":
                roi_hits += 1
        else:
            rejected_far += 1

        frame_i += 1
        if show_progress and frame_i % 60 == 0:
            print(f"  hand landmarker: {frame_i}/{n_frames}", flush=True)

    cap.release()
    landmarker.close()
    raw.to_csv(raw_csv_path, index=False)

    return {
        "hand_landmarker": "ok",
        "hand_model": str(mp_path),
        "pose_rotation_applied": rotate_cw,
        "hand_roi_frames": roi_hits,
        "hand_frames_rejected_far": rejected_far,
        "hand_frames_with_detection": detected,
        "hand_landmarker_columns": [
            f"{s}_HL_{n}_{a}" for s in sides for n in _HAND_LM for a in ("X", "Y", "Z")
        ],
    }
