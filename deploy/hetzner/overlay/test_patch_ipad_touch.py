#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_ipad_touch import (
    CSS_NAME,
    PTR_MOVE_NEW,
    PTR_MOVE_OLD,
    PTR_PREVENT_OLD,
    patch_touch_js,
    wire_index_html,
)


SAMPLE = (
    "whileTap:Yw(.97),onClick:n,"
    "whileTap:x?void 0:Yw(.97),onClick:o,"
    'e.addEventListener("touchmove",r,{passive:!1}),'
    "void(n>18&&t.cancelable&&t.preventDefault()),"
    'filter:"blur(24px) brightness(0.55) saturate(0.80)",'
    "rgba(255,255,255,0.008),"
    'html.nl-touch .sidebar-shell { backdrop-filter: blur(8px) saturate(1.45) !important; }'
)


class IpadTouchTests(unittest.TestCase):
    def test_fixes_tap_path_keeps_glass(self) -> None:
        out, hits = patch_touch_js(SAMPLE)
        self.assertGreater(hits, 0)
        self.assertNotIn("whileTap:Yw(", out)
        self.assertIn("whileTap:void 0", out)
        self.assertIn(PTR_MOVE_NEW, out)
        self.assertNotIn(PTR_MOVE_OLD, out)
        self.assertNotIn(PTR_PREVENT_OLD, out)
        self.assertIn("blur(24px) brightness(0.55)", out)
        self.assertIn("rgba(255,255,255,0.008)", out)
        self.assertIn("blur(8px) saturate(1.45)", out)

    def test_idempotent(self) -> None:
        once, _ = patch_touch_js(SAMPLE)
        twice, hits = patch_touch_js(once)
        self.assertEqual(once, twice)
        self.assertEqual(hits, 0)

    def test_css_is_touch_only(self) -> None:
        import re

        css = Path(__file__).resolve().parent.joinpath(CSS_NAME).read_text(encoding="utf-8")
        rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertIn("touch-action: manipulation", rules)
        self.assertIsNone(re.search(r"background(?:-color)?\s*:", rules))
        self.assertNotIn("backdrop-filter", rules)
        self.assertNotIn("rgba(", rules)

    def test_wires_index(self) -> None:
        html = (
            '<html><head></head><body>'
            '<script src="/static/js/main.0626212c.js?orig=2"></script></body></html>'
        )
        out = wire_index_html(html)
        self.assertIn(f"{CSS_NAME}?v=1", out)
        self.assertIn("main.0626212c.js?touch=2", out)
        self.assertIn("pwa_ipad_sync.js?v=2", out)
        self.assertNotIn("clinic_smooth", out)
        self.assertNotIn("clinic_ipad_paint", out)

    def test_refuses_paint_and_smooth(self) -> None:
        with self.assertRaises(SystemExit):
            wire_index_html('<html><head><link rel="stylesheet" href="/clinic_ipad_paint.css?v=4"/></head></html>')
        with self.assertRaises(SystemExit):
            wire_index_html('<html><head><link rel="stylesheet" href="/clinic_smooth.css?v=6"/></head></html>')

    def test_copy_into_build(self) -> None:
        from patch_ipad_touch import patch_ipad_touch

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            build = root / "frontend" / "build"
            js_dir = build / "static" / "js"
            js_dir.mkdir(parents=True)
            (build / "index.html").write_text(
                '<html><head></head><body><script src="/static/js/main.0626212c.js"></script></body></html>',
                encoding="utf-8",
            )
            (js_dir / "main.0626212c.js").write_text(SAMPLE, encoding="utf-8")
            self.assertEqual(patch_ipad_touch(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn("whileTap:void 0", js)
            self.assertIn("blur(24px) brightness(0.55)", js)
            html = (build / "index.html").read_text(encoding="utf-8")
            self.assertIn(CSS_NAME, html)
            self.assertTrue((build / CSS_NAME).is_file())
            self.assertTrue((build / "pwa_ipad_sync.js").is_file())
            self.assertIn("pwa_ipad_sync.js", html)
            js_sync = (build / "pwa_ipad_sync.js").read_text(encoding="utf-8")
            self.assertIn("navigator.standalone", js_sync)
            self.assertIn("/sync-ipad", js_sync)
            self.assertIn("/connect-drive", js_sync)
            self.assertIn("ربط الدرايف", js_sync)


if __name__ == "__main__":
    unittest.main()
