#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_unblock_analyze_ui import (
    AWAIT_NEW,
    AWAIT_OLD,
    CARD_NEW,
    CARD_OLD,
    WE_NEW,
    WE_OLD,
    patch_js_text,
    patch_unblock_analyze_ui,
)


SAMPLE = WE_OLD + AWAIT_OLD + CARD_OLD


class UnblockAnalyzeUiTests(unittest.TestCase):
    def test_does_not_force_download_before_results(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertEqual(len(applied), 3)
        self.assertIn(WE_NEW, out)
        self.assertNotIn("await Ge(e,n,{force:!0})", out)
        self.assertNotIn("!i&&A&&await We(t,n,A)", out)
        self.assertIn("We(t,n,A).catch", out)
        self.assertIn(AWAIT_NEW, out)
        self.assertIn(CARD_NEW, out)

    def test_uses_local_blob_including_non_mp4(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn("t instanceof Blob&&t.size>0", out)
        self.assertNotIn('o=i.endsWith(".mp4")||i.endsWith(".webm");if(n&&(await Ge', out)

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
                '<meta name="nl-version" content="31.76"/>'
                '<link rel="manifest" href="/manifest.json?v=29.14"/>'
                '<script src="/static/js/main.0626212c.js?kin=4"></script>',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.14-pwa", "name": "NeuroLab"}),
                encoding="utf-8",
            )
            self.assertEqual(patch_unblock_analyze_ui(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(WE_NEW, js)
            self.assertIn("We(t,n,A).catch", js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("main.0626212c.js?kin=5", html)
            self.assertIn('nl-version" content="31.77"', html)
            self.assertIn("manifest.json?v=29.59", html)
            manifest = json.loads(
                (root / "frontend" / "build" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["start_url"], "./?v=29.59-pwa")

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if WE_NEW in text:
            self.assertNotIn("await We(t,n,A)", text)
            return
        self.assertIn(WE_OLD, text)
        self.assertIn(AWAIT_OLD, text)
        self.assertIn(CARD_OLD, text)


if __name__ == "__main__":
    unittest.main()
