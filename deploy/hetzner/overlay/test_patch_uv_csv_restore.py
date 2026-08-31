#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_uv_csv_restore import (
    CACHE_CSV_NEW,
    CACHE_CSV_OLD,
    ME_BLOB_NEW,
    ME_BLOB_OLD,
    ME_VARS_NEW,
    ME_VARS_OLD,
    OVERLAY_MISSING_NEW,
    OVERLAY_MISSING_OLD,
    RUNNER_NEW,
    RUNNER_OLD,
    UV_ERR_NEW,
    UV_ERR_OLD,
    UV_FORM_NEW,
    UV_FORM_OLD,
    UV_MISSING_NEW,
    UV_MISSING_OLD,
    UV_POST_NEW,
    UV_POST_OLD,
    patch_uv_csv_restore,
)


class UvCsvRestoreTests(unittest.TestCase):
    def test_js_patches_on_sample(self) -> None:
        sample = (
            ME_VARS_OLD
            + ME_BLOB_OLD
            + "x;"
            + CACHE_CSV_OLD
            + UV_POST_OLD
            + ".concat(e);"
            + UV_ERR_OLD
        )
        from patch_uv_csv_restore import JS_PATCHES, _apply

        out, applied = _apply(sample, JS_PATCHES, "js")
        self.assertEqual(len(applied), 5)
        self.assertIn(ME_VARS_NEW, out)
        self.assertIn(ME_BLOB_NEW, out)
        self.assertIn(CACHE_CSV_NEW, out)
        self.assertIn(UV_POST_NEW, out)
        self.assertIn(UV_ERR_NEW, out)
        self.assertIn("csvBlob", out)
        self.assertIn("H_(Ce,e)", out)
        self.assertIn("ملف التحليل اتمسح من السيرفر", out)

    def test_python_patches_on_sample(self) -> None:
        sample = UV_FORM_OLD + UV_MISSING_OLD + OVERLAY_MISSING_OLD
        from patch_uv_csv_restore import PY_PATCHES, _apply

        out, applied = _apply(sample, PY_PATCHES[1:], "main")
        self.assertIn(UV_FORM_NEW, out)
        self.assertIn(UV_MISSING_NEW, out)
        self.assertIn(OVERLAY_MISSING_NEW, out)
        self.assertIn("hydrate_output_file", out)
        self.assertIn("csv: UploadFile = File(None)", out)

    def test_runner_pattern(self) -> None:
        self.assertIn("pose_csv=Path(analysis_csv_path)", RUNNER_NEW)
        self.assertNotIn("pose_csv", RUNNER_OLD)

    def test_patch_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (root / "analyze_job_runner.py").write_text("prefix\n" + RUNNER_OLD, encoding="utf-8")
            (root / "main.py").write_text(UV_FORM_OLD + UV_MISSING_OLD + OVERLAY_MISSING_OLD, encoding="utf-8")
            (js_dir / "main.0626212c.js").write_text(
                ME_VARS_OLD + ME_BLOB_OLD + CACHE_CSV_OLD + UV_POST_OLD + UV_ERR_OLD,
                encoding="utf-8",
            )
            (root / "frontend" / "build" / "index.html").write_text(
                '<script src="/static/js/main.0626212c.js?kin=1"></script>',
                encoding="utf-8",
            )
            self.assertEqual(patch_uv_csv_restore(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn("csvBlob", js)
            main = (root / "main.py").read_text(encoding="utf-8")
            self.assertIn("hydrate_output_file", main)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("kin=2", html)

    def test_live_or_snapshot_patterns(self) -> None:
        bundle = Path("/tmp/hf-neurolab/frontend/build/static/js/main.0626212c.js")
        if not bundle.is_file():
            self.skipTest("clinic bundle missing")
        text = bundle.read_text(encoding="utf-8", errors="replace")
        if CACHE_CSV_NEW in text:
            self.assertIn("csvBlob", text)
            return
        self.assertIn(CACHE_CSV_OLD, text)
        self.assertIn(UV_POST_OLD, text)
        self.assertIn(ME_BLOB_OLD, text)


if __name__ == "__main__":
    unittest.main()
