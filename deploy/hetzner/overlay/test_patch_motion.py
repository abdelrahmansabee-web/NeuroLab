#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_motion import (
    CSS_PATCHES,
    JS_PATCHES,
    PANEL_EASE,
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
    def test_js_uses_slow_transform_and_real_fade(self) -> None:
        out, applied = patch_js_text(JS_SAMPLE)
        self.assertEqual(len(applied), len(JS_PATCHES))
        self.assertIn(PANEL_EASE, out)
        self.assertIn('transform:rt?"translate3d(".concat(X,"px,0,0)")', out)
        self.assertIn('willChange:"transform"', out)
        self.assertNotIn("padding-left 520ms", out)
        self.assertNotIn("paddingLeft:rt?X:0", out)
        self.assertIn('g("exiting")', out)
        self.assertIn("F.current=t", out)
        self.assertNotIn("querySelector", out)
        self.assertNotIn("startTransition(()=>l(t))", out)

    def test_css_is_opacity_only_with_soft_ease(self) -> None:
        out, applied = patch_css_text(CSS_SAMPLE)
        self.assertEqual(len(applied), len(CSS_PATCHES))
        self.assertIn("--section-bounce-out-ms:200ms", out)
        self.assertIn("--section-bounce-in-ms:360ms", out)
        self.assertIn("--section-bounce-out-ease:cubic-bezier(0.4,0,0.2,1)", out)
        self.assertIn("--section-bounce-in-ease:cubic-bezier(0.33,0,0.2,1)", out)
        self.assertIn("@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}", out)
        self.assertIn("will-change:opacity", out)
        self.assertIn("html,body,#root{overflow-x:hidden}", out)
        self.assertNotIn("translate3d(0,12px,0)", out)
        self.assertNotIn("cubic-bezier(0.4,0,1,1)", out)
        self.assertIn("@media (prefers-reduced-motion:reduce){.nl-motion-layer{transition:none!important}}", out)
        self.assertNotIn(".section-nav-motion.section-bounce-out{animation:none!important", out)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(JS_SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))
        css_once, _ = patch_css_text(CSS_SAMPLE)
        css_twice, css_applied = patch_css_text(css_once)
        self.assertEqual(css_once, css_twice)
        self.assertTrue(all(item.startswith("already ") for item in css_applied))

    def test_upgrades_gpu_expo_and_dom_fade_bundle(self) -> None:
        expo_js = "".join(
            olds[1] if isinstance(olds, tuple) and len(olds) > 1 else (olds if isinstance(olds, str) else olds[0])
            for _label, olds, _new in JS_PATCHES
        )
        out, applied = patch_js_text(expo_js)
        self.assertTrue(any(not item.startswith("already ") for item in applied))
        self.assertIn(PANEL_EASE, out)
        self.assertIn('g("exiting")', out)
        self.assertNotIn("querySelector", out)

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
                '<meta name="nl-version" content="31.89"/>'
                '<script src="/static/js/main.0626212c.js?kin=17"></script>'
                '<link href="/static/css/main.17fa781b.css?m=5" rel="stylesheet">',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.68-pwa"}),
                encoding="utf-8",
            )
            (root / "main.py").write_text('DEPLOY_VERSION = "29.68"\n', encoding="utf-8")
            self.assertEqual(patch_motion(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            manifest = json.loads(
                (root / "frontend" / "build" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertIn(PANEL_EASE, js)
            self.assertIn("kin=18", html)
            self.assertIn("css/main.17fa781b.css?m=6", html)
            self.assertIn("31.90", html)
            self.assertEqual(manifest["start_url"], "./?v=29.69-pwa")
            self.assertIn('DEPLOY_VERSION = "29.69"', (root / "main.py").read_text(encoding="utf-8"))

    def test_applies_to_live_clinic_bundle(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        css = Path("/tmp/hf-neurolab/frontend/build/static/css/main.17fa781b.css")
        if not bundle.is_file() or not css.is_file():
            self.skipTest("clinic bundle missing")
        js_out, js_applied = patch_js_text(bundle.read_text(encoding="utf-8", errors="replace"))
        css_out, css_applied = patch_css_text(css.read_text(encoding="utf-8", errors="replace"))
        self.assertEqual(len(js_applied), len(JS_PATCHES))
        self.assertEqual(len(css_applied), len(CSS_PATCHES))
        self.assertIn(PANEL_EASE, js_out)
        self.assertIn('g("exiting")', js_out)
        self.assertNotIn("paddingLeft:rt?X:0", js_out)
        self.assertNotIn('querySelector(".section-nav-motion")', js_out)
        self.assertIn("@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}", css_out)
        self.assertIn("cubic-bezier(0.4,0,0.2,1)", css_out)
        self.assertNotIn(".section-nav-motion.section-bounce-out{animation:none!important", css_out)
        self.assertNotIn("translate3d(0,12px,0)", css_out)


if __name__ == "__main__":
    unittest.main()
