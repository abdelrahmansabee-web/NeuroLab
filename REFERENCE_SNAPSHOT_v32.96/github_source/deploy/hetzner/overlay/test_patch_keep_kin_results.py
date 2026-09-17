#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_keep_kin_results import (
    POLL_NEW,
    POLL_OLD,
    RESULT_NEW,
    RESULT_OLD,
    SESSIONKEY_NEW,
    SESSIONKEY_OLD,
    SYNC_MERGE_NEW,
    SYNC_MERGE_OLD,
    WIPE_NEW,
    WIPE_OLD,
    cache_bust_index,
    patch_js_text,
    patch_keep_kin_results,
)


SAMPLE = (
    "BS=e.memo(function(t){let l=t.data,h=t.sessionKey;"
    + WIPE_OLD
    + ";const x=1;"
    + SESSIONKEY_OLD
    + ";"
    + SYNC_MERGE_OLD
    + ";"
    + POLL_OLD
    + "G(e=>e);"
    + RESULT_OLD
    + ";if(_.error)return}"
)


class KeepKinResultsTests(unittest.TestCase):
    def test_does_not_wipe_results_when_analysisResults_empty(self) -> None:
        out, applied = patch_js_text(SAMPLE)
        self.assertIn("keep kinematics on sessionKey remap", applied)
        self.assertNotIn("else g({}),localStorage.removeItem(vS)", out)
        self.assertIn("g(n=>a(a({},n),t))", out)
        self.assertIn("kinematicsSnapshot", out)
        self.assertIn('["pre","post","baseline"]', out)

    def test_prefers_participant_id_for_session_key(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn(SESSIONKEY_NEW, out)
        self.assertNotIn(SESSIONKEY_OLD, out)

    def test_keeps_local_analysis_results_on_sync(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn("analysisResults:r.analysisResults", out)
        self.assertNotIn("i(t=>a(a({},t),e)),null!==(t=e.kinematics)", out)

    def test_retries_progress_and_result(self) -> None:
        out, _ = patch_js_text(SAMPLE)
        self.assertIn("tries<8", out)
        self.assertIn("job_id:n", out)
        self.assertIn("/analyze-progress/", out)
        self.assertIn("/analyze-result/", out)
        self.assertNotIn(POLL_OLD, out)
        self.assertNotIn(RESULT_OLD, out)
        self.assertEqual(out.count("tries<8"), 2)

    def test_idempotent(self) -> None:
        once, _ = patch_js_text(SAMPLE)
        twice, applied = patch_js_text(once)
        self.assertEqual(once, twice)
        self.assertTrue(all(item.startswith("already ") for item in applied))

    def test_cache_bust(self) -> None:
        html = '<script src="/static/js/main.0626212c.js?touch=3"></script>'
        self.assertIn("main.0626212c.js?kin=1", cache_bust_index(html))

    def test_patterns_exist_in_live_bundle(self) -> None:
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
        if WIPE_NEW in text:
            self.assertNotIn("else g({}),localStorage.removeItem(vS)", text)
            return
        self.assertIn(WIPE_OLD, text)
        self.assertIn(SESSIONKEY_OLD, text)
        self.assertIn(SYNC_MERGE_OLD, text)
        self.assertIn(POLL_OLD, text)
        self.assertIn(RESULT_OLD, text)

    def test_patch_writes_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            js_dir = root / "frontend" / "build" / "static" / "js"
            js_dir.mkdir(parents=True)
            (js_dir / "main.0626212c.js").write_text(SAMPLE, encoding="utf-8")
            (root / "frontend" / "build" / "index.html").write_text(
                '<script src="/static/js/main.0626212c.js?touch=3"></script>',
                encoding="utf-8",
            )
            self.assertEqual(patch_keep_kin_results(root), 0)
            js = (js_dir / "main.0626212c.js").read_text(encoding="utf-8")
            self.assertIn(WIPE_NEW, js)
            self.assertIn(POLL_NEW, js)
            self.assertIn(RESULT_NEW, js)
            html = (root / "frontend" / "build" / "index.html").read_text(encoding="utf-8")
            self.assertIn("main.0626212c.js?kin=1", html)


if __name__ == "__main__":
    unittest.main()
