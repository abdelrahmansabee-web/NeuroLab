# -*- coding: utf-8 -*-
"""Hand Landmarker must follow the moving pose wrist, not a table leftover."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOTS = [
    Path(__file__).resolve().parent,
    Path("/tmp/hf-compare/hf-space"),
]
for root in ROOTS:
    if (root / "hl_overlay_resample.py").is_file():
        sys.path.insert(0, str(root))
        break

from hl_overlay_resample import (  # noqa: E402
    MAX_HL_POSE_WRIST,
    helper_near_wrist,
    hl_close_to_pose_wrist,
    one_euro_xy,
    resample_with_max_gap,
    smooth_xy_series,
    wrist_roi_box,
)


class WristRoiTests(unittest.TestCase):
    def test_stuck_table_index_stays_out_of_crop(self):
        fw = fh = 1000
        wx, wy = 0.45, 0.32
        ix, iy = 0.55, 0.62
        x0, y0, cw, ch = wrist_roi_box(wx, wy, ix, iy, fw, fh)
        self.assertFalse(helper_near_wrist(wx, wy, ix, iy))
        table_x, table_y = int(ix * fw), int(iy * fh)
        inside = x0 <= table_x < x0 + cw and y0 <= table_y < y0 + ch
        self.assertFalse(inside)
        wrist_x, wrist_y = int(wx * fw), int(wy * fh)
        self.assertTrue(x0 <= wrist_x < x0 + cw and y0 <= wrist_y < y0 + ch)

    def test_nearby_index_stays_in_crop(self):
        fw = fh = 1000
        wx, wy = 0.50, 0.58
        ix, iy = 0.54, 0.52
        x0, y0, cw, ch = wrist_roi_box(wx, wy, ix, iy, fw, fh)
        self.assertTrue(helper_near_wrist(wx, wy, ix, iy))
        self.assertTrue(x0 <= int(ix * fw) < x0 + cw)
        self.assertTrue(y0 <= int(iy * fh) < y0 + ch)

    def test_raised_wrist_crop_is_not_most_of_the_frame(self):
        fw = fh = 1000
        x0, y0, cw, ch = wrist_roi_box(0.45, 0.28, 0.55, 0.62, fw, fh)
        self.assertLess(cw * ch, 0.18 * fw * fh)
        self.assertLess(ch, 0.40 * fh)

    def test_drink_fingertips_stay_in_distal_crop(self):
        fw = fh = 1000
        wx, wy = 0.45, 0.32
        ex, ey = 0.40, 0.50
        tip_x, tip_y = 0.52, 0.18
        table_x, table_y = 0.55, 0.62
        x0, y0, cw, ch = wrist_roi_box(
            wx, wy, 0.55, 0.62, fw, fh, ex=ex, ey=ey,
        )
        self.assertTrue(x0 <= int(wx * fw) < x0 + cw)
        self.assertTrue(y0 <= int(wy * fh) < y0 + ch)
        self.assertTrue(x0 <= int(tip_x * fw) < x0 + cw)
        self.assertTrue(y0 <= int(tip_y * fh) < y0 + ch)
        inside_table = x0 <= int(table_x * fw) < x0 + cw and y0 <= int(table_y * fh) < y0 + ch
        self.assertFalse(inside_table)


class SmoothSeriesTests(unittest.TestCase):
    def test_small_jitter_is_damped(self):
        xs = np.array([0.50, 0.53, 0.50, 0.53, 0.50])
        ys = np.array([0.40, 0.40, 0.40, 0.40, 0.40])
        ox, oy = smooth_xy_series(xs, ys, alpha=0.36, max_jump=0.055)
        raw_span = float(np.nanmax(xs) - np.nanmin(xs))
        sm_span = float(np.nanmax(ox) - np.nanmin(ox))
        self.assertLess(sm_span, raw_span)

    def test_teleport_is_not_blended(self):
        xs = np.array([0.50, 0.50, 0.20, 0.20])
        ys = np.array([0.60, 0.60, 0.30, 0.30])
        ox, oy = smooth_xy_series(xs, ys, alpha=0.36, max_jump=0.055)
        self.assertAlmostEqual(float(ox[2]), 0.20, places=5)
        self.assertAlmostEqual(float(oy[2]), 0.30, places=5)


class OneEuroTests(unittest.TestCase):
    def test_high_freq_jitter_is_damped(self):
        t = np.linspace(0.0, 1.0, 61)
        xs = 0.50 + 0.02 * np.sin(2.0 * np.pi * 12.0 * t)
        ys = np.full_like(xs, 0.40)
        ox, _ = one_euro_xy(xs, ys, fs=60.0)
        self.assertLess(float(np.nanstd(ox)), float(np.nanstd(xs)))

    def test_follows_a_ramp_closer_than_heavy_ema(self):
        true = 0.40 + np.linspace(0.0, 0.08, 50)
        xs = true.copy()
        ys = np.full(len(xs), 0.50, dtype=float)
        euro_x, _ = one_euro_xy(xs, ys, fs=60.0)
        ema_x, _ = smooth_xy_series(xs, ys, alpha=0.36)
        euro_err = float(np.nanmean(np.abs(euro_x[5:] - true[5:])))
        ema_err = float(np.nanmean(np.abs(ema_x[5:] - true[5:])))
        self.assertLess(euro_err, ema_err)

    def test_teleport_is_not_blended(self):
        xs = np.array([0.50, 0.50, 0.20, 0.20])
        ys = np.array([0.60, 0.60, 0.30, 0.30])
        ox, oy = one_euro_xy(xs, ys, fs=60.0, max_jump=0.07)
        self.assertAlmostEqual(float(ox[2]), 0.20, places=5)
        self.assertAlmostEqual(float(oy[2]), 0.30, places=5)


class ResampleGapTests(unittest.TestCase):
    def test_table_rest_to_table_return_does_not_fill_the_lift(self):
        old_t = np.array([0.0, 1.0, 2.0, 8.0, 9.0])
        y = np.array([0.60, 0.60, 0.61, 0.60, 0.60])
        new_t = np.linspace(0.0, 9.0, 19)
        out = resample_with_max_gap(y, old_t, new_t, max_gap_sec=0.25)
        mid = out[(new_t > 3.0) & (new_t < 7.0)]
        self.assertTrue(np.all(np.isnan(mid)))
        self.assertTrue(np.isfinite(out[0]))
        self.assertTrue(np.isfinite(out[-1]))

    def test_short_gap_is_interpolated(self):
        old_t = np.array([0.0, 0.10, 0.30])
        y = np.array([0.2, np.nan, 0.4])
        # caller already dropped NaN rows; mimic finite samples only
        old_t = np.array([0.0, 0.30])
        y = np.array([0.2, 0.4])
        new_t = np.array([0.0, 0.15, 0.30])
        out = resample_with_max_gap(y, old_t, new_t, max_gap_sec=0.40)
        self.assertAlmostEqual(float(out[1]), 0.3, places=5)


class PoseWristLockTests(unittest.TestCase):
    def test_table_hl_is_not_on_the_lifted_pose_wrist(self):
        self.assertFalse(
            hl_close_to_pose_wrist(0.55, 0.62, 0.45, 0.32, MAX_HL_POSE_WRIST)
        )
        self.assertTrue(
            hl_close_to_pose_wrist(0.46, 0.33, 0.45, 0.32, MAX_HL_POSE_WRIST)
        )


if __name__ == "__main__":
    unittest.main()
