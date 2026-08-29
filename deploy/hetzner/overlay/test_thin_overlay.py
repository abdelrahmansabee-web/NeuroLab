#!/usr/bin/env python3
from __future__ import annotations

import unittest

from thin_overlay import thin_overlay_payload


class ThinOverlayTests(unittest.TestCase):
    def test_short_payload_unchanged(self) -> None:
        data = {"frames": [{"t": 1}, {"t": 2}], "fps": 60}
        self.assertEqual(thin_overlay_payload(data, max_frames=360)["frames"], data["frames"])

    def test_long_payload_strided(self) -> None:
        data = {
            "frames": [{"i": i} for i in range(1200)],
            "velocity_profile": {"t": list(range(1200)), "v": list(range(1200))},
        }
        out = thin_overlay_payload(data, max_frames=360)
        self.assertLessEqual(len(out["frames"]), 360)
        self.assertGreaterEqual(out["overlay_frame_stride"], 2)
        self.assertEqual(out["overlay_frames_full"], 1200)
        self.assertEqual(len(out["velocity_profile"]["t"]), len(out["frames"]))


if __name__ == "__main__":
    unittest.main()
