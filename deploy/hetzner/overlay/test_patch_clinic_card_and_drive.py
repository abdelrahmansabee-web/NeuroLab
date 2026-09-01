#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from patch_clinic_card_and_drive import (
    CHART,
    DOWNLOAD_NEW,
    DOWNLOAD_OLD,
    FT_NEW,
    FT_OLD,
    METRICS,
    RECORDER_NEW,
    RECORDER_OLD,
    VIDEO_OFF,
    patch_clinic_card_and_drive,
    patch_js_text,
)


SAMPLE = VIDEO_OFF + METRICS + CHART + FT_OLD + RECORDER_OLD + DOWNLOAD_OLD


class ClinicCardAndDriveTests(unittest.TestCase):
    def test_removes_card_extras_after_analyze(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertIn("phase-card camera preview", applied)
        self.assertIn("phase-card metric tiles", applied)
        self.assertIn("phase-card movement chart", applied)
        self.assertNotIn("bg-black mb-1.5", out)
        self.assertNotIn("Movement chart", out)
        self.assertNotIn("grid grid-cols-2 gap-1.5", out)

    def test_records_visible_stage_and_saves_unified_blob(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn(FT_NEW, out)
        self.assertIn("getBoundingClientRect", out)
        self.assertIn("#141821", out)
        self.assertIn("pe(te,!0)", out)
        self.assertIn("videoBitsPerSecond:1e7", out)
        self.assertIn("video/mp4", out)
        self.assertIn(DOWNLOAD_NEW, out)
        self.assertIn("unifiedVideoBlob:n", out)
        self.assertIn("_validation_unified.mp4", out)
        self.assertNotIn("validation_\".concat(e.k,\"_\"", out)
        self.assertNotIn(FT_OLD, out)
        self.assertNotIn(RECORDER_OLD, out)

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
                '<meta name="nl-version" content="31.78"/>'
                '<script src="/static/js/main.0626212c.js?kin=6"></script>',
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "manifest.json").write_text(
                json.dumps({"start_url": "./?v=29.60-pwa"}),
                encoding="utf-8",
            )
            self.assertEqual(patch_clinic_card_and_drive(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(FT_NEW, js)
            self.assertIn(DOWNLOAD_NEW, js)
            self.assertNotIn("Movement chart", js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=7", html)
            self.assertIn("31.79", html)
            manifest = json.loads(
                (root / "frontend" / "build" / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["start_url"], "./?v=29.61-pwa")

    def test_live_bundle_has_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if FT_NEW in text:
            self.assertIn(DOWNLOAD_NEW, text)
            self.assertNotIn("Movement chart", text)
            return
        self.assertIn(FT_OLD, text)
        self.assertIn(VIDEO_OFF, text)
        self.assertIn(METRICS, text)
        self.assertIn(CHART, text)
        self.assertIn(RECORDER_OLD, text)
        self.assertIn(DOWNLOAD_OLD, text)

    def test_applies_to_live_clinic_bundle(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        original = bundle.read_text(encoding="utf-8", errors="replace")
        if FT_NEW in original:
            self.assertNotIn("Movement chart", original)
            return
        out, applied = patch_js_text(original)
        self.assertIn("phase-card camera preview", applied)
        self.assertIn("record the visible overlay stage for Drive", applied)
        self.assertIn(FT_NEW, out)
        self.assertIn(DOWNLOAD_NEW, out)
        self.assertNotIn("Movement chart", out)
        self.assertNotIn("bg-black mb-1.5", out)
        self.assertIn("validation-metrics-gutter", out)
        self.assertIn("autoPlay:!0,autoRender:!0", out)


if __name__ == "__main__":
    unittest.main()
