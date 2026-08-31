#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backfill_drive import backfill_data_dir, collect_local_sessions
from persist_validation import persist_phase_artifacts


class BackfillDriveTests(unittest.TestCase):
    def test_collects_team_and_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=self._write(data_dir / "a.mp4", b"video-bytes"),
                overlay_json=self._write(data_dir / "a.json", b"{}"),
            )
            cache = data_dir / "validation_cache" / "128_betul_yusel" / "pre"
            cache.mkdir(parents=True)
            (cache / "original.mp4").write_bytes(b"betul-video")
            sessions = collect_local_sessions(data_dir)
            keys = {(key, phase) for key, phase, _files in sessions}
            self.assertIn(("101", "pre"), keys)
            self.assertIn(("128_betul_yusel", "pre"), keys)

    def test_backfill_skips_drive_when_unset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=self._write(data_dir / "a.mp4", b"video-bytes"),
            )
            out = backfill_data_dir(data_dir)
            self.assertEqual(out["count"], 1)
            self.assertTrue(out["sessions"][0].get("skipped") or out["sessions"][0]["drive"].get("skipped"))
            self.assertIn("records", out)
            self.assertNotIn("originals", out)

    def test_backfill_uploads_unified_validation_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            cache = data_dir / "validation_cache" / "105_Ahmet_sever" / "baseline"
            cache.mkdir(parents=True)
            (cache / "original.mp4").write_bytes(b"camera")
            (cache / "unified.mp4").write_bytes(b"overlay-video")
            (cache / "overlay.json").write_bytes(b"{}")
            out = backfill_data_dir(data_dir)
            session = out["sessions"][0]
            self.assertEqual(session["patientKey"], "105_Ahmet_sever")
            self.assertIn("baseline_validation_unified.mp4", session["files"])
            self.assertNotIn("baseline_validation_original.mp4", session["files"])
            self.assertTrue(session["drive"].get("skipped"))

    def test_backfill_uses_original_when_unified_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            cache = data_dir / "validation_cache" / "111_Douan_ertan" / "baseline"
            cache.mkdir(parents=True)
            (cache / "original.mp4").write_bytes(b"camera")
            out = backfill_data_dir(data_dir)
            session = out["sessions"][0]
            self.assertEqual(session["patientKey"], "111_Douan_ertan")
            self.assertTrue(session.get("skipped"))
            self.assertEqual(session.get("reason"), "no_validation_video")

    def test_rebuild_calls_reorganize(self) -> None:
        from unittest.mock import patch

        from backfill_drive import rebuild_clinic_folder

        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            with patch(
                "drive_persist.reorganize_clinic_folder",
                return_value={"ok": True, "patientCount": 1, "pdfs": 1, "videos": 1},
            ):
                with patch("drive_persist.list_clinic_folder", return_value={"ok": True, "jsonCount": 0}):
                    out = rebuild_clinic_folder(data_dir)
        self.assertTrue(out["ok"])
        self.assertEqual(out["reorganized"]["patientCount"], 1)
        self.assertIn("backfill", out)
        self.assertEqual(out["inventory"]["jsonCount"], 0)

    def _write(self, path: Path, content: bytes) -> Path:
        path.write_bytes(content)
        return path


if __name__ == "__main__":
    unittest.main()
