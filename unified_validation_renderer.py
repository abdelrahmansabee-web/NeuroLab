# -*- coding: utf-8 -*-
"""
Unified validation video renderer for NeuroLab.

Takes the original video, the analysis-ready landmarks CSV produced by
mediapipe_csv_extractor.py, and the analysis dict from
stroke_kinematic_pipeline.analyze_trial().

Outputs a side-by-side video: original footage on the left, live metrics
panel on the right.  Numbers displayed come from the same analysis dict that
is returned by /analyze, so the video and the kinematics table match.

Required columns in df (pixel coordinates):
  frame, time, palm_x, palm_y, wrist_x, wrist_y, shoulder_x, shoulder_y,
  elbow_x, elbow_y, trunk_x, trunk_y, shoulder_width
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from scipy.signal import find_peaks


_SKELETON_CACHE: Dict[str, Any] = {}
_UI_SCALE: float = 1.0


def _set_ui_scale(scale: float) -> None:
    global _UI_SCALE
    _UI_SCALE = float(scale)


def _s(v):
    """Scale an integer/float pixel value by the current UI scale."""
    if isinstance(v, float):
        return v * _UI_SCALE
    return int(v * _UI_SCALE)


def _smooth_series(arr: np.ndarray, window: int = 7) -> np.ndarray:
    """Temporal moving-average smoothing of a (N,2) or (N,) array."""
    if len(arr) < window or window < 2:
        return arr
    out = np.empty_like(arr, dtype=float)
    half = window // 2
    for i in range(len(arr)):
        a = max(0, i - half)
        b = min(len(arr), i + half + 1)
        out[i] = np.nanmean(arr[a:b], axis=0)
    return out


def _interpolate_nan(arr: np.ndarray) -> np.ndarray:
    """Forward/backward fill NaNs in a (N,2) array."""
    out = arr.copy()
    for d in range(out.shape[1]):
        s = out[:, d]
        valid = np.where(np.isfinite(s))[0]
        if len(valid) == 0:
            continue
        s[:valid[0]] = s[valid[0]]
        s[valid[-1] + 1:] = s[valid[-1]]
        for i in range(len(s)):
            if not np.isfinite(s[i]):
                prev = valid[valid < i]
                nxt = valid[valid > i]
                if len(prev) and len(nxt):
                    s[i] = (s[prev[-1]] + s[nxt[0]]) / 2
                elif len(prev):
                    s[i] = s[prev[-1]]
                elif len(nxt):
                    s[i] = s[nxt[0]]
    return out


def _draw_cylinder_bone(
    canvas: np.ndarray,
    a: Tuple[int, int],
    b: Tuple[int, int],
    width: int,
    base_color: Tuple[int, int, int],
    active: bool = False,
) -> None:
    """Draw a realistic cylindrical bone segment with rounded epiphyses."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    # Active arm gets a bright outline; inactive is subtle
    outline_color = (80, 200, 255) if active else (60, 55, 50)
    outline_w = 3 if active else 2

    # Draw shadow/outline line
    cv2.line(canvas, a, b, outline_color, width + outline_w + 2, cv2.LINE_AA)
    # Draw main bone
    cv2.line(canvas, a, b, base_color, width, cv2.LINE_AA)

    # Highlight center-top of the bone (cylindrical shine)
    hl_color = tuple(min(255, int(c * 1.25 + 25)) for c in base_color)
    cv2.line(canvas, a, b, hl_color, max(2, width // 3), cv2.LINE_AA)

    # Rounded ends (epiphyses)
    cap_r = width // 2
    # Dark side of cap
    cv2.circle(canvas, a, cap_r + outline_w // 2, outline_color, -1, cv2.LINE_AA)
    cv2.circle(canvas, b, cap_r + outline_w // 2, outline_color, -1, cv2.LINE_AA)
    # Bone-colored cap
    cv2.circle(canvas, a, cap_r, base_color, -1, cv2.LINE_AA)
    cv2.circle(canvas, b, cap_r, base_color, -1, cv2.LINE_AA)
    # Highlight on cap
    hl_off = max(1, cap_r // 4)
    cv2.circle(canvas, (a[0] - hl_off, a[1] - hl_off), max(1, cap_r // 3), hl_color, -1, cv2.LINE_AA)
    cv2.circle(canvas, (b[0] - hl_off, b[1] - hl_off), max(1, cap_r // 3), hl_color, -1, cv2.LINE_AA)


def _draw_joint_sphere(
    canvas: np.ndarray,
    pt: Tuple[int, int],
    radius: int,
    base_color: Tuple[int, int, int],
    active: bool = False,
) -> None:
    """Draw a realistic 3D joint sphere."""
    r = max(3, radius)
    # Outline
    outline_color = (80, 200, 255) if active else (60, 55, 50)
    cv2.circle(canvas, pt, r + 2, outline_color, -1, cv2.LINE_AA)
    # Sphere body
    cv2.circle(canvas, pt, r, base_color, -1, cv2.LINE_AA)
    # Shading gradient simulated by darker overlay circle offset
    shadow_pt = (pt[0] + r // 3, pt[1] + r // 3)
    cv2.circle(canvas, shadow_pt, r // 2, (0, 0, 0, 60), -1, cv2.LINE_AA)
    # Specular highlight
    hl_pt = (pt[0] - r // 3, pt[1] - r // 3)
    cv2.circle(canvas, hl_pt, max(2, r // 3), (255, 255, 255), -1, cv2.LINE_AA)


def _draw_hand_paddle(
    canvas: np.ndarray,
    wrist: Tuple[int, int],
    fingers: Tuple[int, int],
    width: int,
    base_color: Tuple[int, int, int],
) -> None:
    """Draw a simple stylised hand paddle from wrist toward fingers."""
    dx = fingers[0] - wrist[0]
    dy = fingers[1] - wrist[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    perp_x = -dy / length
    perp_y = dx / length
    w2 = max(4, width // 2)

    # Palm as a quadrilateral
    p1 = (int(wrist[0] + perp_x * w2), int(wrist[1] + perp_y * w2))
    p2 = (int(wrist[0] - perp_x * w2), int(wrist[1] - perp_y * w2))
    p3 = (int(fingers[0] - perp_x * w2 * 0.7), int(fingers[1] - perp_y * w2 * 0.7))
    p4 = (int(fingers[0] + perp_x * w2 * 0.7), int(fingers[1] + perp_y * w2 * 0.7))
    pts = np.array([p1, p2, p3, p4], np.int32)
    cv2.fillPoly(canvas, [pts], base_color, cv2.LINE_AA)
    cv2.polylines(canvas, [pts], True, (60, 55, 50), 2, cv2.LINE_AA)

    # Fingers as short lines
    for t in [0.35, 0.55, 0.75, 0.92]:
        base_x = wrist[0] + (fingers[0] - wrist[0]) * t + perp_x * w2 * 0.5
        base_y = wrist[1] + (fingers[1] - wrist[1]) * t + perp_y * w2 * 0.5
        tip_x = base_x + (fingers[0] - wrist[0]) * 0.25
        tip_y = base_y + (fingers[1] - wrist[1]) * 0.25
        cv2.line(canvas, (int(base_x), int(base_y)), (int(tip_x), int(tip_y)),
                 base_color, max(2, width // 4), cv2.LINE_AA)
        cv2.circle(canvas, (int(tip_x), int(tip_y)), max(2, width // 5), base_color, -1, cv2.LINE_AA)


def _draw_torso(
    canvas: np.ndarray,
    neck: Tuple[int, int],
    pelvis: Tuple[int, int],
    shoulder_width: float,
    base_color: Tuple[int, int, int],
) -> None:
    """Draw a simplified ribcage + spine."""
    dx = pelvis[0] - neck[0]
    dy = pelvis[1] - neck[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    spine_w = max(4, int(shoulder_width / 14))
    _draw_cylinder_bone(canvas, neck, pelvis, spine_w, base_color, active=False)

    # Ribs
    rib_w = int(shoulder_width * 0.35)
    rib_h = max(3, int(shoulder_width / 22))
    n_ribs = 5
    for i in range(1, n_ribs + 1):
        t = i / (n_ribs + 1)
        cx = int(neck[0] + dx * t)
        cy = int(neck[1] + dy * t)
        cv2.ellipse(canvas, (cx, cy), (rib_w, rib_h), 0, 0, 360, (60, 55, 50), 2, cv2.LINE_AA)
        cv2.ellipse(canvas, (cx, cy), (rib_w - 2, rib_h - 1), 0, 0, 360, base_color, -1, cv2.LINE_AA)


def _draw_skull(
    canvas: np.ndarray,
    nose: Tuple[int, int],
    radius: int,
    base_color: Tuple[int, int, int],
) -> None:
    """Draw a simple realistic skull at nose position."""
    r = max(6, radius)
    center = (nose[0], nose[1] - r // 2)
    # Cranium
    cv2.ellipse(canvas, center, (r, int(r * 1.15)), 0, 0, 360, (60, 55, 50), 2, cv2.LINE_AA)
    cv2.ellipse(canvas, center, (r, int(r * 1.15)), 0, 0, 360, base_color, -1, cv2.LINE_AA)
    # Jaw
    jaw_y = center[1] + r // 2
    jaw_pts = np.array([
        [center[0] - r // 2, jaw_y],
        [center[0] + r // 2, jaw_y],
        [center[0] + r // 3, jaw_y + r // 2],
        [center[0] - r // 3, jaw_y + r // 2],
    ], np.int32)
    cv2.fillPoly(canvas, [jaw_pts], base_color, cv2.LINE_AA)
    cv2.polylines(canvas, [jaw_pts], True, (60, 55, 50), 1, cv2.LINE_AA)
    # Highlight
    cv2.ellipse(canvas, (center[0] - r // 4, center[1] - r // 4),
                (r // 3, r // 4), 0, 0, 360, (255, 255, 255), -1, cv2.LINE_AA)


def _draw_clavicle(
    canvas: np.ndarray,
    a: Tuple[int, int],
    b: Tuple[int, int],
    width: int,
    base_color: Tuple[int, int, int],
) -> None:
    """Draw a gently S-curved clavicle."""
    mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
    bulge = max(3, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 14))
    mid = (mid[0], mid[1] + bulge)
    pts = np.array([a, mid, b], np.int32).reshape((-1, 1, 2))
    cv2.polylines(canvas, [pts], False, (60, 55, 50), width + 3, cv2.LINE_AA)
    cv2.polylines(canvas, [pts], False, base_color, width, cv2.LINE_AA)
    # Highlight
    cv2.polylines(canvas, [pts], False, (255, 255, 255), max(1, width // 4), cv2.LINE_AA)
    cv2.circle(canvas, a, width // 2, base_color, -1, cv2.LINE_AA)
    cv2.circle(canvas, b, width // 2, base_color, -1, cv2.LINE_AA)


def _find_ffmpeg() -> Optional[str]:
    """Return a usable ffmpeg executable (system or imageio-ffmpeg bundle)."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
        if Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def _safe_series(df: pd.DataFrame, col: str) -> np.ndarray:
    if col in df.columns:
        return df[col].astype(float).values
    return np.full(len(df), np.nan)


def _normalize_landmark_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map legacy lowercase _x/_y landmark columns to pipeline _X/_Y names."""
    rename = {}
    for c in df.columns:
        if c.endswith("_x"):
            rename[c] = c[:-2] + "_X"
        elif c.endswith("_y"):
            rename[c] = c[:-2] + "_Y"
        elif c.endswith("_z"):
            rename[c] = c[:-2] + "_Z"
        elif c.endswith("_v") and "_VISIBILITY" not in c.upper():
            rename[c] = c[:-2] + "_VISIBILITY"
    return df.rename(columns=rename) if rename else df


def _infer_rotation_from_landmarks(df: pd.DataFrame, frame_w: int, frame_h: int) -> int:
    """
    Infer how much the video must be rotated so the person is upright.
    Uses shoulder/trunk/hip positions when metadata is missing.
    Returns 0/90/180/270 (clockwise degrees, matching cv2.rotate).
    """
    # Prefer raw nose/shoulder/hip columns when available
    has_raw = "LEFT_SHOULDER_X" in df.columns or "left_shoulder_x" in df.columns
    if has_raw:
        norm = _normalize_landmark_columns(df)
        lsx = _safe_series(norm, "LEFT_SHOULDER_X")
        rsx = _safe_series(norm, "RIGHT_SHOULDER_X")
        lsy = _safe_series(norm, "LEFT_SHOULDER_Y")
        rsy = _safe_series(norm, "RIGHT_SHOULDER_Y")
        lhx = _safe_series(norm, "LEFT_HIP_X")
        rhx = _safe_series(norm, "RIGHT_HIP_X")
        lhy = _safe_series(norm, "LEFT_HIP_Y")
        rhy = _safe_series(norm, "RIGHT_HIP_Y")
        sx = float(np.nanmedian((lsx + rsx) / 2))
        sy = float(np.nanmedian((lsy + rsy) / 2))
        hx = float(np.nanmedian((lhx + rhx) / 2))
        hy = float(np.nanmedian((lhy + rhy) / 2))
    else:
        # Cleaned CSV: shoulder_x/y and trunk_x/y (trunk is between shoulders and hips)
        if "shoulder_x" not in df.columns or "trunk_x" not in df.columns:
            return 0
        sx = float(np.nanmedian(df["shoulder_x"].astype(float).values))
        sy = float(np.nanmedian(df["shoulder_y"].astype(float).values))
        hx = float(np.nanmedian(df["trunk_x"].astype(float).values))
        hy = float(np.nanmedian(df["trunk_y"].astype(float).values))

    if not (np.isfinite(sx) and np.isfinite(sy) and np.isfinite(hx) and np.isfinite(hy)):
        return 0

    dx = hx - sx
    dy = hy - sy

    # Person is roughly horizontal in frame -> rotate to make vertical.
    # The stored video is landscape.  We need to rotate the *frame* so the
    # person stands upright.  cv2.ROTATE_90_CLOCKWISE means the frame is turned
    # 90 degrees clockwise, which makes a person lying on their left side stand
    # up.  cv2.ROTATE_90_COUNTERCLOCKWISE does the opposite.
    if abs(dx) > abs(dy):
        if dx > 0:      # hips to the right of shoulders -> person on right side -> CW rotation stands them up
            return 90   # cv2.ROTATE_90_CLOCKWISE
        else:           # hips to the left -> person on left side -> CCW rotation stands them up
            return 270  # cv2.ROTATE_90_COUNTERCLOCKWISE

    # Person is roughly vertical. If head/shoulders are below hips, flip 180.
    if dy > 0:
        return 180

    return 0


def _find_ffmpeg() -> Optional[str]:
    """Return a usable ffmpeg executable (system or imageio-ffmpeg bundle)."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        exe = get_ffmpeg_exe()
        if Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def _get_video_rotation(video_path: Path) -> int:
    """Read rotation metadata from video file (ffmpeg or OpenCV fallback)."""
    # Prefer OpenCV's metadata tag when available; avoids ffmpeg probe cost.
    try:
        cap = cv2.VideoCapture(str(video_path))
        tag = cap.get(cv2.CAP_PROP_ORIENTATION_META)
        cap.release()
        if tag and tag > 0:
            return int(tag) % 360
    except Exception:
        pass

    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return 0
    try:
        cmd = [ffmpeg, "-i", str(video_path), "-f", "null", "-"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        output = result.stdout + result.stderr

        # iPhone/Android often stores rotation as a metadata tag
        import re
        m = re.search(r'rotate\s*[:=]\s*(\-?\d+(?:\.\d+)?)', output, re.IGNORECASE)
        if m:
            return int(float(m.group(1))) % 360

        # QuickTime displaymatrix side data
        m = re.search(r'displaymatrix:\s*rotation\s*(-?\d+(?:\.\d+)?)', output)
        if m:
            return int(float(m.group(1))) % 360

        # Stream #0:0(und): Video: h264 (avc1 / 0x31637661), none, 1920x1080, ... rotation 90 deg
        m = re.search(r'rotation\s+(-?\d+(?:\.\d+)?)\s*deg', output)
        if m:
            return int(float(m.group(1))) % 360
    except Exception as exc:
        print(f"Could not read video rotation metadata: {exc}")
    return 0


def _rotate_landmark_columns(df: pd.DataFrame, angle: int, orig_w: int, orig_h: int) -> pd.DataFrame:
    """Rotate pixel landmark columns to match frame rotation."""
    if angle == 0:
        return df
    pairs = [("palm_x", "palm_y"), ("wrist_x", "wrist_y"),
             ("shoulder_x", "shoulder_y"), ("elbow_x", "elbow_y"),
             ("trunk_x", "trunk_y")]
    df = df.copy()
    for cx, cy in pairs:
        if cx not in df.columns or cy not in df.columns:
            continue
        x = df[cx].astype(float).values
        y = df[cy].astype(float).values
        # These formulas match cv2.rotate() semantics:
        #   90  = ROTATE_90_CLOCKWISE
        #   180 = ROTATE_180
        #   270 = ROTATE_90_COUNTERCLOCKWISE
        if angle == 90:
            nx, ny = orig_h - 1 - y, x
        elif angle == 180:
            nx, ny = orig_w - 1 - x, orig_h - 1 - y
        elif angle == 270:
            nx, ny = y, orig_w - 1 - x
        else:
            nx, ny = x, y
        df[cx] = nx
        df[cy] = ny
    return df


def _rotate_raw_landmarks(df: pd.DataFrame, angle: int, orig_w: int, orig_h: int) -> pd.DataFrame:
    """Rotate all MediaPipe _X/_Y columns to match frame rotation."""
    if angle == 0:
        return df
    df = df.copy()
    for c in df.columns:
        if c.endswith("_X"):
            base = c[:-2]
            ycol = base + "_Y"
            if ycol not in df.columns:
                continue
            x = df[c].astype(float).values * orig_w
            y = df[ycol].astype(float).values * orig_h
            if angle == 90:
                nx, ny = orig_h - 1 - y, x
            elif angle == 180:
                nx, ny = orig_w - 1 - x, orig_h - 1 - y
            elif angle == 270:
                nx, ny = y, orig_w - 1 - x
            else:
                nx, ny = x, y
            df[c] = nx / (orig_h if angle in (90, 270) else orig_w)
            df[ycol] = ny / (orig_w if angle in (90, 270) else orig_h)
    return df


def _draw_bone_segment(
    canvas: np.ndarray,
    a: Tuple[int, int],
    b: Tuple[int, int],
    width: int,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a shaded bone shaft with rounded caps; clipped to video region."""
    if clip_x is not None and a[0] >= clip_x and b[0] >= clip_x:
        return
    if a == b:
        return

    width = max(4, int(width))
    shadow = (25, 25, 25)
    highlight = tuple(min(255, int(c * 1.18 + 20)) for c in color)

    cv2.line(canvas, a, b, shadow, width + 4, cv2.LINE_AA)
    cv2.line(canvas, a, b, color, width, cv2.LINE_AA)
    cv2.line(canvas, a, b, highlight, max(2, width // 4), cv2.LINE_AA)

    cap_r = width // 2
    cv2.circle(canvas, a, cap_r, color, -1, cv2.LINE_AA)
    cv2.circle(canvas, b, cap_r, color, -1, cv2.LINE_AA)



def _draw_joint_sphere(
    canvas: np.ndarray,
    pt: Tuple[int, int],
    radius: int,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a 3-D-looking joint sphere; clipped to video region."""
    if clip_x is not None and pt[0] >= clip_x:
        return
    radius = max(3, int(radius))

    cv2.circle(canvas, pt, radius + 2, (20, 20, 20), -1, cv2.LINE_AA)
    cv2.circle(canvas, pt, radius, color, -1, cv2.LINE_AA)
    # specular highlight up-left
    hl_off = max(1, radius // 3)
    hl_pt = (pt[0] - hl_off, pt[1] - hl_off)
    cv2.circle(canvas, hl_pt, max(1, radius // 3), (255, 255, 255), -1, cv2.LINE_AA)



def _draw_skull(
    canvas: np.ndarray,
    pt: Tuple[int, int],
    scale: float,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a simple shaded skull at the nose position."""
    if clip_x is not None and pt[0] >= clip_x:
        return
    w = max(6, int(26 * scale))
    h = max(8, int(32 * scale))
    center = (pt[0], pt[1] - h // 4)
    shadow = (20, 20, 20)
    highlight = tuple(min(255, int(c * 1.15 + 15)) for c in color)

    # cranium
    cv2.ellipse(canvas, center, (w, h), 0, 0, 360, shadow, 3, cv2.LINE_AA)
    cv2.ellipse(canvas, center, (w, h), 0, 0, 360, color, -1, cv2.LINE_AA)
    cv2.ellipse(canvas, (center[0] - w // 4, center[1] - h // 4), (w // 4, h // 5), 0, 0, 360, highlight, -1, cv2.LINE_AA)
    # jaw
    jaw_y = center[1] + h // 2
    jaw_pts = np.array([
        [center[0] - w // 2, jaw_y],
        [center[0] + w // 2, jaw_y],
        [center[0] + w // 4, jaw_y + h // 3],
        [center[0] - w // 4, jaw_y + h // 3],
    ], np.int32)
    cv2.fillPoly(canvas, [jaw_pts], color, cv2.LINE_AA)
    cv2.polylines(canvas, [jaw_pts], True, shadow, 1, cv2.LINE_AA)



def _draw_hand_paddle(
    canvas: np.ndarray,
    wrist: Tuple[int, int],
    idx: Tuple[int, int],
    pinky: Optional[Tuple[int, int]],
    scale: float,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a simplified hand paddle from wrist toward fingers."""
    if clip_x is not None and wrist[0] >= clip_x:
        return

    dx = idx[0] - wrist[0]
    dy = idx[1] - wrist[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    if pinky is not None:
        # palm center between index and pinky
        palm_end = (int((idx[0] + pinky[0]) / 2), int((idx[1] + pinky[1]) / 2))
    else:
        palm_end = idx

    perp_x = -dy / length
    perp_y = dx / length
    w = max(6, int(14 * scale))

    p1 = (int(wrist[0] + perp_x * w), int(wrist[1] + perp_y * w))
    p2 = (int(wrist[0] - perp_x * w), int(wrist[1] - perp_y * w))
    p3 = (int(palm_end[0] - perp_x * w * 0.8), int(palm_end[1] - perp_y * w * 0.8))
    p4 = (int(palm_end[0] + perp_x * w * 0.8), int(palm_end[1] + perp_y * w * 0.8))

    pts = np.array([p1, p2, p3, p4], np.int32)
    cv2.fillPoly(canvas, [pts], color, cv2.LINE_AA)
    cv2.polylines(canvas, [pts], True, (30, 30, 30), 2, cv2.LINE_AA)

    # fingers as short lines
    n_fingers = 4
    for i in range(1, n_fingers + 1):
        t = i / (n_fingers + 1)
        base_x = wrist[0] + (palm_end[0] - wrist[0]) * t + perp_x * w * 0.6
        base_y = wrist[1] + (palm_end[1] - wrist[1]) * t + perp_y * w * 0.6
        tip_x = base_x + (palm_end[0] - wrist[0]) * 0.35
        tip_y = base_y + (palm_end[1] - wrist[1]) * 0.35
        cv2.line(canvas, (int(base_x), int(base_y)), (int(tip_x), int(tip_y)), color, max(2, int(3 * scale)), cv2.LINE_AA)



def _draw_ribcage(
    canvas: np.ndarray,
    neck: Tuple[int, int],
    pelvis: Tuple[int, int],
    shoulder_width: float,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a simplified ribcage + spine from neck to pelvis."""
    if clip_x is not None and neck[0] >= clip_x and pelvis[0] >= clip_x:
        return

    dx = pelvis[0] - neck[0]
    dy = pelvis[1] - neck[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return

    # spine
    _draw_bone_segment(canvas, neck, pelvis, max(6, int(shoulder_width / 10)), color, clip_x=clip_x)

    # ribs as horizontal ellipses along the spine
    n_ribs = 5
    rib_w = int(shoulder_width * 0.35)
    rib_h = max(3, int(shoulder_width / 18))
    for i in range(1, n_ribs + 1):
        t = i / (n_ribs + 1)
        cx = int(neck[0] + dx * t)
        cy = int(neck[1] + dy * t)
        if clip_x is not None and cx >= clip_x:
            continue
        cv2.ellipse(canvas, (cx, cy), (rib_w, rib_h), 0, 0, 360, (30, 30, 30), 2, cv2.LINE_AA)
        cv2.ellipse(canvas, (cx, cy), (rib_w - 2, rib_h - 1), 0, 0, 360, color, -1, cv2.LINE_AA)



def _draw_clavicle(
    canvas: np.ndarray,
    a: Tuple[int, int],
    b: Tuple[int, int],
    width: int,
    color: Tuple[int, int, int],
    clip_x: Optional[int] = None,
) -> None:
    """Draw a gently curved clavicle between two points."""
    if clip_x is not None and a[0] >= clip_x and b[0] >= clip_x:
        return
    mid = ((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)
    # slight downward bulge
    bulge = max(4, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 12))
    mid = (mid[0], mid[1] + bulge)
    pts = np.array([a, mid, b], np.int32).reshape((-1, 1, 2))
    cv2.polylines(canvas, [pts], False, (25, 25, 25), width + 3, cv2.LINE_AA)
    cv2.polylines(canvas, [pts], False, color, width, cv2.LINE_AA)
    cv2.circle(canvas, a, width // 2, color, -1, cv2.LINE_AA)
    cv2.circle(canvas, b, width // 2, color, -1, cv2.LINE_AA)



def _smooth_positions(positions: np.ndarray, window: int = 3) -> np.ndarray:
    """Light moving-average smoothing for landmark positions."""
    if len(positions) < window or window <= 1:
        return positions
    out = np.empty_like(positions, dtype=float)
    half = window // 2
    for i in range(len(positions)):
        a = max(0, i - half)
        b = min(len(positions), i + half + 1)
        out[i] = np.nanmean(positions[a:b], axis=0)
    return out



def _draw_mediapipe_skeleton(
    canvas: np.ndarray,
    raw_df: pd.DataFrame,
    row_idx: int,
    frame_w: int,
    frame_h: int,
    active_side: str = "right",
    trunk_xy: Optional[np.ndarray] = None,
) -> None:
    """Draw a clean, accurate skeleton overlay with temporal smoothing to remove jitter."""

    if row_idx >= len(raw_df):
        return
    n_rows = len(raw_df)

    # Stronger temporal smoothing (Savgol) per DataFrame to reduce jitter.
    cache_key = (id(raw_df), frame_w, frame_h)
    smooth_cache = getattr(_draw_mediapipe_skeleton, "_smooth_cache", None)
    if smooth_cache is None or smooth_cache.get("key") != cache_key:
        names = ["NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
                 "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
                 "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE"]
        # Infer sampling rate
        fs = 60.0
        if "time" in raw_df.columns:
            t = raw_df["time"].astype(float).values
            if len(t) > 1:
                dt = np.median(np.diff(t))
                if dt > 0:
                    fs = float(1.0 / dt)
        smooth = {}
        for n in names:
            xs, ys = f"{n}_X", f"{n}_Y"
            if xs in raw_df.columns and ys in raw_df.columns:
                x = raw_df[xs].astype(float).values * frame_w
                y = raw_df[ys].astype(float).values * frame_h
                try:
                    from scipy.ndimage import median_filter
                    x_m = median_filter(np.nan_to_num(x, nan=np.nanmedian(x)), size=3)
                    y_m = median_filter(np.nan_to_num(y, nan=np.nanmedian(y)), size=3)
                    from motion_invariants import smooth_series
                    x_s = smooth_series(x_m, fs, window_s=0.40)
                    y_s = smooth_series(y_m, fs, window_s=0.40)
                except Exception:
                    xy_s = _smooth_positions(np.column_stack([x, y]), window=15)
                    x_s, y_s = xy_s[:, 0], xy_s[:, 1]
                smooth[n] = np.column_stack([x_s, y_s])

        # Hip fallback: MediaPipe often places hips on the table/occluded area. The trunk
        # in the cleaned CSV is the shoulder-girdle midpoint, so estimate hips from the
        # shoulder/knee relationship for seated poses.
        if trunk_xy is not None and "LEFT_SHOULDER" in smooth and "RIGHT_SHOULDER" in smooth:
            ls_smooth = smooth["LEFT_SHOULDER"]
            rs_smooth = smooth["RIGHT_SHOULDER"]
            lk_smooth = smooth.get("LEFT_KNEE")
            rk_smooth = smooth.get("RIGHT_KNEE")
            shoulder_center = (ls_smooth + rs_smooth) / 2.0

            def _hip_estimate(s_arr, k_arr, center):
                if k_arr is None:
                    return s_arr.copy()
                est = s_arr + (k_arr - s_arr) * 0.40
                # pull x toward body center
                est[:, 0] = center[:, 0] + (est[:, 0] - center[:, 0]) * 0.75
                return est

            est_lh = _hip_estimate(ls_smooth, lk_smooth, shoulder_center)
            est_rh = _hip_estimate(rs_smooth, rk_smooth, shoulder_center)

            # Use detected hip only if it is below the shoulder and above the knee.
            for side, est, s_arr, k_arr in [
                ("LEFT_HIP", est_lh, ls_smooth, lk_smooth),
                ("RIGHT_HIP", est_rh, rs_smooth, rk_smooth),
            ]:
                if side in smooth:
                    arr = smooth[side]
                    missing = ~(np.isfinite(arr[:, 0]) & np.isfinite(arr[:, 1]))
                    reasonable = np.ones(len(arr), dtype=bool)
                    if k_arr is not None:
                        reasonable &= arr[:, 1] > s_arr[:, 1] + 0.05 * frame_h
                        reasonable &= arr[:, 1] < k_arr[:, 1] - 0.05 * frame_h
                    replace = missing | ~reasonable
                    arr[replace] = est[replace]

        smooth_cache = {"key": cache_key, "smooth": smooth}
        _draw_mediapipe_skeleton._smooth_cache = smooth_cache
    smooth = smooth_cache["smooth"]

    def _pt(name: str) -> Optional[Tuple[int, int]]:
        arr = smooth.get(name)
        if arr is None or row_idx >= len(arr):
            return None
        x, y = arr[row_idx]
        if not (np.isfinite(x) and np.isfinite(y)):
            return None
        return int(x), int(y)

    active_arm = active_side.lower() == "left" and "LEFT" or "RIGHT"

    # Landmarks
    ls, rs = _pt("LEFT_SHOULDER"), _pt("RIGHT_SHOULDER")
    le, re = _pt("LEFT_ELBOW"), _pt("RIGHT_ELBOW")
    lw, rw = _pt("LEFT_WRIST"), _pt("RIGHT_WRIST")
    lh, rh = _pt("LEFT_HIP"), _pt("RIGHT_HIP")
    nose = _pt("NOSE")

    left_active = active_arm == "LEFT"
    right_active = active_arm == "RIGHT"

    # Body scale from shoulder width
    shoulder_width = 160.0
    if ls and rs:
        shoulder_width = math.hypot(ls[0] - rs[0], ls[1] - rs[1])
    body_scale = shoulder_width / 160.0

    # Colors (BGR) - high contrast so they survive video compression
    inactive_bone = (120, 120, 120)      # muted grey
    inactive_joint = (150, 150, 150)
    active_bone = (255, 220, 0)          # bright cyan BGR
    active_outline = (200, 100, 0)       # darker blue-cyan outline
    active_joint = (255, 240, 200)
    glow_color = (255, 160, 0)           # cyan glow behind active arm

    def _bone_cv(
        a: Optional[Tuple[int, int]],
        b: Optional[Tuple[int, int]],
        width: int,
        color: Tuple[int, int, int],
        outline: Optional[Tuple[int, int, int]] = None,
        glow: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        if a is None or b is None:
            return
        w = max(2, int(width))
        # Subtle dark halo for contrast; keep thin so skeleton matches body size
        cv2.line(canvas, a, b, (10, 10, 10), w + _s(3), cv2.LINE_AA)
        if glow:
            cv2.line(canvas, a, b, glow, w + _s(4), cv2.LINE_AA)
        cv2.line(canvas, a, b, (20, 20, 20), w + _s(1), cv2.LINE_AA)
        if outline:
            cv2.line(canvas, a, b, outline, w + _s(1), cv2.LINE_AA)
        cv2.line(canvas, a, b, color, w, cv2.LINE_AA)
        r = max(2, w // 2)
        cv2.circle(canvas, a, r, color, -1, cv2.LINE_AA)
        cv2.circle(canvas, b, r, color, -1, cv2.LINE_AA)
        if w >= _s(4):
            hl = tuple(min(255, int(c * 1.15 + 30)) for c in color)
            cv2.line(canvas, a, b, hl, max(1, w // 4), cv2.LINE_AA)

    def _joint_cv(
        pt: Optional[Tuple[int, int]],
        radius: int,
        color: Tuple[int, int, int],
        outline: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        if pt is None:
            return
        r = max(2, int(radius))
        cv2.circle(canvas, pt, r + _s(2), (10, 10, 10), -1, cv2.LINE_AA)
        cv2.circle(canvas, pt, r + _s(1), (20, 20, 20), -1, cv2.LINE_AA)
        if outline:
            cv2.circle(canvas, pt, r + _s(1), outline, -1, cv2.LINE_AA)
        cv2.circle(canvas, pt, r, color, -1, cv2.LINE_AA)
        hl = tuple(min(255, int(c * 1.25 + 40)) for c in color)
        hr = max(1, r // 3)
        cv2.circle(canvas, (pt[0] - r // 3, pt[1] - r // 3), hr, hl, -1, cv2.LINE_AA)

    # Subtle body wireframe ---------------------------------------------------
    torso_pairs = [
        (ls, rs), (lh, rh), (ls, lh), (rs, rh)
    ]
    for a, b in torso_pairs:
        _bone_cv(a, b, max(_s(1), int(shoulder_width / 36)), inactive_bone)

    # Head
    if nose is not None and ls and rs:
        neck = (int((ls[0] + rs[0]) / 2), int((ls[1] + rs[1]) / 2))
        _bone_cv(neck, nose, max(_s(1), int(shoulder_width / 40)), inactive_bone)
        _joint_cv(nose, max(_s(2), int(shoulder_width / 28)), inactive_joint)

    # Subtle clavicles
    if ls and rs:
        _bone_cv(ls, rs, max(_s(1), int(shoulder_width / 38)), inactive_bone)

    # Subtle joints for whole body
    for pt in [ls, rs, le, re, lw, rw, lh, rh]:
        if pt is not None:
            _joint_cv(pt, max(_s(2), int(shoulder_width / 32)), inactive_joint)

    # Active arm (prominent but not oversized) --------------------------------------------------
    if right_active and rs and re:
        _bone_cv(rs, re, max(_s(5), int(shoulder_width / 24)), active_bone, outline=active_outline, glow=glow_color)
        _joint_cv(rs, max(_s(4), int(shoulder_width / 30)), active_joint, outline=active_outline)
        _joint_cv(re, max(_s(4), int(shoulder_width / 30)), active_joint, outline=active_outline)
        if rw:
            _bone_cv(re, rw, max(_s(4), int(shoulder_width / 26)), active_bone, outline=active_outline, glow=glow_color)
            _joint_cv(rw, max(_s(3), int(shoulder_width / 36)), active_joint, outline=active_outline)

    if left_active and ls and le:
        _bone_cv(ls, le, max(_s(5), int(shoulder_width / 24)), active_bone, outline=active_outline, glow=glow_color)
        _joint_cv(ls, max(_s(4), int(shoulder_width / 30)), active_joint, outline=active_outline)
        _joint_cv(le, max(_s(4), int(shoulder_width / 30)), active_joint, outline=active_outline)
        if lw:
            _bone_cv(le, lw, max(_s(4), int(shoulder_width / 26)), active_bone, outline=active_outline, glow=glow_color)
            _joint_cv(lw, max(_s(3), int(shoulder_width / 36)), active_joint, outline=active_outline)


def _draw_3d_skeleton(
    canvas: np.ndarray,
    raw_df: pd.DataFrame,
    row_idx: int,
    frame_w: int,
    frame_h: int,
    active_side: str = "right",
) -> None:
    """Render a true 3-D articulated skeleton overlay using pyrender (optional)."""
    try:
        from skeleton_3d_renderer import Skeleton3DRenderer
    except Exception as exc:
        # pyrender/trimesh not installed on lightweight deploys; fall back to 2-D.
        _draw_mediapipe_skeleton(canvas, raw_df, row_idx, frame_w, frame_h, active_side)
        return
    if row_idx >= len(raw_df):
        return
    row = raw_df.iloc[row_idx]

    landmarks_3d = {}
    for name in ["NOSE", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW",
                 "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP"]:
        xs, ys = f"{name}_X", f"{name}_Y"
        if xs in row.index and ys in row.index:
            x, y = float(row[xs]), float(row[ys])
            if np.isfinite(x) and np.isfinite(y):
                landmarks_3d[name] = (x, y, 0.0)

    if len(landmarks_3d) < 4:
        return

    # Lazy init per canvas size
    key = (frame_w, frame_h)
    renderer = getattr(_draw_3d_skeleton, "_renderer", None)
    if renderer is None or (renderer.width, renderer.height) != key:
        if renderer is not None:
            renderer.close()
        renderer = Skeleton3DRenderer(width=frame_w, height=frame_h)
        _draw_3d_skeleton._renderer = renderer

    try:
        skel = renderer.render(landmarks_3d, active_side=active_side)
    except Exception as exc:
        print(f"3-D skeleton render failed: {exc}; falling back to 2-D")
        _draw_mediapipe_skeleton(canvas, raw_df, row_idx, frame_w, frame_h, active_side)
        return

    if skel.shape[:2] != canvas.shape[:2]:
        skel = cv2.resize(skel, (canvas.shape[1], canvas.shape[0]))

    alpha = skel[:, :, 3:4].astype(np.float32) / 255.0
    fg = skel[:, :, :3].astype(np.float32)
    bg = canvas.astype(np.float32)
    blended = (fg * alpha * 0.85 + bg * (1 - alpha * 0.85)).astype(np.uint8)
    canvas[:] = blended


def _draw_simple_skeleton(
    canvas: np.ndarray,
    raw_df: pd.DataFrame,
    row_idx: int,
    frame_w: int,
    frame_h: int,
    active_side: str = "right",
) -> None:
    """Fallback stick skeleton."""
    if row_idx >= len(raw_df):
        return
    row = raw_df.iloc[row_idx]

    def _pt(name: str) -> Optional[Tuple[int, int]]:
        xs, ys = f"{name}_X", f"{name}_Y"
        if xs not in row.index or ys not in row.index:
            return None
        x, y = float(row[xs]), float(row[ys])
        if not (np.isfinite(x) and np.isfinite(y)):
            return None
        return int(x * frame_w), int(y * frame_h)

    active_arm = active_side.lower() == "left" and "LEFT" or "RIGHT"
    color = (0, 200, 255)
    inactive = (180, 190, 200)
    pairs = [
        ("LEFT_SHOULDER", "RIGHT_SHOULDER"), ("LEFT_SHOULDER", "LEFT_ELBOW"),
        ("LEFT_ELBOW", "LEFT_WRIST"), ("RIGHT_SHOULDER", "RIGHT_ELBOW"),
        ("RIGHT_ELBOW", "RIGHT_WRIST"), ("LEFT_SHOULDER", "LEFT_HIP"),
        ("RIGHT_SHOULDER", "RIGHT_HIP"), ("LEFT_HIP", "RIGHT_HIP"),
    ]
    for a_name, b_name in pairs:
        a, b = _pt(a_name), _pt(b_name)
        if a and b:
            is_active = active_arm in a_name and active_arm in b_name
            cv2.line(canvas, a, b, color if is_active else inactive, 3, cv2.LINE_AA)
    for name in ["LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
                 "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP"]:
        pt = _pt(name)
        if pt:
            cv2.circle(canvas, pt, 5, color if active_arm in name else inactive, -1, cv2.LINE_AA)


def _reencode_to_h264(src: Path, dst: Path) -> bool:
    """Re-encode an OpenCV mp4v file to browser-playable H.264 using ffmpeg."""
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        print("ffmpeg not found — validation video will stay in OpenCV mp4v format (may not play in browser)")
        return False
    try:
        cmd = [
            ffmpeg,
            "-y",
            "-i", str(src),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-an",
            str(dst),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if result.returncode != 0:
            print(f"ffmpeg stderr: {result.stderr.decode('utf-8', errors='ignore')[:500]}")
        return result.returncode == 0 and dst.exists() and dst.stat().st_size > 1000
    except Exception as exc:
        print(f"ffmpeg re-encode failed: {exc}")
        return False


def _write_h264_with_imageio(frames, output_path: Path, fps: float) -> bool:
    """Write H.264 MP4 using imageio's ffmpeg backend (fallback when OpenCV can't)."""
    try:
        import imageio
        writer = imageio.get_writer(str(output_path), fps=fps, codec="libx264", quality=8, pixelformat="yuv420p")
        for frame in frames:
            writer.append_data(frame)
        writer.close()
        return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as exc:
        print(f"imageio write failed: {exc}")
        return False


# ------------------------------------------------------------------
# High-quality anti-aliased drawing helpers (Pillow + FreeType)
# ------------------------------------------------------------------
_PIL_FONTS: Dict[Tuple[str, int], Any] = {}


def _pil_font(size: int, bold: bool = False) -> Any:
    """Return a cached PIL font at the requested pixel size.

    Prefer matplotlib's bundled DejaVu Sans (guaranteed where matplotlib
    is installed), then fall back to common system fonts, then Pillow's
    default bitmap font.
    """
    key = ("pil", size, bold)
    if key not in _PIL_FONTS:
        font = None

        # 1) matplotlib bundled DejaVu Sans
        try:
            import matplotlib
            mpl_dejavu = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
            if mpl_dejavu.exists():
                font = ImageFont.truetype(str(mpl_dejavu), size)
        except Exception:
            font = None

        # 2) common Linux system fonts
        if font is None:
            system_candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
                "arialbd.ttf" if bold else "arial.ttf",
                "segoeuib.ttf" if bold else "segoeui.ttf",
            ]
            for c in system_candidates:
                try:
                    font = ImageFont.truetype(c, size)
                    break
                except Exception:
                    continue

        # 3) last resort: bitmap default (tiny)
        if font is None:
            print(f"WARNING: no TrueType font found for size={size} bold={bold}; using Pillow default bitmap font.")
            font = ImageFont.load_default()

        _PIL_FONTS[key] = font
    return _PIL_FONTS[key]


def _bgr_to_rgb(c: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return (c[2], c[1], c[0])


def _draw_text_pil(
    draw: Any,
    text: str,
    x: int,
    y: int,
    size: int,
    color: Tuple[int, int, int],
    bold: bool = False,
    anchor: str = "lt",
    stroke: int = 0,
    stroke_color: Tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Draw anti-aliased text with optional outline."""
    font = _pil_font(int(round(size * _UI_SCALE)), bold=bold)
    draw.text((x, y), text, font=font, fill=_bgr_to_rgb(color), anchor=anchor,
              stroke_width=int(round(stroke * _UI_SCALE)) if stroke else 0,
              stroke_fill=_bgr_to_rgb(stroke_color))


def _text_size_pil(text: str, size: int, bold: bool = False) -> Tuple[int, int]:
    font = _pil_font(int(round(size * _UI_SCALE)), bold=bold)
    bbox = font.getbbox(text)
    if bbox is None:
        return 0, 0
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_value_box_pil(
    draw: Any,
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    value: Any,
    unit: str,
    color: Tuple[int, int, int],
    value_size: int = 22,
) -> None:
    """Draw a rounded metric box with label/value/unit."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    r = _s(6)
    # Background
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=(45, 48, 55))
    # Border
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, outline=_bgr_to_rgb(color), width=max(1, _s(2)))

    # Label
    label_size = max(11, _s(12))
    _draw_text_pil(draw, label, x + _s(6), y + _s(4), label_size, (180, 180, 180))

    # Value
    if isinstance(value, float):
        value_text = f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"
    else:
        value_text = str(value)
    if value_text.lower() == "nan":
        value_text = "--"
    _draw_text_pil(draw, value_text, x + _s(6), y + _s(20), value_size, (255, 255, 255), bold=True)

    # Unit
    if unit:
        unit_size = max(10, _s(11))
        uw, uh = _text_size_pil(unit, unit_size)
        _draw_text_pil(draw, unit, x + w - _s(6) - uw, y + _s(22), unit_size, color)


def _draw_mini_graph_pil(
    draw: Any,
    values: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    color: Tuple[int, int, int],
    current_idx: int = 0,
    label: str = "",
    max_val: Optional[float] = None,
) -> None:
    """Draw an anti-aliased mini time-series graph."""
    x, y, w, h = int(x), int(y), int(w), int(h)
    if len(values) < 2:
        return
    valid = np.asarray(values, dtype=float)
    finite = valid[np.isfinite(valid)]
    if len(finite) == 0:
        return
    mx = max_val if max_val is not None else (float(np.nanmax(valid)) if np.nanmax(valid) > 0 else 1.0)
    mn = float(np.nanmin(valid))
    rng = mx - mn if mx != mn else 1.0

    # Background
    r = _s(6)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=(30, 32, 38))

    # Grid lines
    rgb = _bgr_to_rgb(color)
    grid = (60, 60, 65)
    for gy in [y + h // 4, y + h // 2, y + 3 * h // 4]:
        draw.line([(x, gy), (x + w, gy)], fill=grid, width=max(1, _s(1)))

    # Series line
    pts = []
    for i, v in enumerate(valid):
        px = x + int(i * w / len(valid))
        py = y + h - int((v - mn) / rng * h) if np.isfinite(v) else y + h
        pts.append((px, py))

    for i in range(1, len(pts)):
        if np.isfinite(valid[i - 1]) and np.isfinite(valid[i]):
            draw.line([pts[i - 1], pts[i]], fill=rgb, width=max(1, _s(3)))

    if 0 <= current_idx < len(pts) and np.isfinite(valid[current_idx]):
        cx, cy = pts[current_idx]
        rdot = _s(6)
        draw.ellipse([cx - rdot, cy - rdot, cx + rdot, cy + rdot], fill=(255, 255, 255))
        draw.ellipse([cx - rdot // 2, cy - rdot // 2, cx + rdot // 2, cy + rdot // 2], fill=rgb)

    if label:
        label_size = max(11, _s(12))
        _draw_text_pil(draw, label, x + _s(5), y - _s(12), label_size, (200, 200, 200))


def _draw_panel_pil(
    width: int,
    height: int,
    analysis: Dict[str, Any],
    df: pd.DataFrame,
    frame_i: int,
    n_frames_video: int,
    speed: np.ndarray,
    elbow_angle: np.ndarray,
    straightness: np.ndarray,
    summary: Dict[str, Any],
    scale_note: str,
    scale_ok: bool,
    use_cm_velocity: bool,
) -> np.ndarray:
    """Render the metrics panel in the app's dark glass style at 2x supersampling."""
    # Design at 2x native resolution, then downsample for crisp anti-aliasing.
    supersample = 2
    W, H = width * supersample, height * supersample
    _set_ui_scale(float(supersample))

    # App palette
    bg = (18, 24, 32)          # #121820
    card_bg = (255, 255, 255)
    card_bg_alpha = 24         # 0.09 * 255 ~ 23
    border_alpha = 31          # 0.12 * 255 ~ 31
    text_primary = (255, 255, 255)
    text_secondary = (255, 255, 255)
    text_muted = (148, 163, 184)

    panel = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(panel)

    def rgb(c):
        return _bgr_to_rgb(c)

    def _rounded_rect_alpha(draw, bbox, radius, alpha_fill, alpha_border):
        """Draw a rounded glass rectangle over bg."""
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(bbox, radius=radius, fill=(255, 255, 255, alpha_fill))
        overlay_draw.rounded_rectangle(bbox, radius=radius, outline=(255, 255, 255, alpha_border), width=1)
        panel.paste(Image.alpha_composite(panel.convert("RGBA"), overlay).convert("RGB"), (0, 0))

    m = _s(18)
    x = m
    y = m

    # Header ---------------------------------------------------------------
    _draw_text_pil(draw, "NeuroLab Unified Validation", x, y, 30, text_primary, bold=True)
    y += _s(34)
    phase = str(analysis.get("comparison_role", analysis.get("phase", "TRIAL"))).upper()
    _draw_text_pil(draw, f"{phase}  •  Frame {frame_i + 1}/{n_frames_video}", x, y, 14, text_muted)
    y += _s(22)
    _draw_text_pil(draw, scale_note, x, y, 12, (252, 211, 77) if scale_ok else (251, 113, 133))
    y += _s(44)

    row_idx = min(frame_i, len(df) - 1)
    cur_speed = speed[row_idx] if row_idx < len(speed) else 0.0
    cur_straightness = straightness[row_idx] if row_idx < len(straightness) else float("nan")

    # Official metrics come from the analysis dict (same numbers as the table).
    # We display those directly so the video overlay is guaranteed to match the table.
    official_nvp = int(_safe_float(analysis.get("nvp")))
    official_straightness = _safe_float(analysis.get("straightness"))
    official_pause_time = _safe_float(analysis.get("pause_time_sec"))
    official_n_stops = int(_safe_float(analysis.get("number_of_stops")))
    official_trunk_ratio = _safe_float(analysis.get("trunk_ratio"))
    official_shoulder_elev = _safe_float(analysis.get("shoulder_elevation_norm"))
    official_elbow_mean = _safe_float(analysis.get("elbow_angle_mean_deg"))
    official_elbow_range = _safe_float(analysis.get("elbow_angle_range_deg"))
    official_movement_time = _safe_float(analysis.get("movement_time_sec"))
    official_peak_velocity = _safe_float(analysis.get("peak_velocity_cm_s") or analysis.get("peak_velocity_px_s"))
    official_time_to_peak = _safe_float(analysis.get("time_to_peak_velocity_sec"))

    # For the animated NVP counter we still want it to grow with peaks, but it must
    # land exactly on the official table value at the end of the video.
    speed_std = float(np.nanstd(speed)) if len(speed) else 0.0
    speed_peak = float(np.nanmax(speed)) if len(speed) else 0.0
    nvp_prominence = speed_std * 0.30 if speed_std > 0 else speed_peak * 0.05
    nvp_peak_indices = find_peaks(speed, prominence=nvp_prominence)[0]
    computed_nvp = len(nvp_peak_indices)
    if not analysis.get("velocity_profile"):
        print(f"UV renderer fallback: velocity_profile missing, computed_nvp={computed_nvp}, official_nvp={official_nvp}")

    # Scale peak count so the final frame equals official_nvp.
    if computed_nvp > 0 and official_nvp > 0:
        nvp_so_far = int(np.sum(nvp_peak_indices <= row_idx))
        nvp_so_far = int(round(nvp_so_far * official_nvp / computed_nvp))
    elif official_nvp > 0:
        # No speed profile — show official value immediately.
        nvp_so_far = official_nvp
    else:
        nvp_so_far = computed_nvp
    nvp_so_far = max(0, min(nvp_so_far, official_nvp if official_nvp > 0 else computed_nvp))
    # Hard guarantee: the final frame must show the official table value.
    if frame_i >= n_frames_video - 1 and official_nvp > 0:
        nvp_so_far = official_nvp

    speed_threshold = 0.05 * speed_peak if speed_peak > 0 else 1.0
    is_pause = cur_speed < speed_threshold

    start_idx = int(analysis.get("movement_onset_frame", 0) or 0)
    end_idx = int(analysis.get("movement_offset_frame", len(df) - 1) or (len(df) - 1))
    start_idx = max(0, min(start_idx, len(df) - 1))
    end_idx = max(start_idx, min(end_idx, len(df) - 1))
    cur_elbow = elbow_angle[row_idx] if row_idx < len(elbow_angle) else float("nan")
    elbow_range = float(np.nanmax(elbow_angle[start_idx : end_idx + 1]) - np.nanmin(elbow_angle[start_idx : end_idx + 1])) if end_idx > start_idx else float("nan")

    gap = _s(14)
    col_w = (W - 2 * m - gap) // 2
    box_h = _s(70)

    def section_header(label, color):
        nonlocal y
        _draw_text_pil(draw, label, x, y, 14, color, bold=True)
        y += _s(22)
        draw.line([(x, y), (W - m, y)], fill=rgb(color), width=max(1, _s(2)))
        y += _s(14)

    def metric_card(label, value, unit, color, width=col_w):
        nonlocal x, y
        r = _s(12)
        # glass card
        _rounded_rect_alpha(draw, [x, y, x + width, y + box_h], r, card_bg_alpha, border_alpha)
        # left accent bar
        draw.rounded_rectangle([x + _s(3), y + _s(12), x + _s(8), y + box_h - _s(12)], radius=_s(3), fill=rgb(color))
        # label
        _draw_text_pil(draw, label, x + _s(18), y + _s(10), 14, text_secondary)
        # unit top-right
        if unit:
            uw, _ = _text_size_pil(unit, 13)
            _draw_text_pil(draw, unit, x + width - _s(12) - uw, y + _s(11), 13, text_muted)
        # value (align precision with the kinematics table: 3 decimals for small
        # values such as straightness / shoulder elevation, 2 for medium, 1 for large)
        if isinstance(value, float):
            av = abs(value)
            if av >= 10:
                value_text = f"{value:.1f}"
            elif av >= 1:
                value_text = f"{value:.2f}"
            else:
                value_text = f"{value:.3f}"
        else:
            value_text = str(value)
        if value_text.lower() == "nan":
            value_text = "--"
        _draw_text_pil(draw, value_text, x + _s(18), y + _s(32), 26, text_primary, bold=True)

    def pair_row(label1, val1, unit1, color1, label2, val2, unit2, color2):
        nonlocal x, y
        x = m
        metric_card(label1, val1, unit1, color1)
        x = m + col_w + gap
        metric_card(label2, val2, unit2, color2)
        y += box_h + _s(12)

    def mini_graph(values, color, label, max_val=None):
        nonlocal x, y
        h = _s(64)
        w = W - 2 * m
        r = _s(12)
        y += _s(20)  # reserve space for floating label
        _rounded_rect_alpha(draw, [x, y, x + w, y + h], r, card_bg_alpha, border_alpha)

        valid = np.asarray(values, dtype=float)
        finite = valid[np.isfinite(valid)]
        if len(finite) > 1:
            mx = max_val if max_val is not None else (float(np.nanmax(valid)) if np.nanmax(valid) > 0 else 1.0)
            mn = float(np.nanmin(valid))
            rng = mx - mn if mx != mn else 1.0
            pts = []
            pad = _s(10)
            gw = w - 2 * pad
            gh = h - 2 * pad
            for i, v in enumerate(valid):
                px_ = x + pad + int(i * gw / len(valid))
                py_ = y + h - pad - int((v - mn) / rng * gh) if np.isfinite(v) else y + h - pad
                pts.append((px_, py_))
            for i in range(1, len(pts)):
                if np.isfinite(valid[i - 1]) and np.isfinite(valid[i]):
                    draw.line([pts[i - 1], pts[i]], fill=rgb(color), width=max(1, _s(3)))
            if 0 <= row_idx < len(pts) and np.isfinite(valid[row_idx]):
                cx, cy = pts[row_idx]
                rd = _s(5)
                draw.ellipse([cx - rd, cy - rd, cx + rd, cy + rd], fill=(255, 255, 255))
                draw.ellipse([cx - rd // 2, cy - rd // 2, cx + rd // 2, cy + rd // 2], fill=rgb(color))
        _draw_text_pil(draw, label, x + _s(12), y - _s(17), 13, text_muted)
        y += h + _s(12)

    # SMOOTHNESS -----------------------------------------------------------
    section_header("SMOOTHNESS", (56, 189, 248))  # sky-400
    pair_row("NVP", nvp_so_far, f"/{summary['nvp']:.0f}", (56, 189, 248),
             "Straightness", summary["straightness"], "", (56, 189, 248))
    pair_row("Pause Time", summary["pause_time_sec"], "s", (251, 113, 133) if is_pause else (56, 189, 248),
             "Stops", summary["number_of_stops"], "", (56, 189, 248))
    mini_graph(speed, (56, 189, 248), "Palm Speed")

    # KINEMATICS -----------------------------------------------------------
    section_header("KINEMATICS", (251, 191, 36))  # amber-400
    pair_row("Trunk Ratio", summary["trunk_ratio"] * 100, "%", (251, 191, 36),
             "Shoulder Elev", summary["shoulder_elevation_norm"], "SW", (251, 191, 36))
    pair_row("Move Time", summary["movement_time_sec"], "s", (251, 191, 36),
             "Elbow Angle", summary["elbow_angle_mean_deg"], "deg", (251, 191, 36))
    if use_cm_velocity:
        pair_row("Peak Vel", summary["peak_velocity_cm_s"], "cm/s", (251, 191, 36),
                 "Time to Peak", summary["time_to_peak_velocity_sec"], "s", (251, 191, 36))
    else:
        pair_row("Peak Vel", summary["peak_velocity_px_s"], "px/s", (251, 191, 36),
                 "Time to Peak", summary["time_to_peak_velocity_sec"], "s", (251, 191, 36))
    mini_graph(df["trunk_x"].astype(float).values, (251, 191, 36), "Trunk X")

    # JOINT ANGLE ----------------------------------------------------------
    section_header("JOINT ANGLE", (52, 211, 153))  # emerald-400
    pair_row("Elbow Angle", cur_elbow, "deg", (52, 211, 153),
             "Elbow Range", elbow_range, "deg", (52, 211, 153))
    mini_graph(elbow_angle, (52, 211, 153), "Elbow Angle (deg)", max_val=180)

    # STRAIGHTNESS ---------------------------------------------------------
    section_header("STRAIGHTNESS", (252, 211, 77))  # amber-300
    x = m
    # Use the official table straightness so the big card matches the kinematics table.
    metric_card("Path Straightness", summary["straightness"], "", (252, 211, 77), width=W - 2 * m)
    y += box_h + _s(8)
    mini_graph(straightness, (252, 211, 77), "Straightness")

    # Progress bar ---------------------------------------------------------
    pb_h = _s(10)
    pb_y = H - m - pb_h
    progress = (frame_i + 1) / max(1, n_frames_video)
    draw.rounded_rectangle([m, pb_y, W - m, pb_y + pb_h], radius=pb_h // 2, fill=(30, 41, 59))
    if progress > 0:
        draw.rounded_rectangle([m, pb_y, m + int((W - 2 * m) * progress), pb_y + pb_h], radius=pb_h // 2, fill=rgb((56, 189, 248)))
    _draw_text_pil(draw, f"Progress: {progress * 100:.1f}%", m, pb_y - _s(16), 12, text_secondary)
    # Downsample back to native width
    panel = panel.resize((width, height), Image.Resampling.LANCZOS)
    _set_ui_scale(1.0)
    return np.array(panel)


def _draw_straightness_trajectory(
    canvas: np.ndarray,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    row_idx: int,
    start_idx: int,
    end_idx: int,
    color: Tuple[int, int, int] = (252, 211, 77),
) -> None:
    """Draw the actual hand trajectory and the ideal straight line so far."""
    if end_idx <= start_idx or row_idx < start_idx:
        return
    end_idx = min(end_idx, row_idx)
    xs = palm_x[start_idx : end_idx + 1]
    ys = palm_y[start_idx : end_idx + 1]
    valid = np.isfinite(xs) & np.isfinite(ys)
    xs, ys = xs[valid], ys[valid]
    if len(xs) < 2:
        return

    pts = np.column_stack([xs, ys]).astype(np.int32)
    # Smooth trajectory - single anti-aliased polyline
    cv2.polylines(canvas, [pts], False, color, 3, cv2.LINE_AA)

    # Ideal straight line from start to current position
    start_pt = (int(xs[0]), int(ys[0]))
    cur_pt = (int(xs[-1]), int(ys[-1]))
    cv2.line(canvas, start_pt, cur_pt, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.circle(canvas, start_pt, 5, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, start_pt, 3, color, -1, cv2.LINE_AA)
    cv2.circle(canvas, cur_pt, 5, (255, 255, 255), -1, cv2.LINE_AA)
    cv2.circle(canvas, cur_pt, 3, color, -1, cv2.LINE_AA)


def _draw_label_near_pil(
    canvas: np.ndarray,
    pt: Optional[Tuple[int, int]],
    text: str,
    color: Tuple[int, int, int],
    offset: Tuple[int, int] = (14, -14),
    orig_w: int = 0,
    orig_h: int = 0,
) -> None:
    """Draw a landmark-aware metric label with a dark pill background."""
    if pt is None or not text:
        return
    tx = pt[0] + offset[0]
    ty = pt[1] + offset[1]
    tx = max(_s(4), min(tx, orig_w - _s(4)))
    ty = max(_s(18), min(ty, orig_h - _s(4)))

    size = max(16, _s(18))
    tw, th = _text_size_pil(text, size, bold=True)
    pad_x = _s(10)
    pad_y = _s(6)
    r = _s(6)
    x1, y1 = tx - pad_x, ty - th - pad_y
    x2, y2 = tx + tw + pad_x, ty + pad_y

    # Clip to canvas bounds and operate on a small ROI.
    y1 = max(0, y1)
    x1 = max(0, x1)
    y2 = min(canvas.shape[0], y2)
    x2 = min(canvas.shape[1], x2)
    if x2 <= x1 or y2 <= y1:
        return

    roi = canvas[y1:y2, x1:x2]
    pil = Image.fromarray(roi)
    draw = ImageDraw.Draw(pil)

    draw.rounded_rectangle([0, 0, x2 - x1, y2 - y1], radius=r, fill=(15, 15, 15), outline=_bgr_to_rgb(color), width=max(1, _s(2)))
    _draw_text_pil(draw, text, tx - x1, ty - th - y1, size, (255, 255, 255), bold=True)

    canvas[y1:y2, x1:x2] = np.array(pil)


def _draw_pause_overlay_pil(
    canvas: np.ndarray,
    orig_w: int,
) -> None:
    """Apply a subtle blue pause tint over the video region and draw PAUSE text."""
    video_roi = canvas[:, :orig_w].astype(np.float32)
    tinted = video_roi * 0.85 + np.array([60, 0, 0], dtype=np.float32) * 0.15
    canvas[:, :orig_w] = np.clip(tinted, 0, 255).astype(np.uint8)

    size = max(50, _s(55))
    text = "PAUSE"
    tw, th = _text_size_pil(text, size, bold=True)
    x = _s(20)
    y = _s(20)
    pad = _s(14)
    x1, y1 = x - pad, y - pad
    x2, y2 = x + tw + pad, y + th + pad

    # Clip to video region and operate on a small ROI.
    x2 = min(orig_w, x2)
    y2 = min(canvas.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return

    roi = canvas[y1:y2, x1:x2]
    pil = Image.fromarray(roi)
    draw = ImageDraw.Draw(pil)

    draw.rounded_rectangle([0, 0, x2 - x1, y2 - y1], radius=_s(10), fill=(15, 15, 40), outline=(255, 100, 100), width=max(2, _s(3)))
    _draw_text_pil(draw, text, x - x1, y - y1, size, (255, 100, 100), bold=True)
    canvas[y1:y2, x1:x2] = np.array(pil)


def _draw_text(
    img: np.ndarray,
    text: str,
    x: int,
    y: int,
    size: float = 0.6,
    color: Tuple[int, int, int] = (255, 255, 255),
    thickness: int = 1,
) -> None:
    # Deprecated: kept for any callers outside the renderer.
    t = max(1, int(thickness * _UI_SCALE))
    s = size * _UI_SCALE
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, s, (0, 0, 0), t + max(1, _s(2)), cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, s, color, t, cv2.LINE_AA)



# ------------------------------------------------------------------
# Metrics helpers
# ------------------------------------------------------------------
def _safe_float(v: Any, default: float = float("nan")) -> float:
    try:
        if v is None:
            return default
        f = float(v)
        return f if np.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _compute_straightness_series(palm_x: np.ndarray, palm_y: np.ndarray) -> np.ndarray:
    """Cumulative path straightness at each frame (displacement/path_length)."""
    n = len(palm_x)
    out = np.full(n, float("nan"))
    if n < 2:
        return out
    dx = np.hypot(np.diff(palm_x, prepend=palm_x[0]), np.diff(palm_y, prepend=palm_y[0]))
    cum_path = np.cumsum(dx)
    start_x, start_y = palm_x[0], palm_y[0]
    disp = np.hypot(palm_x - start_x, palm_y - start_y)
    valid = cum_path > 0
    out[valid] = disp[valid] / cum_path[valid]
    return np.clip(out, 0.0, 1.0)


def _extract_profile_arrays(
    analysis: Dict[str, Any]
) -> Dict[str, Optional[np.ndarray]]:
    """Return the exact palm speed / straightness / elbow-angle arrays used by the analysis."""
    out: Dict[str, Optional[np.ndarray]] = {
        "palm_speed_profile": None,
        "straightness_series": None,
        "elbow_angle_series": None,
        "time": None,
        "fs_hz": None,
    }
    vp = analysis.get("velocity_profile")
    if isinstance(vp, dict):
        for k in ("speed", "palm_speed", "palm_speed_profile"):
            if k in vp:
                try:
                    arr = np.asarray(vp[k], dtype=float)
                    if arr.size:
                        out["palm_speed_profile"] = arr
                        break
                except Exception:
                    pass
        if "time" in vp:
            try:
                out["time"] = np.asarray(vp["time"], dtype=float)
            except Exception:
                pass
        if out["time"] is None and out["palm_speed_profile"] is not None:
            out["time"] = np.arange(len(out["palm_speed_profile"])) / 60.0
    if out["fs_hz"] is None:
        out["fs_hz"] = float(analysis.get("analysis_fs_hz") or analysis.get("fs_hz") or 60.0)
    return out


def _compute_speed(df: pd.DataFrame) -> np.ndarray:
    """Tangential palm speed in px/s (fallback if no velocity_profile provided)."""
    if "palm_x" not in df.columns or "palm_y" not in df.columns:
        return np.zeros(len(df))
    px = df["palm_x"].astype(float).values
    py = df["palm_y"].astype(float).values
    time = df["time"].astype(float).values if "time" in df.columns else np.arange(len(df)) / 30.0
    dt = np.median(np.diff(time))
    fs = 1.0 / dt if dt > 0 else 30.0
    vx = np.gradient(px) * fs
    vy = np.gradient(py) * fs
    return np.sqrt(vx**2 + vy**2)


def _compute_nvp_and_stops(
    speed: np.ndarray,
    time: np.ndarray,
    prominence_frac: float = 0.30,
    min_pause_s: float = 0.1,
) -> Tuple[int, float, int]:
    """
    Number of velocity peaks, total pause time, and number of stops.
    Matches stroke_kinematic_pipeline.calculate_nvp() (prominence = 0.30 * std).
    """
    if len(speed) == 0:
        return 0, 0.0, 0
    std = float(np.nanstd(speed)) if np.nanstd(speed) > 0 else 0.0
    peak = float(np.nanmax(speed)) if np.nanmax(speed) > 0 else 1.0
    prominence = std * prominence_frac if std > 0 else peak * 0.05
    peaks, _ = find_peaks(speed, prominence=prominence)
    threshold = 0.05 * peak
    paused = speed < threshold

    pause_time = 0.0
    n_stops = 0
    i = 0
    while i < len(paused):
        if paused[i]:
            j = i
            while j < len(paused) and paused[j]:
                j += 1
            dur = time[min(j, len(time) - 1)] - time[i]
            if dur >= min_pause_s:
                pause_time += dur
                n_stops += 1
            i = j
        else:
            i += 1
    return len(peaks), pause_time, n_stops


def _compute_elbow_angle(df: pd.DataFrame) -> np.ndarray:
    """Elbow flexion angle from shoulder-elbow-wrist vectors."""
    if not all(c in df.columns for c in ("shoulder_x", "shoulder_y", "elbow_x", "elbow_y", "wrist_x", "wrist_y")):
        return np.full(len(df), np.nan)
    sx, sy = df["shoulder_x"].values, df["shoulder_y"].values
    ex, ey = df["elbow_x"].values, df["elbow_y"].values
    wx, wy = df["wrist_x"].values, df["wrist_y"].values

    v1x, v1y = sx - ex, sy - ey
    v2x, v2y = wx - ex, wy - ey
    m1 = np.hypot(v1x, v1y)
    m2 = np.hypot(v2x, v2y)
    cos = np.clip((v1x * v2x + v1y * v2y) / (m1 * m2 + 1e-9), -1.0, 1.0)
    return np.degrees(np.arccos(cos))


# ------------------------------------------------------------------
# Main renderer
# ------------------------------------------------------------------
def render_unified_validation_video(
    video_path: str,
    output_path: str,
    analysis: Dict[str, Any],
    landmarks_csv: Optional[str] = None,
    panel_width: int = 560,
    force_rotation: str = "auto",
    resolution: str = "4k",
) -> str:
    """
    Render the unified validation video.

    Parameters
    ----------
    video_path: path to original uploaded video
    output_path: path to write the output MP4
    analysis: dict returned by stroke_kinematic_pipeline.analyze_trial()
    landmarks_csv: optional analysis-ready landmarks CSV; if None, the function
        tries to infer it from analysis metadata or the video path
    panel_width: width of the right-hand metrics panel in pixels
    """
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve landmarks CSV
    if landmarks_csv is None:
        candidates = []
        if analysis.get("csv_filename"):
            candidates.append(Path(analysis["csv_filename"]))
        if analysis.get("intermediate_files", {}).get("filtered_landmarks_csv"):
            candidates.append(Path(analysis["intermediate_files"]["filtered_landmarks_csv"]))
        if analysis.get("intermediate_files", {}).get("raw_pose_csv"):
            candidates.append(Path(analysis["intermediate_files"]["raw_pose_csv"]))
        # sibling landmarks CSV
        candidates.append(video_path.parent / (video_path.stem + "_landmarks.csv"))
        candidates.append(video_path.with_suffix(".csv"))
        for cand in candidates:
            if cand and cand.exists():
                landmarks_csv = str(cand)
                break

    if not landmarks_csv or not Path(landmarks_csv).exists():
        raise FileNotFoundError(f"Could not find landmarks CSV for validation video (tried {candidates})")

    # Open video first to know native dimensions (needed if we must rebuild
    # the analysis-ready landmarks from a raw MediaPipe CSV).
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
    n_frames_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    df = pd.read_csv(landmarks_csv)

    # Auto-rotate based on video metadata so phones/tablets display upright.
    # force_rotation can override: "auto" | "0" | "90" | "180" | "270" | "-90".
    if force_rotation and force_rotation.lower() != "auto":
        rotation = int(force_rotation) % 360
    else:
        rotation = _get_video_rotation(video_path)
        # If metadata reports 90/270 but the stored video is already portrait
        # (h > w), the rotation tag is stale/copied; keep the video as-is.
        raw_rotation = rotation
        if rotation in (90, 270) and native_w < native_h:
            rotation = 0
            print(f"Ignoring stale rotation metadata {raw_rotation} for portrait video ({native_w}x{native_h})")
        # If metadata reports no rotation, infer from landmark layout so the
        # person ends up upright without any manual setting.
        # IMPORTANT: inference from landmarks is only safe for landscape clips
        # where a phone was laid on its side; portrait clips are kept as-is.
        if rotation == 0 and native_w >= native_h:
            inferred = _infer_rotation_from_landmarks(df, native_w, native_h)
            if inferred != 0:
                rotation = inferred
                print(f"Inferred UV video rotation: {rotation}")
    required = {"palm_x", "palm_y", "wrist_x", "wrist_y", "shoulder_x", "shoulder_y", "elbow_x", "elbow_y", "trunk_x", "trunk_y"}
    missing = required - set(df.columns)
    if missing:
        # If the frontend stored the raw_pose CSV name, try the cleaned sibling CSV.
        if Path(landmarks_csv).name.endswith("_raw_pose.csv"):
            cleaned_csv = Path(landmarks_csv).with_name(Path(landmarks_csv).name.replace("_raw_pose.csv", ".csv"))
            if cleaned_csv.exists():
                df = pd.read_csv(cleaned_csv)
        # If still missing (e.g. legacy mode copied raw MediaPipe columns), build
        # the analysis-ready dataframe from the raw landmarks on the fly.
        if (missing - set(df.columns)) and {"LEFT_SHOULDER_X", "RIGHT_SHOULDER_X"}.intersection(df.columns):
            try:
                from mediapipe_csv_extractor import build_analysis_dataframe
                side = str(analysis.get("affected_side") or analysis.get("side_analyzed") or "auto").lower()
                view = str(analysis.get("camera_view") or "auto").lower()
                fps = float(analysis.get("fs_hz") or analysis.get("fps") or video_fps or 30.0)
                df, _ = build_analysis_dataframe(
                    df, frame_width=native_w, frame_height=native_h, fps=fps,
                    affected_side=side, camera_view=view,
                    butterworth_cutoff_hz=4.0, butterworth_order=4,
                )
            except Exception as exc:
                print(f"Could not build analysis dataframe from raw landmarks: {exc}")
        if missing - set(df.columns):
            raise ValueError(f"Missing required columns in landmarks CSV: {missing - set(df.columns)}")

    # Make sure all required columns exist after fallback
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Apply the same rotation to landmark coordinates so overlays line up.
    df = _rotate_landmark_columns(df, rotation, native_w, native_h)

    # Dimensions used for layout are the *rotated* frame dimensions.
    if rotation in (90, 270):
        orig_w, orig_h = native_h, native_w
    else:
        orig_w, orig_h = native_w, native_h

    # Use native resolution but skip costly interpolation
    scale = 1.0
    orig_w = int(orig_w * scale)
    orig_h = int(orig_h * scale) if scale != 1.0 else orig_h
    panel_width = int(panel_width * scale)

    def s(v):
        if isinstance(v, float):
            return v * scale
        return int(v * scale)

    _set_ui_scale(scale)

    print(f"UV renderer: native={native_w}x{native_h}, rotation={rotation}, "
          f"scale={scale:.3f}, output={orig_w + panel_width}x{orig_h}")

    profile = _extract_profile_arrays(analysis)
    profile_speed = profile["palm_speed_profile"]
    profile_time = profile["time"]
    profile_fs = profile["fs_hz"] or float(analysis.get("analysis_fs_hz") or analysis.get("fs_hz") or video_fps or 30.0)

    # Speed: prefer the exact analysis profile; otherwise derive from landmarks.
    speed = profile_speed if profile_speed is not None else _compute_speed(df)
    time = profile_time if profile_time is not None else (
        df["time"].astype(float).values if "time" in df.columns else np.arange(len(df)) / 30.0
    )
    fps = float(analysis.get("analysis_fs_hz", analysis.get("fs_hz", video_fps)))
    if fps <= 0:
        fps = profile_fs if profile_fs > 0 else (1.0 / np.median(np.diff(time)) if len(time) > 1 else 30.0)

    nvp, pause_time, n_stops = _compute_nvp_and_stops(speed, time)
    elbow_angle = _compute_elbow_angle(df)

    # Map current video frame to the analysis-profile index (same time base).
    def _profile_idx_for_frame(frame_i: int) -> int:
        if profile_speed is None or profile_time is None or len(profile_time) == 0:
            return min(frame_i, len(speed) - 1)
        t = frame_i / max(video_fps, 1e-6)
        idx = int(np.argmin(np.abs(profile_time - t)))
        return max(0, min(idx, len(profile_speed) - 1))

    # Override start/end indices with the exact window used by the analysis.
    if isinstance(analysis.get("velocity_profile"), dict):
        vp_meta = analysis["velocity_profile"]
        if vp_meta.get("onset_frame") is not None and vp_meta.get("offset_frame") is not None:
            try:
                start_idx = int(vp_meta["onset_frame"])
                end_idx = int(vp_meta["offset_frame"])
            except Exception:
                pass

    # Summary values from analysis dict (these are the numbers shown in the table)
    shoulder_elev_norm = _safe_float(analysis.get("shoulder_elevation_norm"))
    summary = {
        "nvp": _safe_float(analysis.get("nvp")),
        "straightness": _safe_float(analysis.get("straightness")),
        "pause_time_sec": _safe_float(analysis.get("pause_time_sec")),
        "number_of_stops": _safe_float(analysis.get("number_of_stops")),
        "trunk_ratio": _safe_float(analysis.get("trunk_ratio")),
        "shoulder_elevation_norm": shoulder_elev_norm,
        "shoulder_vert_norm": shoulder_elev_norm,
        "elbow_angle_mean_deg": _safe_float(analysis.get("elbow_angle_mean_deg")),
        "elbow_angle_range_deg": _safe_float(analysis.get("elbow_angle_range_deg")),
        "movement_time_sec": _safe_float(analysis.get("movement_time_sec")),
        "peak_velocity_px_s": _safe_float(analysis.get("peak_velocity_px_s")),
        "peak_velocity_cm_s": _safe_float(analysis.get("peak_velocity_cm_s")),
        "time_to_peak_velocity_sec": _safe_float(analysis.get("time_to_peak_velocity_sec")),
        "overall_straightness": _safe_float(analysis.get("straightness")),
    }

    # Physical scale metadata for on-screen transparency
    scale_method = str(analysis.get("table_scale_method") or "unknown")
    shoulder_width_cm = _safe_float(analysis.get("shoulder_width_cm"))
    cm_per_px = _safe_float(analysis.get("cm_per_px"))
    scale_ok = scale_method == "user_shoulder_width" and shoulder_width_cm and shoulder_width_cm > 0
    scale_note = (
        f"Scale: user shoulder width {shoulder_width_cm:.1f} cm"
        if scale_ok
        else (f"Scale: auto ({scale_method})" if scale_method not in ("unknown", "") else "Scale: not set")
    )

    use_cm_velocity = bool(summary["peak_velocity_cm_s"] and summary["peak_velocity_cm_s"] > 0)

    # Extract numeric metadata
    start_idx = int(analysis.get("movement_onset_frame", 0) or 0)
    end_idx = int(analysis.get("movement_offset_frame", len(df) - 1) or (len(df) - 1))
    start_idx = max(0, min(start_idx, len(df) - 1))
    end_idx = max(start_idx, min(end_idx, len(df) - 1))

    speed_peak = float(np.nanmax(speed)) if len(speed) else 0.0
    speed_threshold = 0.05 * speed_peak if speed_peak > 0 else 1.0

    # Shoulder width for scaling
    sw_px = None
    if "shoulder_width" in df.columns:
        sw = df["shoulder_width"].iloc[0]
        if pd.notna(sw) and float(sw) > 0:
            sw_px = float(sw)

    n_rows = len(df)

    out_w = orig_w + panel_width
    out_h = orig_h

    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        video_fps,
        (out_w, out_h),
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"Cannot create video writer: {output_path}")

    # Trajectory overlay on video
    traj_points: list[tuple[float, float]] = []

    # Prepare raw MediaPipe skeleton data once (most faithful to detector)
    raw_pose_csv = None
    if landmarks_csv and Path(landmarks_csv).name.endswith("_raw_pose.csv"):
        raw_pose_csv = landmarks_csv
    elif analysis.get("intermediate_files", {}).get("raw_pose_csv"):
        raw_pose_csv = analysis["intermediate_files"]["raw_pose_csv"]
    else:
        candidate = Path(landmarks_csv).with_name(Path(landmarks_csv).name.replace(".csv", "_raw_pose.csv"))
        if candidate.exists():
            raw_pose_csv = str(candidate)

    raw_df = None
    if raw_pose_csv and Path(raw_pose_csv).exists():
        try:
            raw_df = pd.read_csv(raw_pose_csv)
            if "LEFT_SHOULDER_X" in raw_df.columns or "left_shoulder_x" in raw_df.columns:
                raw_df = _normalize_landmark_columns(raw_df)
                if rotation != 0:
                    raw_df = _rotate_raw_landmarks(raw_df, rotation, native_w, native_h)
        except Exception as exc:
            print(f"Could not prepare raw skeleton: {exc}")

    active_side = str(
        analysis.get("affected_side")
        or analysis.get("side_analyzed")
        or analysis.get("active_landmark_side")
        or "right"
    ).lower()

    speed_peak = float(np.nanmax(speed)) if len(speed) else 0.0
    speed_threshold = 0.05 * speed_peak if speed_peak > 0 else 1.0

    for frame_i in range(n_frames_video):
        ret, frame = cap.read()
        if not ret:
            break

        # Rotate each frame with OpenCV so phone/tablet footage displays upright.
        if rotation == 90:
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270:
            frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Upscale to 4K rendering resolution
        if scale != 1.0:
            frame = cv2.resize(frame, (orig_w, orig_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            frame = cv2.resize(frame, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)

        # Map video frame to dataframe row
        row_idx = min(frame_i, n_rows - 1)
        row = df.iloc[row_idx]

        canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
        canvas[:, :orig_w] = frame

        # Compute straightness series once
        straightness = _compute_straightness_series(
            df["palm_x"].astype(float).values,
            df["palm_y"].astype(float).values,
        )

        # Render high-quality anti-aliased metrics panel using Pillow
        panel_img = _draw_panel_pil(
            panel_width, out_h, analysis, df,
            frame_i, n_frames_video,
            speed, elbow_angle, straightness, summary,
            scale_note, scale_ok, use_cm_velocity,
        )
        canvas[:, orig_w:] = panel_img

        # Skeleton overlay from raw MediaPipe landmarks (most faithful to detector)
        if raw_df is not None:
            trunk_xy = None
            if "trunk_x" in df.columns and "trunk_y" in df.columns:
                trunk_xy = np.column_stack([
                    df["trunk_x"].astype(float).values * scale,
                    df["trunk_y"].astype(float).values * scale,
                ])
            _draw_mediapipe_skeleton(
                canvas, raw_df, row_idx,
                orig_w, orig_h,
                active_side=active_side,
                trunk_xy=trunk_xy,
            )

        # Landmark-aware metric labels (Pillow anti-aliased)
        def _landmark_pt(col_x: str, col_y: str) -> Optional[Tuple[int, int]]:
            if col_x not in row.index or col_y not in row.index:
                return None
            x = float(row[col_x]) * scale
            y = float(row[col_y]) * scale
            if not (np.isfinite(x) and np.isfinite(y)):
                return None
            return int(x), int(y)

        sh_pt = _landmark_pt("shoulder_x", "shoulder_y")
        el_pt = _landmark_pt("elbow_x", "elbow_y")
        wr_pt = _landmark_pt("wrist_x", "wrist_y")
        tr_pt = _landmark_pt("trunk_x", "trunk_y")

        cur_speed = speed[row_idx] if row_idx < len(speed) else 0.0
        cur_elbow = elbow_angle[row_idx] if row_idx < len(elbow_angle) else float("nan")

        if sh_pt:
            _draw_label_near_pil(canvas, sh_pt, f"Elev {summary['shoulder_elevation_norm']:.2f} SW", (255, 180, 100), offset=(_s(-10), _s(-14)), orig_w=orig_w, orig_h=orig_h)
        if el_pt:
            _draw_label_near_pil(canvas, el_pt, f"Elbow {cur_elbow:.0f} deg", (150, 255, 150), offset=(_s(12), _s(10)), orig_w=orig_w, orig_h=orig_h)
        if wr_pt:
            spd_text = f"{cur_speed:.0f} px/s"
            if use_cm_velocity and cm_per_px and cm_per_px > 0:
                spd_text = f"{cur_speed * cm_per_px:.0f} cm/s"
            _draw_label_near_pil(canvas, wr_pt, spd_text, (100, 200, 255), offset=(_s(12), _s(20)), orig_w=orig_w, orig_h=orig_h)
            # Use the official table straightness so the on-screen label matches the results table.
            _draw_label_near_pil(canvas, wr_pt, f"Str {summary['straightness']:.2f}", (252, 211, 77), offset=(_s(12), _s(36)), orig_w=orig_w, orig_h=orig_h)

        # Straightness trajectory overlay
        _draw_straightness_trajectory(
            canvas,
            df["palm_x"].astype(float).values * scale,
            df["palm_y"].astype(float).values * scale,
            row_idx,
            start_idx,
            end_idx,
            color=(252, 211, 77),
        )
        if tr_pt:
            _draw_label_near_pil(canvas, tr_pt, f"Trunk {summary['trunk_ratio'] * 100:.1f}%", (255, 180, 100), offset=(_s(12), _s(-14)), orig_w=orig_w, orig_h=orig_h)

        # Pause overlay (only during the movement window)
        if start_idx <= row_idx <= end_idx and cur_speed < speed_threshold:
            _draw_pause_overlay_pil(canvas, orig_w)

        writer.write(canvas)

    cap.release()
    writer.release()

    # Re-encode to H.264 so browsers can play the MP4 (OpenCV mp4v is not
    # browser-compatible).  Keep the original as fallback if ffmpeg fails.
    h264_ok = False
    try:
        tmp_h264 = output_path.with_suffix(".h264.mp4")
        if _reencode_to_h264(output_path, tmp_h264):
            tmp_h264.replace(output_path)
            h264_ok = True
    except Exception as exc:
        print(f"H.264 post-processing via ffmpeg failed: {exc}")

    if not h264_ok:
        print("WARNING: validation video was saved in OpenCV mp4v format and may not play in browsers.")

    return {"path": str(output_path), "summary": summary}


if __name__ == "__main__":
    # Stand-alone test entry point
    import json
    import sys

    if len(sys.argv) < 4:
        print("Usage: python unified_validation_renderer.py <video.mp4> <analysis.json> <output.mp4> [landmarks.csv]")
        sys.exit(1)

    with open(sys.argv[2], "r", encoding="utf-8") as f:
        analysis_data = json.load(f)
    landmarks = sys.argv[4] if len(sys.argv) > 4 else None
    out = render_unified_validation_video(sys.argv[1], sys.argv[3], analysis_data, landmarks)
    print(f"Saved: {out.get('path') if isinstance(out, dict) else out}")
