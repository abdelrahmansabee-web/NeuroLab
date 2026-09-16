"""
Overlay coordinate diagnostic — finds the correct landmark→video transform.

Scores candidate transforms on anatomical plausibility (nose above shoulders,
level shoulders, hips below torso) and can render a side-by-side debug JPEG.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd

SKELETON_PROBE_KEYS = (
    ("nose", "NOSE"),
    ("lshoulder", "LEFT_SHOULDER"),
    ("rshoulder", "RIGHT_SHOULDER"),
    ("lelbow", "LEFT_ELBOW"),
    ("relbow", "RIGHT_ELBOW"),
    ("lwrist", "LEFT_WRIST"),
    ("rwrist", "RIGHT_WRIST"),
    ("lhip", "LEFT_HIP"),
    ("rhip", "RIGHT_HIP"),
)

TRANSFORM_LABELS = {
    "none": "No transform (landmarks already match served video)",
    "portrait_to_landscape": "Portrait analysis → landscape video (inverse rotate_cw)",
    "landscape_to_portrait": "Landscape → portrait (forward rotate_cw)",
}


def portrait_norm_to_landscape_norm(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return y.copy(), 1.0 - x


def landscape_norm_to_portrait_norm(x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    return 1.0 - y, x.copy()


def apply_transform_norm(
    x: np.ndarray,
    y: np.ndarray,
    transform: str,
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
    if transform == "portrait_to_landscape":
        return portrait_norm_to_landscape_norm(x, y)
    if transform == "landscape_to_portrait":
        return landscape_norm_to_portrait_norm(x, y)
    return x, y


def norm_series(df: pd.DataFrame, name: str, coord: str) -> pd.Series:
    c_upper = coord.upper()
    c_lower = coord.lower()
    for c in (f"{name}_img{c_upper}", f"{name}_img{c_lower}"):
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    for c in (f"{name}_{coord}", f"{name}_{c_upper}", f"{name.lower()}_{c_lower}"):
        if c in df.columns:
            return pd.to_numeric(df[c], errors="coerce")
    return pd.Series(np.nan, index=df.index)


def probe_landmarks_frame(raw_df: pd.DataFrame, frame_idx: int) -> Dict[str, Tuple[float, float]]:
    if frame_idx < 0 or frame_idx >= len(raw_df):
        frame_idx = len(raw_df) // 2
    out: Dict[str, Tuple[float, float]] = {}
    for key, lm in SKELETON_PROBE_KEYS:
        x = float(norm_series(raw_df, lm, "x").iloc[frame_idx])
        y = float(norm_series(raw_df, lm, "y").iloc[frame_idx])
        if np.isfinite(x) and np.isfinite(y):
            out[key] = (x, y)
    return out


def score_pose_layout(points: Dict[str, Tuple[float, float]]) -> float:
    """Higher score = landmarks look like a seated reach in normalized video space."""

    def pt(k: str):
        p = points.get(k)
        if not p:
            return None
        x, y = p
        if not (np.isfinite(x) and np.isfinite(y)):
            return None
        if x < -0.05 or x > 1.05 or y < -0.05 or y > 1.05:
            return None
        return (float(x), float(y))

    nose = pt("nose")
    ls = pt("lshoulder")
    rs = pt("rshoulder")
    lh = pt("lhip")
    rh = pt("rhip")
    score = 0.0
    if nose and ls and rs:
        sy = (ls[1] + rs[1]) / 2.0
        if nose[1] < sy - 0.015:
            score += 3.0
        elif nose[1] < sy:
            score += 1.0
        shoulder_w = abs(ls[0] - rs[0])
        shoulder_tilt = abs(ls[1] - rs[1])
        if shoulder_w > 0.08:
            score += min(2.5, shoulder_w * 5.0)
        if shoulder_tilt < 0.08:
            score += 2.0
        elif shoulder_tilt < 0.14:
            score += 1.0
    if ls and rs and lh and rh:
        if lh[1] > ls[1] + 0.02 and rh[1] > rs[1] + 0.02:
            score += 2.0
    inside = sum(
        1 for p in points.values()
        if p and 0.02 <= p[0] <= 0.98 and 0.02 <= p[1] <= 0.98
    )
    score += min(2.0, inside * 0.25)
    return float(score)


def detect_overlay_coord_transform(
    raw_df: pd.DataFrame,
    *,
    orientation: int,
    raw_w: float,
    raw_h: float,
    served_w: float,
    served_h: float,
    analysis: Optional[Dict[str, Any]] = None,
    frame_idx: Optional[int] = None,
) -> Dict[str, Any]:
    """Return best transform name plus per-candidate scores."""
    if frame_idx is None:
        frame_idx = len(raw_df) // 2
    base = probe_landmarks_frame(raw_df, frame_idx)
    analysis_src_w = float((analysis or {}).get("frame_width_px") or 0)
    analysis_src_h = float((analysis or {}).get("frame_height_px") or 0)
    src_w = analysis_src_w if analysis_src_w > 0 else float(raw_h if raw_w > raw_h else raw_w)
    src_h = analysis_src_h if analysis_src_h > 0 else float(raw_w if raw_w > raw_h else raw_h)

    candidates = ["none", "portrait_to_landscape", "landscape_to_portrait"]
    scores: Dict[str, float] = {}
    transformed: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for name in candidates:
        pts: Dict[str, Tuple[float, float]] = {}
        for key, (x, y) in base.items():
            x2, y2 = apply_transform_norm(
                np.array([x]), np.array([y]), name, src_w=src_w, src_h=src_h,
            )
            pts[key] = (float(x2[0]), float(y2[0]))
        transformed[name] = pts
        scores[name] = score_pose_layout(pts)

    has_img = any(c.endswith("_imgX") for c in raw_df.columns)
    if has_img and scores.get("none", 0) >= scores.get("portrait_to_landscape", 0) - 0.5:
        # imgX/imgY are usually already in served-video space — prefer none when close.
        scores["none"] = scores.get("none", 0) + 0.75

    best = max(candidates, key=lambda k: scores.get(k, -1e9))
    return {
        "best_transform": best,
        "scores": scores,
        "probe_frame_idx": int(frame_idx),
        "landmark_source": "imgXY" if has_img else "XY",
        "orientation_deg": int(orientation or 0),
        "raw_stream_px": [round(float(raw_w), 2), round(float(raw_h), 2)],
        "served_video_px": [round(float(served_w), 2), round(float(served_h), 2)],
        "analysis_frame_px": [round(analysis_src_w, 2), round(analysis_src_h, 2)] if analysis_src_w else None,
        "probe_landmarks_raw": {k: list(v) for k, v in base.items()},
        "probe_landmarks_by_transform": {
            k: {pk: list(pv) for pk, pv in v.items()} for k, v in transformed.items()
        },
        "transform_labels": TRANSFORM_LABELS,
        "recommended_action": (
            "Re-analyze after deploy so overlay JSON uses auto-detected transform."
            if best != "none"
            else "Landmarks already align with served video — no rotation remap needed."
        ),
    }


def _coord_column_pairs(df: pd.DataFrame, *, hl_only: bool = False) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for col in list(df.columns):
        if hl_only and "_HL_" not in col:
            continue
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
    return pairs


def apply_transform_df(
    df: pd.DataFrame,
    transform: str,
    src_w: float,
    src_h: float,
    *,
    hl_only: bool = False,
) -> pd.DataFrame:
    if transform == "none":
        return df
    df = df.copy()
    seen = set()
    for x_col, y_col in _coord_column_pairs(df, hl_only=hl_only):
        key = (x_col, y_col)
        if key in seen:
            continue
        seen.add(key)
        x = pd.to_numeric(df[x_col], errors="coerce").values.astype(float)
        y = pd.to_numeric(df[y_col], errors="coerce").values.astype(float)
        x2, y2 = apply_transform_norm(x, y, transform, src_w=src_w, src_h=src_h)
        df[x_col] = x2
        df[y_col] = y2
    return df


def apply_transform_df_hl_only(
    df: pd.DataFrame,
    transform: str,
    src_w: float,
    src_h: float,
) -> pd.DataFrame:
    return apply_transform_df(df, transform, src_w, src_h, hl_only=True)


def _hl_wrist_pose_dist(
    raw_df: pd.DataFrame,
    side: str,
    transform: str,
    *,
    src_w: float,
    src_h: float,
    frame_indices: Optional[List[int]] = None,
) -> float:
    side = side.upper()
    hl_x = norm_series(raw_df, f"{side}_HL_WRIST", "x").values
    hl_y = norm_series(raw_df, f"{side}_HL_WRIST", "y").values
    pose_x = norm_series(raw_df, f"{side}_WRIST", "x").values
    pose_y = norm_series(raw_df, f"{side}_WRIST", "y").values
    if frame_indices is None:
        frame_indices = list(range(0, len(raw_df), max(1, len(raw_df) // 24)))
    dists: List[float] = []
    for i in frame_indices:
        if i < 0 or i >= len(raw_df):
            continue
        px = float(pose_x[i]) if np.isfinite(pose_x[i]) else np.nan
        py = float(pose_y[i]) if np.isfinite(pose_y[i]) else np.nan
        hx = float(hl_x[i]) if np.isfinite(hl_x[i]) else np.nan
        hy = float(hl_y[i]) if np.isfinite(hl_y[i]) else np.nan
        if not (np.isfinite(px) and np.isfinite(py) and np.isfinite(hx) and np.isfinite(hy)):
            continue
        tx, ty = apply_transform_norm(
            np.array([hx]), np.array([hy]), transform, src_w=src_w, src_h=src_h,
        )
        dists.append(float(np.hypot(float(tx[0]) - px, float(ty[0]) - py)))
    if not dists:
        return 1e9
    return float(np.median(dists))


def detect_hl_coord_transform(
    raw_df: pd.DataFrame,
    *,
    side: str,
    body_transform: str,
    analysis_src_w: float,
    analysis_src_h: float,
    raw_w: float,
    raw_h: float,
    served_w: float,
    served_h: float,
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pick HL-only transform so HL wrist aligns with pose WRIST imgX (served video space)."""
    side = str(side or "RIGHT").upper()
    hl_col = f"{side}_HL_WRIST_X"
    if hl_col not in raw_df.columns and f"{side}_HL_WRIST_x" not in raw_df.columns:
        return {"best_transform": "none", "scores": {}, "reason": "no_hl_columns"}

    if body_transform != "none":
        return {
            "best_transform": body_transform,
            "scores": {body_transform: 0.0},
            "reason": "follows_body_transform",
        }

    src_w = analysis_src_w if analysis_src_w > 0 else float(raw_h if raw_w > raw_h else raw_w)
    src_h = analysis_src_h if analysis_src_h > 0 else float(raw_w if raw_w > raw_h else raw_h)
    candidates = ["none", "portrait_to_landscape", "landscape_to_portrait"]
    dists: Dict[str, float] = {}
    for name in candidates:
        dists[name] = _hl_wrist_pose_dist(raw_df, side, name, src_w=src_w, src_h=src_h)
    scores = {k: round(max(0.0, 1.0 - v * 8.0), 4) for k, v in dists.items()}

    portrait_analysis = (
        (analysis_src_h > analysis_src_w * 1.08 if analysis_src_w > 0 else False)
        or bool((analysis or {}).get("orientation_corrected"))
    )
    landscape_served = served_w > served_h * 1.08
    if portrait_analysis and landscape_served:
        if dists.get("portrait_to_landscape", 1e9) <= dists.get("none", 1e9) * 1.08:
            scores["portrait_to_landscape"] = scores.get("portrait_to_landscape", 0) + 0.25

    best = min(candidates, key=lambda k: dists.get(k, 1e9))
    return {
        "best_transform": best,
        "scores": scores,
        "side": side,
        "wrist_dist_none": round(dists.get("none", 0.0), 5),
        "wrist_dist_portrait_to_landscape": round(dists.get("portrait_to_landscape", 0.0), 5),
        "wrist_dist_landscape_to_portrait": round(dists.get("landscape_to_portrait", 0.0), 5),
        "reason": "hl_wrist_vs_pose_wrist",
    }


