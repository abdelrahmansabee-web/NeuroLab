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

# IMAGE-mode HL jitters every frame; blend toward the new point but snap on a teleport.
HL_SMOOTH_ALPHA = 0.36
HL_SMOOTH_MAX_JUMP = 0.055


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
    ex: float = float("nan"),
    ey: float = float("nan"),
    *,
    pad: float = 1.7,
    min_frac: float = 0.13,
    max_frac: float = 0.34,
    distal_shift_frac: float = 0.09,
) -> Tuple[int, int, int, int]:
    """Pixel box around the pose hand.

    Stuck table INDEX cannot enlarge it. Shift the box along elbow→wrist so
    fingertips at the mouth stay inside instead of collapsing toward the wrist.
    """
    pts_x = [float(wx) * fw]
    pts_y = [float(wy) * fh]
    for hx, hy in ((ix, iy), (tx, ty)):
        if helper_near_wrist(wx, wy, hx, hy):
            pts_x.append(float(hx) * fw)
            pts_y.append(float(hy) * fh)
    cx = float(np.mean(pts_x))
    cy = float(np.mean(pts_y))
    if all(np.isfinite(v) for v in (ex, ey, wx, wy)):
        dx = float(wx) - float(ex)
        dy = float(wy) - float(ey)
        n = float(np.hypot(dx, dy))
        if n > 1e-5:
            shift = distal_shift_frac * min(fw, fh)
            cx += (dx / n) * shift
            cy += (dy / n) * shift
    span = max(abs(px - cx) for px in pts_x)
    span = max(span, max(abs(py - cy) for py in pts_y), min_frac * min(fw, fh), 72.0)
    span *= pad
    span = min(span, max_frac * min(fw, fh))
    x0 = int(max(0, round(cx - span * 0.5)))
    y0 = int(max(0, round(cy - span * 0.5)))
    x1 = int(min(fw, round(cx + span * 0.5)))
    y1 = int(min(fh, round(cy + span * 0.5)))
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def smooth_xy_series(
    xs: np.ndarray,
    ys: np.ndarray,
    *,
    alpha: float = HL_SMOOTH_ALPHA,
    max_jump: float = HL_SMOOTH_MAX_JUMP,
) -> Tuple[np.ndarray, np.ndarray]:
    """EMA in image space; snap if the point teleports (hand switch / lost lock)."""
    xs = np.asarray(xs, dtype=float).copy()
    ys = np.asarray(ys, dtype=float).copy()
    n = min(len(xs), len(ys))
    out_x = np.full(n, np.nan)
    out_y = np.full(n, np.nan)
    prev_x = np.nan
    prev_y = np.nan
    a = float(np.clip(alpha, 0.0, 1.0))
    jump = float(max_jump)
    for i in range(n):
        x = float(xs[i]) if np.isfinite(xs[i]) else np.nan
        y = float(ys[i]) if np.isfinite(ys[i]) else np.nan
        if not (np.isfinite(x) and np.isfinite(y)):
            prev_x = np.nan
            prev_y = np.nan
            continue
        if np.isfinite(prev_x) and np.isfinite(prev_y):
            dist = float(np.hypot(x - prev_x, y - prev_y))
            if dist <= jump:
                x = a * x + (1.0 - a) * prev_x
                y = a * y + (1.0 - a) * prev_y
        out_x[i] = x
        out_y[i] = y
        prev_x, prev_y = x, y
    return out_x, out_y
