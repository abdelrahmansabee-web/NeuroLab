# -*- coding: utf-8 -*-
"""
Table calibration for reach-wipe kinematics.

Physical table width = 60 cm (reference). Converts pixel displacements to cm via:
  cm_per_px = TABLE_WIDTH_CM / table_width_px
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

TABLE_WIDTH_CM = 60.0
SHOULDER_WIDTH_CM = 40.0  # last-resort scale when table cannot be estimated

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None


class TableCalibrator:
    """Detect blue table surface in a video frame (HSV) and derive cm/px scale."""

    def __init__(self, real_width_cm: float = TABLE_WIDTH_CM):
        self.real_width_cm = real_width_cm
        self.scale_cm_per_px: Optional[float] = None
        self.table_width_px: Optional[float] = None

    def detect(self, frame: np.ndarray) -> bool:
        if cv2 is None:
            return False
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([90, 40, 40])
        upper = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return False

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.03
        frame_max = float(max(w, h))

        candidates = []
        for cnt in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if bw > w * 0.85 or bh > h * 0.85:
                continue
            if float(max(bw, bh)) > frame_max * 0.65:
                continue
            if bw < 40 and bh < 40:
                continue
            candidates.append((area, bw, bh, x, y))

        if not candidates:
            return False

        def score(item):
            area, bw, bh, x, y = item
            cy = y + bh / 2.0
            wide_bonus = bw / max(bh, 1)
            lower_bonus = cy / max(h, 1)
            return area * (1.0 + 0.35 * wide_bonus + 0.25 * lower_bonus)

        _, bw, bh, _, _ = max(candidates, key=score)
        self.table_width_px = float(max(bw, bh))
        self.scale_cm_per_px = self.real_width_cm / self.table_width_px
        return True

    def get_scale(self) -> Optional[float]:
        return self.scale_cm_per_px

    def get_table_width_px(self) -> Optional[float]:
        return self.table_width_px


def find_video_for_csv(csv_path: str, explicit_video: Optional[str] = None) -> Optional[Path]:
    if explicit_video:
        p = Path(explicit_video)
        if p.is_file():
            return p
    csv_p = Path(csv_path)
    stem = csv_p.stem.replace("_landmarks", "")
    stem_clean = stem.replace("_pre", "").replace("_post", "").replace("_baseline", "")
    for candidate in (
        csv_p.with_suffix(".mp4"),
        csv_p.parent / f"{stem}.mp4",
        csv_p.parent / f"{stem_clean}.mp4",
    ):
        if candidate.is_file():
            return candidate
    return None


def _calibrate_from_video(video_path: Path) -> Optional[Tuple[float, float]]:
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    indices = sorted({0, n // 4, n // 2, (3 * n) // 4, max(n - 1, 0)})
    cal = TableCalibrator(TABLE_WIDTH_CM)
    best: Optional[Tuple[float, float]] = None
    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        if cal.detect(frame):
            tw = cal.get_table_width_px()
            sc = cal.get_scale()
            if tw and sc:
                best = (float(tw), float(sc))
    cap.release()
    return best


def detect_table_surface_y(
    video_path: Path,
    start_idx: int = 0,
    end_idx: Optional[int] = None,
) -> Optional[float]:
    """
    Detect table surface as the lowest strong horizontal line in the video.
    Returns normalized y in [0, 1] (0 = top, 1 = bottom), or None if not found.
    Does not rely on color or table shape — only on the horizontal edge.
    """
    if cv2 is None:
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    last_idx = max(n - 1, 0)
    if end_idx is None or end_idx > last_idx:
        end_idx = last_idx
    if start_idx > end_idx:
        start_idx = 0
    indices = sorted({start_idx, (start_idx + end_idx) // 2, end_idx})

    best_y: Optional[float] = None
    best_score = -1.0

    for i in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=max(50, int(w * 0.08)),
            minLineLength=int(w * 0.25),
            maxLineGap=int(w * 0.05),
        )
        if lines is None:
            continue
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            if dx < w * 0.25:
                continue
            # Nearly horizontal
            if dy > dx * 0.12:
                continue
            y = (y1 + y2) / 2.0
            # Ignore lines in the upper half (likely shoulders/wall)
            if y < h * 0.45:
                continue
            # Score: longer lines lower in the frame are preferred
            score = dx * (1.0 + 0.5 * (y / h))
            if score > best_score:
                best_score = score
                best_y = y / h

    cap.release()
    return best_y


def estimate_table_width_px_from_wipe(
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    *,
    min_span_px: float = 120.0,
) -> Optional[float]:
    """
    Reach-wipe: lateral palm span during the trial approximates table width (60 cm).
    Uses robust peak-to-peak on palm_x (dominant wipe axis in frontal/oblique views).
    """
    px = np.asarray(palm_x, dtype=float)
    if len(px) < 10:
        return None
    span = float(np.nanmax(px) - np.nanmin(px))
    if not np.isfinite(span) or span < min_span_px:
        return None
    return span


def calibrate_table_scale(
    csv_path: str,
    palm_x: np.ndarray,
    palm_y: np.ndarray,
    shoulder_width_px: Optional[float] = None,
    *,
    video_path: Optional[str] = None,
    reach_only: bool = True,
) -> Dict[str, object]:
    """
    Return cm/px scale anchored to 60 cm table width.

    Priority:
      1. HSV blue-table detection on associated video (multi-frame)
      2. Lateral palm span during wipe (reach_wipe only — disabled when reach_only)
      3. Shoulder-width fallback (40 cm shoulder → cm/px only; table_width_px inferred)
    """
    method = "unknown"
    table_width_px: Optional[float] = None
    cm_per_px: Optional[float] = None

    vid = find_video_for_csv(csv_path, video_path)
    if vid is not None:
        from_video = _calibrate_from_video(vid)
        if from_video:
            table_width_px, cm_per_px = from_video
            method = "table_hsv_video"

    if cm_per_px is None and not reach_only:
        wipe_tw = estimate_table_width_px_from_wipe(palm_x, palm_y)
        if wipe_tw:
            table_width_px = wipe_tw
            cm_per_px = TABLE_WIDTH_CM / table_width_px
            method = "wipe_lateral_span"

    sw = float(shoulder_width_px) if shoulder_width_px and np.isfinite(shoulder_width_px) else float("nan")
    if cm_per_px is None and np.isfinite(sw) and sw > 20:
        cm_per_px = SHOULDER_WIDTH_CM / sw
        table_width_px = TABLE_WIDTH_CM / cm_per_px if cm_per_px > 0 else None
        method = "shoulder_width_fallback"

    return {
        "cm_per_px": cm_per_px,
        "table_width_px": table_width_px,
        "table_width_cm": TABLE_WIDTH_CM,
        "scale_method": method,
        "video_path": str(vid) if vid else None,
    }


def px_to_cm(displacement_px: float, cm_per_px: Optional[float]) -> float:
    if not (np.isfinite(displacement_px) and cm_per_px and cm_per_px > 0):
        return float("nan")
    return float(displacement_px * cm_per_px)
