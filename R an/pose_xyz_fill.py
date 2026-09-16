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
