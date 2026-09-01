#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_ptr_hang import (
    KK_NEW,
    KK_OLD,
    ZE_NEW,
    ZE_OLD,
    patch_js_text,
    patch_ptr_hang,
)


SAMPLE = KK_OLD + ZE_OLD


class PtrHangTests(unittest.TestCase):
    def test_caps_spinner_and_skips_awaiting_drive(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertEqual(len(applied), 2)
        self.assertIn(KK_NEW, out)
        self.assertIn(ZE_NEW, out)
        self.assertIn("setTimeout(e,6e3)", out)
        self.assertIn('jk("/auth/me",{},5e3)', out)
        self.assertNotIn("await Bk({silent:!0})", out)
        self.assertIn("Bk({silent:!0})", out)
        self.assertNotIn(KK_OLD, out)
        self.assertNotIn(ZE_OLD, out)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))

    def test_writes_bundle_and_pwa_reload(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(SAMPLE, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<meta name="nl-version" content="31.79"/>'
                '<script src="/static/js/main.0626212c.js?kin=7"></script>',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.61-pwa"}),
                encoding="utf-8",
            )
            self.assertEqual(patch_ptr_hang(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(ZE_NEW, js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=8", html)
            self.assertIn("31.80", html)
            manifest = json.loads(
                (root / "frontend" / "build" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["start_url"], "./?v=29.62-pwa")

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if ZE_NEW in text:
            self.assertIn(KK_NEW, text)
            self.assertNotIn("await Bk({silent:!0})", text)
            return
        self.assertIn(KK_OLD, text)
        self.assertIn(ZE_OLD, text)

    def test_applies_to_live_clinic_bundle(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        original = bundle.read_text(encoding="utf-8", errors="replace")
        if ZE_NEW in original:
            self.assertIn(KK_NEW, original)
            return
        out, applied = patch_js_text(original)
        self.assertEqual(len(applied), 2)
        self.assertIn(ZE_NEW, out)
        self.assertIn(KK_NEW, out)
        self.assertIn("ptr-spinner-anchor", out)


if __name__ == "__main__":
    unittest.main()
