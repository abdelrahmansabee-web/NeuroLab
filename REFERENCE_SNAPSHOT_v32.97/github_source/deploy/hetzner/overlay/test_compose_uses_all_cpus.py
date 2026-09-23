#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


class ComposeCpuTests(unittest.TestCase):
    def test_uses_all_host_threads_without_lowering_pose_quality(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        self.assertIn("OMP_NUM_THREADS: \"4\"", text)
        self.assertIn("TF_NUM_INTRAOP_THREADS: \"4\"", text)
        self.assertNotIn("NEUROLAB_FAST_ANALYZE", text)
        self.assertNotIn("NEUROLAB_POSE_MODEL", text)
        self.assertNotIn("NEUROLAB_SKIP_SKELETON", text)
        self.assertNotIn("NEUROLAB_HAND_STRIDE", text)


if __name__ == "__main__":
    unittest.main()
