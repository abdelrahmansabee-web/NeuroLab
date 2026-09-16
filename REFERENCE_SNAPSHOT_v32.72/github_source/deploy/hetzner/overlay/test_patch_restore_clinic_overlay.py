#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_restore_clinic_overlay import (
    LOCAL_NEW,
    LOCAL_OLD,
    MOV_NEW,
    MOV_OLD,
    patch_js_text,
    patch_restore_clinic_overlay,
)


class RestoreClinicOverlayTests(unittest.TestCase):
    def test_plays_mov_under_skeleton(self) -> None:
        sample = MOV_OLD + "x);" + LOCAL_OLD + "return !1}"
        out, applied = patch_js_text(sample)
        self.assertEqual(len(applied), 2)
        self.assertIn(".mov", out)
        self.assertIn("localFile", out)
        self.assertIn(MOV_NEW, out)
        self.assertIn(LOCAL_NEW, out)

    def test_idempotent(self) -> None:
        sample = MOV_OLD + LOCAL_OLD
        once, _ = patch_js_text(sample)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))

    def test_writes_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(MOV_OLD + LOCAL_OLD, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<script src="/static/js/main.0626212c.js?kin=2"></script>',
                encoding="utf-8",
            )
            self.assertEqual(patch_restore_clinic_overlay(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(".mov", js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=3", html)

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if MOV_NEW in text:
            self.assertIn("localFile", text)
            return
        self.assertIn(MOV_OLD, text)
        self.assertIn(LOCAL_OLD, text)


if __name__ == "__main__":
    unittest.main()
