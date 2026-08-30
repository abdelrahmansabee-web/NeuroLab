#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_ipad_paint import CSS_NAME, wire_index_html


class IpadPaintTests(unittest.TestCase):
    def test_wires_boot_and_css_keeps_glass_query(self) -> None:
        html = (
            "<!doctype html><html><head></head><body>"
            '<script src="/static/js/main.0626212c.js?bg=1"></script>'
            "</body></html>"
        )
        out = wire_index_html(html)
        self.assertIn(f"{CSS_NAME}?v=1", out)
        self.assertIn("nl-ipad-paint", out)
        self.assertIn("main.0626212c.js?paint=1", out)
        self.assertNotIn("clinic_smooth", out)
        self.assertEqual(out.count(CSS_NAME), 1)
        self.assertEqual(out.count("nl-ipad-paint"), 1)

    def test_idempotent(self) -> None:
        html = "<html><head></head></html>"
        once = wire_index_html(html)
        twice = wire_index_html(once)
        self.assertEqual(once.count(CSS_NAME), 1)
        self.assertEqual(twice.count(CSS_NAME), 1)
        self.assertEqual(once.count("nl-ipad-paint"), 1)
        self.assertEqual(twice.count("nl-ipad-paint"), 1)

    def test_refuses_smooth_override(self) -> None:
        with self.assertRaises(SystemExit):
            wire_index_html(
                '<html><head><link rel="stylesheet" href="/clinic_smooth.css?v=6"/></head></html>'
            )

    def test_css_does_not_change_fills(self) -> None:
        import re

        css = Path(__file__).resolve().parent.joinpath(CSS_NAME).read_text(encoding="utf-8")
        rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertIsNone(re.search(r"background(?:-color)?\s*:", rules))
        self.assertIn("backdrop-filter: none", css)
        self.assertIn("html.nl-ipad-paint", css)
        self.assertNotRegex(rules, r"rgba\(")

    def test_copy_into_build(self) -> None:
        from patch_ipad_paint import patch_ipad_paint

        overlay = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            build.mkdir(parents=True)
            (build / "index.html").write_text(
                '<html><head></head><body><script src="/static/js/main.0626212c.js"></script></body></html>',
                encoding="utf-8",
            )
            self.assertEqual(patch_ipad_paint(root), 0)
            self.assertTrue((build / CSS_NAME).is_file())
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn(CSS_NAME, html)
            self.assertIn("nl-ipad-paint", html)


if __name__ == "__main__":
    unittest.main()
