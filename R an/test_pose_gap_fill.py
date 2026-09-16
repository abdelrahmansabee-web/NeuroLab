# -*- coding: utf-8 -*-
"""PRE rest must not inherit the first reach pose."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pose_gap_fill import interpolate_interior_gaps, interpolate_landmarks_df
from landmark_tracker_enhance import _interpolate_landmark_gaps, apply_one_euro_series


def test_leading_rest_stays_empty():
    y = np.full(120, np.nan)
    y[90:] = 0.42
    vis = np.zeros(120)
    vis[90:] = 0.9
    out = interpolate_interior_gaps(y, visibility=vis, max_gap=10)
    assert np.isnan(out[:90]).all()
    assert np.allclose(out[90:], 0.42)


def test_short_interior_gap_fills():
    y = np.array([0.1, np.nan, np.nan, 0.4])
    out = interpolate_interior_gaps(y, max_gap=4)
    assert np.allclose(out, [0.1, 0.2, 0.3, 0.4])


def test_long_interior_gap_stays_empty():
    y = np.array([0.1, np.nan, np.nan, np.nan, 0.5])
    out = interpolate_interior_gaps(y, max_gap=2)
    assert out[0] == 0.1
    assert np.isnan(out[1:4]).all()
    assert out[4] == 0.5


def test_extract_does_not_bfill_reach_onto_rest():
    n = 30
    df = pd.DataFrame({
        "frame": np.arange(n),
        "time": np.arange(n) / 30.0,
        "RIGHT_WRIST_X": np.concatenate([np.full(20, np.nan), np.linspace(0.4, 0.6, 10)]),
        "RIGHT_WRIST_Y": np.concatenate([np.full(20, np.nan), np.linspace(0.7, 0.3, 10)]),
        "RIGHT_WRIST_Z": np.concatenate([np.full(20, np.nan), np.zeros(10)]),
        "RIGHT_WRIST_VISIBILITY": np.concatenate([np.full(20, 0.05), np.full(10, 0.9)]),
    })
    out = interpolate_landmarks_df(df.copy(), max_gap=8)
    assert np.isnan(out.loc[:19, "RIGHT_WRIST_X"]).all()
    assert np.isnan(out.loc[:19, "RIGHT_WRIST_Y"]).all()
    assert np.allclose(out.loc[20:, "RIGHT_WRIST_X"], df.loc[20:, "RIGHT_WRIST_X"])
    assert np.allclose(out.loc[:19, "RIGHT_WRIST_VISIBILITY"], 0.05)


def test_one_euro_does_not_smear_reach_into_rest():
    v = np.full(20, np.nan)
    v[12:] = 0.5
    t = np.arange(20) / 30.0
    out = apply_one_euro_series(v, t)
    assert np.isnan(out[:12]).all()
    assert np.isfinite(out[12:]).all()


def test_landmark_gap_helper_matches_interior_fill():
    y = np.array([np.nan, np.nan, 0.2, np.nan, 0.4, np.nan])
    vis = np.array([0.0, 0.0, 0.9, 0.9, 0.9, 0.1])
    out = _interpolate_landmark_gaps(y, vis, max_gap=4)
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert np.isclose(out[3], 0.3)
    assert np.isnan(out[5])
