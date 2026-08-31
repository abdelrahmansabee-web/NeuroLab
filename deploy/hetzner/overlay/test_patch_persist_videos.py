#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_persist_videos import (
    PERSIST_NEW,
    PERSIST_TRY,
    PLAYBACK_NEW,
    PLAYBACK_OLD,
    _patch,
    collapse_stacked_runner_patches,
    main as patch_videos_main,
)


class PersistPatchIdempotentTests(unittest.TestCase):
    def test_persist_try_does_not_include_progress(self) -> None:
        self.assertIn("persist_phase_artifacts", PERSIST_TRY)
        self.assertNotIn("_prog(95", PERSIST_TRY)
        self.assertTrue(PERSIST_NEW.startswith(PERSIST_TRY))

    def test_collapse_triple_stack(self) -> None:
        stacked = (
            "    playback_video = video_path\n"
            "    playback_video = video_path\n"
            "    playback_video = video_path\n"
            "    video_path = _downscale_video_for_analysis(video_path)\n"
            + PERSIST_TRY
            + PERSIST_TRY
            + PERSIST_TRY
            + '    _prog(95, "Finalizing results…")\n'
        )
        out = collapse_stacked_runner_patches(stacked)
        self.assertEqual(out.count("playback_video = video_path"), 1)
        self.assertEqual(out.count("persist_phase_artifacts("), 1)
        self.assertEqual(out.count("_prog(95"), 1)

    def test_patch_does_not_restack_when_old_is_substring(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "runner.py"
            path.write_text(PLAYBACK_OLD, encoding="utf-8")
            _patch(path, PLAYBACK_OLD, PLAYBACK_NEW, "keep playback video")
            _patch(path, PLAYBACK_OLD, PLAYBACK_NEW, "keep playback video")
            text = path.read_text(encoding="utf-8")
            self.assertEqual(text.count("playback_video = video_path"), 1)
            self.assertEqual(text.count("_downscale_video_for_analysis"), 1)

    def test_copies_oauth_files(self) -> None:
        import sys

        overlay = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "frontend" / "build" / "static" / "js").mkdir(parents=True)
            (root / "main.py").write_text("# placeholder\n", encoding="utf-8")
            (root / "analyze_job_runner.py").write_text("# placeholder\n", encoding="utf-8")
            argv = sys.argv[:]
            try:
                sys.argv = ["patch_persist_videos.py", str(root)]
                # Patterns are missing, so patching main/runner fails after copies.
                with self.assertRaises(SystemExit):
                    patch_videos_main()
            finally:
                sys.argv = argv
            for name in (
                "drive_oauth.py",
                "drive_oauth_routes.py",
                "connect_drive.html",
                "drive_persist.py",
                "backfill_drive.py",
                "validation_cache.py",
                "patient_drive_archive.py",
                "patient_pdf.py",
                "glass_report.py",
            ):
                self.assertTrue((root / name).is_file(), name)
            self.assertTrue((overlay / "drive_oauth.py").is_file())


if __name__ == "__main__":
    unittest.main()
