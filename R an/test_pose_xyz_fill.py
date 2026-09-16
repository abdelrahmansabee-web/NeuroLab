# -*- coding: utf-8 -*-
"""PRE rest: keep XYZ fill for Analyze; keep visibility so overlay can hide the arm."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pose_xyz_fill import fill_landmark_xyz_keep_visibility, overlay_hide_unseen


def test_xyz_still_fills_for_analysis():
    n = 30
    df = pd.DataFrame({
        "frame": np.arange(n),
        "time": np.arange(n) / 30.0,
        "RIGHT_WRIST_X": np.concatenate([np.full(20, np.nan), np.linspace(0.4, 0.6, 10)]),
        "RIGHT_WRIST_Y": np.concatenate([np.full(20, np.nan), np.linspace(0.7, 0.3, 10)]),
        "RIGHT_WRIST_Z": np.concatenate([np.full(20, np.nan), np.zeros(10)]),
        "RIGHT_WRIST_VISIBILITY": np.concatenate([np.full(20, 0.05), np.full(10, 0.9)]),
    })
    out = fill_landmark_xyz_keep_visibility(df, max_gap=8)
    assert np.isfinite(out.loc[:19, "RIGHT_WRIST_X"]).all()
    assert np.isfinite(out.loc[20:, "RIGHT_WRIST_X"]).all()


def test_visibility_stays_measured_on_rest():
    n = 30
    vis = np.concatenate([np.full(20, 0.05), np.full(10, 0.9)])
    df = pd.DataFrame({
        "frame": np.arange(n),
        "time": np.arange(n) / 30.0,
        "RIGHT_WRIST_X": np.concatenate([np.full(20, np.nan), np.linspace(0.4, 0.6, 10)]),
        "RIGHT_WRIST_Y": np.concatenate([np.full(20, np.nan), np.linspace(0.7, 0.3, 10)]),
        "RIGHT_WRIST_Z": np.zeros(n),
        "RIGHT_WRIST_VISIBILITY": vis,
    })
    out = fill_landmark_xyz_keep_visibility(df, max_gap=8)
    assert np.allclose(out["RIGHT_WRIST_VISIBILITY"], vis)


def test_overlay_hides_unseen_copied_reach():
    x = np.array([0.55, 0.56, 0.57, 0.58])
    y = np.array([0.40, 0.41, 0.42, 0.30])
    vis = np.array([0.05, 0.05, 0.08, 0.92])
    ox, oy = overlay_hide_unseen(x, y, vis)
    assert np.isnan(ox[:3]).all() and np.isnan(oy[:3]).all()
    assert np.isclose(ox[3], 0.58) and np.isclose(oy[3], 0.30)


def test_post_like_visible_rest_still_draws():
    x = np.array([0.20, 0.21, 0.40])
    y = np.array([0.70, 0.70, 0.40])
    vis = np.array([0.88, 0.90, 0.93])
    ox, oy = overlay_hide_unseen(x, y, vis)
    assert np.isfinite(ox).all() and np.isfinite(oy).all()