def render_diag_image(
    video_path: Path,
    raw_df: pd.DataFrame,
    diag: Dict[str, Any],
    out_path: Path,
    frame_idx: Optional[int] = None,
) -> Optional[str]:
    if not video_path.exists():
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    idx = int(frame_idx if frame_idx is not None else diag.get("probe_frame_idx", 0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None

    h, w = frame.shape[:2]
    panels = ["none", "portrait_to_landscape", "landscape_to_portrait"]
    best = diag.get("best_transform", "none")
    colors = {
        "none": (80, 200, 255),
        "portrait_to_landscape": (80, 255, 120),
        "landscape_to_portrait": (120, 120, 255),
    }
    tile_w = min(480, w)
    tile_h = int(tile_w * h / max(w, 1))
    row_h = tile_h + 36
    canvas = np.zeros((row_h, tile_w * 3, 3), dtype=np.uint8)
    by_tf = diag.get("probe_landmarks_by_transform") or {}
    scores = diag.get("scores") or {}
    for i, tf in enumerate(panels):
        tile = cv2.resize(frame, (tile_w, tile_h))
        pts = by_tf.get(tf) or {}
        for key, (nx, ny) in pts.items():
            if not (np.isfinite(nx) and np.isfinite(ny)):
                continue
            px = int(np.clip(nx, 0, 1) * (tile_w - 1))
            py = int(np.clip(ny, 0, 1) * (tile_h - 1))
            cv2.circle(tile, (px, py), 5, colors.get(tf, (255, 255, 255)), -1)
            if key == "nose":
                cv2.putText(tile, "N", (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        label = f"{tf}  score={scores.get(tf, 0):.1f}"
        if tf == best:
            label += "  BEST"
        cv2.rectangle(tile, (0, 0), (tile_w - 1, 22), (0, 0, 0), -1)
        cv2.putText(tile, label[:42], (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        x0 = i * tile_w
        canvas[36 : 36 + tile_h, x0 : x0 + tile_w] = tile
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)
    return str(out_path)


def run_overlay_coord_diagnostic(
    csv_path: str,
    video_path: Optional[str] = None,
    analysis: Optional[Dict[str, Any]] = None,
    out_dir: Optional[str] = None,
) -> Dict[str, Any]:
    from overlay_data import _rotate_xy, _video_orientation_and_dims, _served_video_dims
    from table_calibrator import find_video_for_csv

    csv_p = Path(csv_path)
    if not csv_p.exists():
        return {"error": f"CSV not found: {csv_path}"}

    raw_csv = csv_p.with_name(csv_p.name.replace(".csv", "_raw_pose.csv"))
    if not raw_csv.exists():
        raw_csv = csv_p
    raw_df = pd.read_csv(raw_csv)

    vid_p = Path(video_path) if video_path else find_video_for_csv(str(csv_p))
    if not vid_p or not Path(vid_p).exists():
        return {"error": "Video not found for diagnostic"}

    orientation, raw_w, raw_h = _video_orientation_and_dims(Path(vid_p))
    raw_df = _rotate_xy(raw_df, orientation, raw_w, raw_h)
    served_w, served_h = _served_video_dims(orientation, raw_w, raw_h)

    diag = detect_overlay_coord_transform(
        raw_df,
        orientation=orientation,
        raw_w=raw_w,
        raw_h=raw_h,
        served_w=served_w,
        served_h=served_h,
        analysis=analysis,
    )
    diag["csv"] = csv_p.name
    diag["video"] = Path(vid_p).name

    out_base = Path(out_dir) if out_dir else csv_p.parent
    img_path = out_base / f"{csv_p.stem}_overlay_coord_diag.jpg"
    rendered = render_diag_image(Path(vid_p), raw_df, diag, img_path)
    if rendered:
        diag["diag_image"] = rendered

    json_path = out_base / f"{csv_p.stem}_overlay_coord_diag.json"
    json_path.write_text(json.dumps(diag, indent=2), encoding="utf-8")
    diag["diag_json"] = str(json_path)
    return diag


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python overlay_coord_diag.py <csv_path> [video_path]")
        raise SystemExit(1)
    result = run_overlay_coord_diagnostic(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps({k: v for k, v in result.items() if k != "probe_landmarks_by_transform"}, indent=2))
