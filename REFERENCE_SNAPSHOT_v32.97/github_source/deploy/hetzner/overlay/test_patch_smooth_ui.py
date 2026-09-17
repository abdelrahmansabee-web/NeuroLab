#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_smooth_ui import patch_clinic_js, patch_smooth_ui


class PatchSmoothUiTests(unittest.TestCase):
    def test_copies_assets_and_wires_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                '<html><head><title>NeuroLab</title>'
                '<script defer="defer" src="/static/js/main.0626212c.js"></script>'
                "</head><body></body></html>",
                encoding="utf-8",
            )
            rc = patch_smooth_ui(root)
            self.assertEqual(rc, 0)
            css = (build / "clinic_smooth.css").read_text(encoding="utf-8")
            self.assertIn("backdrop-filter: none", css)
            self.assertNotIn("rgba(16, 22, 32, 0.94)", css)
            self.assertIn("rgba(24, 34, 48, 0.44)", css)
            self.assertIn("bg_soft.jpg", css)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn("clinic_smooth.css?v=6", html)
            self.assertIn("clinic_smooth.js?v=6", html)
            self.assertIn("nl-clinic-smooth", html)
            self.assertIn("main.0626212c.js?v=6", html)
            self.assertTrue((build / "bg_soft.jpg").is_file())
            self.assertTrue((build / "clinic_smooth.js").is_file())

    def test_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                "<html><head><title>NeuroLab</title></head><body></body></html>",
                encoding="utf-8",
            )
            self.assertEqual(patch_smooth_ui(root), 0)
            self.assertEqual(patch_smooth_ui(root), 0)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertEqual(html.count("clinic_smooth.css"), 1)
            self.assertEqual(html.count("clinic_smooth.js"), 1)

    def test_bumps_cached_asset_query(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                '<html><head><link rel="stylesheet" href="/clinic_smooth.css?v=2"/>'
                '<script src="/clinic_smooth.js?v=1"></script></head></html>',
                encoding="utf-8",
            )
            self.assertEqual(patch_smooth_ui(root), 0)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn("clinic_smooth.css?v=6", html)
            self.assertIn("clinic_smooth.js?v=6", html)
            self.assertNotIn("?v=5", html)

    def test_strips_live_blur_from_bundle(self) -> None:
        sample = (
            'backgroundImage:"url(\'".concat("/bg.jpg","\')"),'
            'filter:"blur(24px) brightness(0.55) saturate(0.80)",transform:"scale(1.08)"'
            'backdrop-filter: blur(8px) saturate(1.45) !important;'
            'className:"glass-float backdrop-blur-md backdrop-saturate-[2.25]"'
        )
        updated, hits = patch_clinic_js(sample)
        self.assertGreater(hits, 0)
        self.assertIn("/bg_soft.jpg", updated)
        self.assertNotIn("blur(24px)", updated)
        self.assertNotIn('"/bg.jpg"', updated)
        self.assertNotIn("blur(8px)", updated)
        self.assertNotIn("backdrop-blur-md", updated)
        self.assertIn("backdrop-filter: none !important", updated)


if __name__ == "__main__":
    unittest.main()
