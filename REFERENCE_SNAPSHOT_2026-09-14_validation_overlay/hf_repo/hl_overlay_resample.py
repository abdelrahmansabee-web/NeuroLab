# -*- coding: utf-8 -*-
"""HL overlay resampling that does not invent a hand across long dropouts.

``np.interp`` over all finite samples turns a lost-tracking gap (table rest →
table return) into a fake hand parked on the table for the whole lift.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


# Reject a Hand Landmarker wrist that is this far (normalized) from pose wrist.
MAX_HL_POSE_WRIST = 0.11


def resample_with_max_gap(
    y: np.ndarray,
    old_t: np.ndarray,
    new_t: np.ndarray,
    max_gap_sec: float,
) -> np.ndarray:
    """Linear interp only between samples closer than ``max_gap_sec``; else NaN."""
    y = np.asarray(y, dtype=float)
    old_t = np.asarray(old_t, dtype=float)
    new_t = np.asarray(new_t, dtype=float)
    out = np.full(len(new_t), np.nan)
    if len(y) == 0 or len(old_t) == 0 or len(new_t) == 0:
        return out
    mask = np.isfinite(y) & np.isfinite(old_t)
    if int(np.count_nonzero(mask)) == 0:
        return out
    ot = old_t[mask]
    oy = y[mask]
    order = np.argsort(ot)
    ot = ot[order]
    oy = oy[order]
    idx = np.searchsorted(ot, new_t)
    max_gap = float(max_gap_sec)
    for i, t in enumerate(new_t):
        j = int(idx[i])
        tt = float(t)
        if j <= 0:
            if abs(float(ot[0]) - tt) <= max_gap:
                out[i] = float(oy[0])
            continue
        if j >= len(ot):
            if abs(float(ot[-1]) - tt) <= max_gap:
                out[i] = float(oy[-1])
            continue
        t0 = float(ot[j - 1])
        t1 = float(ot[j])
        y0 = float(oy[j - 1])
        y1 = float(oy[j])
        left_ok = (tt - t0) <= max_gap
        right_ok = (t1 - tt) <= max_gap
        if left_ok and right_ok:
            if t1 == t0:
                out[i] = y1
            else:
                w = (tt - t0) / (t1 - t0)
                out[i] = y0 * (1.0 - w) + y1 * w
        elif left_ok:
            out[i] = y0
        elif right_ok:
            out[i] = y1
    return out


def hl_close_to_pose_wrist(
    hl_wx: float,
    hl_wy: float,
    pose_wx: float,
    pose_wy: float,
    max_dist: float = MAX_HL_POSE_WRIST,
) -> bool:
    if not all(np.isfinite(v) for v in (hl_wx, hl_wy, pose_wx, pose_wy)):
        return False
    return float(np.hypot(hl_wx - pose_wx, hl_wy - pose_wy)) <= float(max_dist)


def helper_near_wrist(
    wx: float,
    wy: float,
    hx: float,
    hy: float,
    max_dist: float = 0.14,
) -> bool:
    """Pose INDEX/THUMB may stay on the table after the wrist lifts — ignore them."""
    if not all(np.isfinite(v) for v in (wx, wy, hx, hy)):
        return False
    return float(np.hypot(hx - wx, hy - wy)) <= float(max_dist)


def wrist_roi_box(
    wx: float,
    wy: float,
    ix: float,
    iy: float,
    fw: int,
    fh: int,
    tx: float = float("nan"),
    ty: float = float("nan"),
    *,
    pad: float = 1.65,
    min_frac: float = 0.11,
    max_frac: float = 0.26,
) -> Tuple[int, int, int, int]:
    """Pixel box around the pose wrist. Stuck table INDEX cannot enlarge it."""
    pts_x = [float(wx) * fw]
    pts_y = [float(wy) * fh]
    for hx, hy in ((ix, iy), (tx, ty)):
        if helper_near_wrist(wx, wy, hx, hy):
            pts_x.append(float(hx) * fw)
            pts_y.append(float(hy) * fh)
    cx = float(np.mean(pts_x))
    cy = float(np.mean(pts_y))
    span = max(abs(px - cx) for px in pts_x)
    span = max(span, max(abs(py - cy) for py in pts_y), min_frac * min(fw, fh), 64.0)
    span *= pad
    span = min(span, max_frac * min(fw, fh))
    x0 = int(max(0, round(cx - span * 0.5)))
    y0 = int(max(0, round(cy - span * 0.5)))
    x1 = int(min(fw, round(cx + span * 0.5)))
    y1 = int(min(fh, round(cy + span * 0.5)))
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)
