# -*- coding: utf-8 -*-
"""Fill XYZ for kinematics; leave measured visibility alone.

Analysis needs the old XYZ bfill so PRE Analyze still runs. Overlay uses
visibility to hide a copied reach during unseen lap rest.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fill_landmark_xyz_keep_visibility(df: pd.DataFrame, max_gap: int = 8) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = [c for c in out.columns if c not in ("frame", "time")]
    for col in numeric_cols:
        if "_VISIBILITY" not in col:
            continue
        base = col.replace("_VISIBILITY", "")
        present = [c for c in (f"{base}_X", f"{base}_Y", f"{base}_Z") if c in out.columns]
        if not present:
            continue
        low_vis = pd.to_numeric(out[col], errors="coerce") < 0.25
        out.loc[low_vis, present] = np.nan
    xyz_cols = [c for c in numeric_cols if "_VISIBILITY" not in c]
    if xyz_cols:
        out[xyz_cols] = out[xyz_cols].interpolate(
            method="linear", limit=max_gap, limit_direction="both",
        )
        out[xyz_cols] = out[xyz_cols].ffill().bfill()
    return out


def overlay_hide_unseen(x, y, vis, threshold: float = 0.5):
    """Null overlay joints the camera did not actually see."""
    xs = np.asarray(x, dtype=float).copy()
    ys = np.asarray(y, dtype=float).copy()
    v = np.asarray(vis, dtype=float)
    v = np.where(np.isfinite(v), v, 0.0)
    hide = v < float(threshold)
    xs[hide] = np.nan
    ys[hide] = np.nan
    return xs, ys


def resample_visibility(vis, old_t, new_t):
    """Resample visibility without copying a later reach onto unseen rest.

    np.interp on only-finite samples holds the first confident vis backward
    across NaN rest frames. Treat missing vis as 0 (unseen) first.
    """
    y = np.asarray(vis, dtype=float).reshape(-1)
    t = np.asarray(old_t, dtype=float).reshape(-1)
    nt = np.asarray(new_t, dtype=float).reshape(-1)
    y = np.where(np.isfinite(y), y, 0.0)
    if nt.size == 0:
        return np.zeros(0, dtype=float)
    if t.size == 0 or y.size == 0:
        return np.zeros(nt.size, dtype=float)
    n = min(t.size, y.size)
    t = t[:n]
    y = y[:n]
    if n == 1:
        return np.full(nt.size, y[0], dtype=float)
    return np.interp(nt, t, y)


def overlay_blank_unseen_wrist(wrist_x, wrist_y, *arrays):
    """Drop palm/fingers/HL when the pose wrist is unseen.

    Index and Hand Landmarker can still carry a copied reach after the wrist
    was hidden. POST rest keeps a visible wrist, so those arrays stay.
    """
    unseen = ~np.isfinite(np.asarray(wrist_x, dtype=float)) | ~np.isfinite(
        np.asarray(wrist_y, dtype=float)
    )
    out = []
    for a in arrays:
        b = np.asarray(a, dtype=float).copy()
        if b.shape[:1] == unseen.shape:
            b[unseen] = np.nan
        out.append(b)
    return out
