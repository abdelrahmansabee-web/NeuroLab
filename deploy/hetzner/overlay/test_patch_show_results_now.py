#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_show_results_now import (
    AUTOPLAY_NEW,
    AUTOPLAY_OLD,
    CARD_METRICS_NEW,
    CARD_METRICS_OLD,
    COMPLETE_NEW,
    COMPLETE_OLD,
    PREPARING_NEW,
    PREPARING_OLD,
    TABLE_GATE_NEW,
    TABLE_GATE_OLD,
    UV_HIDE_READY_NEW,
    UV_HIDE_READY_OLD,
    UV_HIDE_START_NEW,
    UV_HIDE_START_OLD,
    VALIDATION_ID_NEW,
    VALIDATION_ID_OLD,
    patch_js_text,
    patch_show_results_now,
)


SAMPLE = (
    TABLE_GATE_OLD
    + UV_HIDE_START_OLD
    + UV_HIDE_READY_OLD
    + AUTOPLAY_OLD
    + COMPLETE_OLD
    + CARD_METRICS_OLD
    + VALIDATION_ID_OLD
    + PREPARING_OLD
)


class ShowResultsNowTests(unittest.TestCase):
    def test_shows_table_without_waiting_for_overlay(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertEqual(len(applied), 8)
        self.assertIn(TABLE_GATE_NEW, out)
        self.assertNotIn("!le[e.k]&&!Xe[e.k]", out)
        self.assertIn("K(e.length>0)", out)

    def test_keeps_table_during_uv(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn(UV_HIDE_START_NEW, out)
        self.assertIn(UV_HIDE_READY_NEW, out)
        self.assertNotIn(UV_HIDE_START_OLD, out)
        self.assertNotIn(",K(!1),void B", out)

    def test_autoplays_overlay_and_camera_fallback(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn(AUTOPLAY_NEW, out)
        self.assertIn("Preparing skeleton overlay", out)
        self.assertIn("Se[e.k]?(0,Un.jsxs)", out)
        self.assertIn(COMPLETE_NEW, out)
        self.assertIn("K(!0)", out)
        self.assertIn(CARD_METRICS_NEW, out)
        self.assertNotIn("sm:hidden grid grid-cols-2", out)
        self.assertIn('id:"kin-validation-video"', out)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))

    def test_writes_bundle_and_cache_bust(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(SAMPLE, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<script src="/static/js/main.0626212c.js?kin=3"></script>',
                encoding="utf-8",
            )
            self.assertEqual(patch_show_results_now(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(TABLE_GATE_NEW, js)
            self.assertIn(PREPARING_NEW, js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("main.0626212c.js?kin=4", html)

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            snapshot = (
                Path(__file__).resolve().parents[3]
                / "REFERENCE_SNAPSHOT_v31.75"
                / "hf_space"
                / "frontend"
                / "build"
                / "static"
                / "js"
                / "main.0626212c.js"
            )
            bundle = snapshot
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if TABLE_GATE_NEW in text:
            self.assertIn(AUTOPLAY_NEW, text)
            self.assertIn("Preparing skeleton overlay", text)
            return
        self.assertIn(TABLE_GATE_OLD, text)
        self.assertIn(UV_HIDE_START_OLD, text)
        self.assertIn(UV_HIDE_READY_OLD, text)
        self.assertIn(AUTOPLAY_OLD, text)
        self.assertIn(COMPLETE_OLD, text)
        self.assertIn(CARD_METRICS_OLD, text)
        self.assertIn(VALIDATION_ID_OLD, text)
        self.assertIn(PREPARING_OLD, text)


if __name__ == "__main__":
    unittest.main()
