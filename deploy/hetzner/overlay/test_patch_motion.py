#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_motion import (
    CSS_PATCHES,
    JS_PATCHES,
    patch_css_text,
    patch_js_text,
    patch_motion,
)


def _first_olds(pairs):
    chunks = []
    for _label, olds, _new in pairs:
        chunks.append(olds[0] if isinstance(olds, tuple) else olds)
    return "".join(chunks)


JS_SAMPLE = _first_olds(JS_PATCHES)
CSS_SAMPLE = _first_olds(CSS_PATCHES)


class MotionPatchTests(unittest.TestCase):
    def test_js_uses_slow_transform_not_padding(self) -> None:
        out, applied = patch_js_text(JS_SAMPLE)
        self.assertEqual(len(applied), len(JS_PATCHES))
        self.assertIn("transform 700ms cubic-bezier(0.45, 0, 0.55, 1)", out)
        self.assertIn('transform:rt?"translate3d(".concat(X,"px,0,0)")', out)
        self.assertNotIn("padding-left 520ms", out)
        self.assertNotIn("paddingLeft:rt?X:0", out)
        self.assertIn("const d=!1,u=\"exiting\"===i&&!d", out)

    def test_css_is_opacity_only(self) -> None:
        out, applied = patch_css_text(CSS_SAMPLE)
        self.assertEqual(len(applied), len(CSS_PATCHES))
        self.assertIn("--section-bounce-out-ms:240ms", out)
        self.assertIn("--section-bounce-in-ms:320ms", out)
        self.assertIn("@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}", out)
        self.assertIn("will-change:opacity", out)
        self.assertIn("html,body,#root{overflow-x:hidden}", out)
        self.assertNotIn("translate3d(0,12px,0)", out)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(JS_SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))
        css_once, _ = patch_css_text(CSS_SAMPLE)
        css_twice, css_applied = patch_css_text(css_once)
        self.assertEqual(css_once, css_twice)
        self.assertTrue(all(item.startswith("already ") for item in css_applied))

    def test_upgrades_gpu_expo_bundle(self) -> None:
        expo_js = "".join(
            olds[1] if isinstance(olds, tuple) and len(olds) > 1 else (olds if isinstance(olds, str) else olds[0])
            for _label, olds, _new in JS_PATCHES
        )
        out, applied = patch_js_text(expo_js)
        self.assertTrue(any(not item.startswith("already ") for item in applied))
        self.assertIn("transform 700ms cubic-bezier(0.45, 0, 0.55, 1)", out)

    def test_writes_bundle_css_and_pwa_reload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            css_dir = root / "frontend" / "build" / "static" / "css"
            js_dir.mkdir(parents=True)
            css_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(JS_SAMPLE, encoding="utf-8")
            (css_dir / "main.17fa781b.css").write_text(CSS_SAMPLE, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<meta name="nl-version" content="31.84"/>'
                '<script src="/static/js/main.0626212c.js?kin=12"></script>'
                '<link href="/static/css/main.17fa781b.css?m=1" rel="stylesheet">',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.66-pwa"}),
                encoding="utf-8",
            )
            (root / "main.py").write_text('DEPLOY_VERSION = "29.66"\n', encoding="utf-8")
            self.assertEqual(patch_motion(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            manifest = json.loads(
                (root / "frontend" / "build" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn("transform 700ms cubic-bezier(0.45, 0, 0.55, 1)", js)
            self.assertIn("kin=15", html)
            self.assertIn("css/main.17fa781b.css?m=4", html)
            self.assertIn("31.87", html)
            self.assertEqual(manifest["start_url"], "./?v=29.67-pwa")

    def test_applies_to_live_clinic_bundle(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        css = Path("/tmp/hf-neurolab/frontend/build/static/css/main.17fa781b.css")
        if not bundle.is_file() or not css.is_file():
            self.skipTest("clinic bundle missing")
        js_out, js_applied = patch_js_text(bundle.read_text(encoding="utf-8", errors="replace"))
        css_out, css_applied = patch_css_text(css.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(len(js_applied), len(JS_PATCHES))
        self.assertEqual(len(css_applied), len(CSS_PATCHES))
        self.assertIn("transform 700ms cubic-bezier(0.45, 0, 0.55, 1)", js_out)
        self.assertNotIn("paddingLeft:rt?X:0", js_out)
        self.assertIn("@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}", css_out)
        self.assertNotIn("translate3d(0,12px,0)", css_out)


if __name__ == "__main__":
    unittest.main()
