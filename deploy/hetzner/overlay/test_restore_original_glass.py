#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from restore_original_glass import restore_index_html, restore_original_glass


class RestoreOriginalGlassTests(unittest.TestCase):
    def test_strips_smoothness_from_index(self) -> None:
        html = (
            "<html><head>"
            "<script>document.documentElement.classList.add('nl-clinic-smooth')</script>"
            '<link rel="stylesheet" href="/clinic_smooth.css?v=6"/>'
            '<script src="/clinic_smooth.js?v=6"></script>'
            '<script defer="defer" src="/static/js/main.0626212c.js?v=6"></script>'
            "</head></html>"
        )
        out = restore_index_html(html)
        self.assertNotIn("nl-clinic-smooth", out)
        self.assertNotIn("clinic_smooth.css", out)
        self.assertNotIn("clinic_smooth.js", out)
        self.assertIn('src="/static/js/main.0626212c.js"', out)
        self.assertNotIn("main.0626212c.js?v=", out)

    def test_restores_js_from_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            main = js_dir / "main.0626212c.js"
            bak = js_dir / "main.0626212c.js.bak-preblur"
            main.write_text("PATCHED", encoding="utf-8")
            bak.write_text("ORIGINAL_GLASS", encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<html><head><link rel="stylesheet" href="/clinic_smooth.css?v=6"/></head></html>',
                encoding="utf-8",
            )
            self.assertEqual(restore_original_glass(root), 0)
            self.assertEqual(main.read_text(encoding="utf-8"), "ORIGINAL_GLASS")
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertNotIn("clinic_smooth.css", html)


if __name__ == "__main__":
    unittest.main()
