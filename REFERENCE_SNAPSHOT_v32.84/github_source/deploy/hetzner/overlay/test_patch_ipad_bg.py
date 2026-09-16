#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_ipad_bg import FILTER_NEW, FILTER_OLD, patch_clinic_js


SAMPLE = (
    'style:{backgroundImage:"url(\'".concat("/bg.jpg","\')"),'
    'filter:"blur(24px) brightness(0.55) saturate(0.80)",transform:"scale(1.08)"},'
    'backdrop-filter: blur(8px) saturate(1.45),'
    'background:rgba(255,255,255,0.008)'
    'useState)("/bg.jpg")'
)


class IpadBgBakeTests(unittest.TestCase):
    def test_removes_live_photo_filter_keeps_glass(self) -> None:
        out, hits = patch_clinic_js(SAMPLE)
        self.assertGreater(hits, 0)
        self.assertNotIn(FILTER_OLD, out)
        self.assertIn(FILTER_NEW, out)
        self.assertIn("/bg_baked.jpg", out)
        self.assertIn("backdrop-filter: blur(8px) saturate(1.45)", out)
        self.assertIn("rgba(255,255,255,0.008)", out)

    def test_baked_asset_exists(self) -> None:
        img = Path(__file__).resolve().parent / "bg_baked.jpg"
        self.assertTrue(img.is_file())
        self.assertGreater(img.stat().st_size, 10_000)

    def test_pattern_exists_in_clinic_bundle(self) -> None:
        root = Path(__file__).resolve().parents[3]
        bundle = (
            root
            / "REFERENCE_SNAPSHOT_v31.75"
            / "hf_space"
            / "frontend"
            / "build"
            / "static"
            / "js"
            / "main.0626212c.js"
        )
        if not bundle.is_file():
            self.skipTest("clinic bundle snapshot missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        self.assertIn(FILTER_OLD, text)


if __name__ == "__main__":
    unittest.main()
