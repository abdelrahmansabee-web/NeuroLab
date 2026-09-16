# -*- coding: utf-8 -*-
"""Fill only short interior landmark gaps.

Copying the first confident pose backward paints a later reach onto PRE rest
(hands in the lap, low visibility). POST/healthy rest is usually visible, so
the same fill is invisible there.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


def interpolate_interior_gaps(
    series,
    visibility=None,
    max_gap: int = 10,
    vis_threshold: float = 0.22,
) -> np.ndarray:
    """Linear-fill NaN runs of at most ``max_gap`` frames between two real samples.

    Leading and trailing rest stay NaN. Long dropouts stay NaN.
    """
    arr = np.asarray(series, dtype=float).copy()
    if visibility is not None:
        vis = np.asarray(visibility, dtype=float)
        arr[vis < vis_threshold] = np.nan
    n = len(arr)
    if n == 0:
        return arr
    i = 0
    while i < n:
        if np.isfinite(arr[i]):
            i += 1
            continue
        j = i
        while j < n and not np.isfinite(arr[j]):
            j += 1
        if j - i <= max_gap and i > 0 and j < n:
            arr[i:j] = np.linspace(arr[i - 1], arr[j], j - i + 2)[1:-1]
        i = j
    return arr


def interpolate_landmarks_df(df, max_gap: int = 8):
    """Short interior XYZ gaps only. Visibility is not filled. No bfill/ffill."""
    import pandas as pd

    out = df.copy()
    numeric_cols = [c for c in out.columns if c not in ("frame", "time")]
    for col in numeric_cols:
        if "_VISIBILITY" not in col:
            continue
        vis_col = col
        base = col.replace("_VISIBILITY", "")
        xyz = [f"{base}_X", f"{base}_Y", f"{base}_Z"]
        present = [c for c in xyz if c in out.columns]
        if not present:
            continue
        low_vis = pd.to_numeric(out[vis_col], errors="coerce") < 0.25
        out.loc[low_vis, present] = np.nan
    xyz_cols = [c for c in numeric_cols if "_VISIBILITY" not in c]
    if xyz_cols:
        out[xyz_cols] = out[xyz_cols].interpolate(
            method="linear", limit=max_gap, limit_area="inside",
        )
    return out
