#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_fix_stuck_analyze import (
    ANALYZE_NEW,
    ANALYZE_OLD,
    CARD_PLAY_NEW,
    CARD_PLAY_OLD,
    FD_NEW,
    FD_OLD,
    patch_fix_stuck_analyze,
    patch_js_text,
)


SAMPLE = FD_OLD + ANALYZE_OLD + CARD_PLAY_OLD


class FixStuckAnalyzeTests(unittest.TestCase):
    def test_clears_analyzing_and_reuses_blob(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertEqual(len(applied), 3)
        self.assertIn(FD_NEW, out)
        self.assertIn('t[r]="uploaded"', out)
        self.assertIn("H_(Ce,t)", out)
        self.assertIn("choose the file again", out)
        self.assertIn(CARD_PLAY_NEW, out)
        self.assertNotIn(ANALYZE_OLD, out)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))

    def test_writes_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(SAMPLE, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<meta name="nl-version" content="31.77"/>'
                '<script src="/static/js/main.0626212c.js?kin=5"></script>',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.59-pwa"}),
                encoding="utf-8",
            )
            self.assertEqual(patch_fix_stuck_analyze(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(ANALYZE_NEW, js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=6", html)
            self.assertIn("31.78", html)

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if ANALYZE_NEW in text:
            self.assertIn('t[r]="uploaded"', text)
            return
        self.assertIn(ANALYZE_OLD, text)
        self.assertIn(FD_OLD, text)
        self.assertIn(CARD_PLAY_OLD, text)


if __name__ == "__main__":
    unittest.main()
