#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_smooth_ui import patch_smooth_ui


class PatchSmoothUiTests(unittest.TestCase):
    def test_copies_css_and_wires_index(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                "<html><head><title>NeuroLab</title></head><body></body></html>",
                encoding="utf-8",
            )
            rc = patch_smooth_ui(root)
            self.assertEqual(rc, 0)
            css = (build / "clinic_smooth.css").read_text(encoding="utf-8")
            self.assertIn("backdrop-filter: none", css)
            self.assertNotIn("rgba(16, 22, 32, 0.94)", css)
            self.assertNotIn("background-color:", css)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn("/clinic_smooth.css", html)
            self.assertIn("nl-clinic-smooth", html)
            self.assertTrue((root / "clinic_smooth.css").is_file())

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
            self.assertIn("clinic_smooth.css?v=2", html)
            self.assertEqual(html.count("nl-clinic-smooth"), 1)

    def test_bumps_cached_css_query(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                '<html><head><link rel="stylesheet" href="/clinic_smooth.css?v=1"/></head></html>',
                encoding="utf-8",
            )
            self.assertEqual(patch_smooth_ui(root), 0)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn("clinic_smooth.css?v=2", html)
            self.assertNotIn("clinic_smooth.css?v=1", html)


if __name__ == "__main__":
    unittest.main()
