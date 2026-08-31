#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from persist_validation import persist_phase_artifacts


class PersistValidationTests(unittest.TestCase):
    def test_copies_named_files_for_restore(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            src = data_dir / "src"
            src.mkdir()
            video = src / "clip.mp4"
            overlay = src / "ov.json"
            video.write_bytes(b"mp4-bytes")
            overlay.write_text("{}", encoding="utf-8")
            saved = persist_phase_artifacts(
                data_dir,
                "101",
                "pre",
                original_video=video,
                overlay_json=overlay,
                library_name="pre_test",
            )
            self.assertEqual(saved["files"]["pre_validation_original.mp4"], 9)
            dest_v = data_dir / "local_artifacts" / "team" / "101" / "videos" / "pre_validation_original.mp4"
            dest_o = data_dir / "local_artifacts" / "team" / "101" / "data" / "pre_validation_overlay.json"
            self.assertTrue(dest_v.is_file())
            self.assertTrue(dest_o.is_file())
            lib = data_dir / "local_artifacts" / "library" / "pre_test" / "pre_validation_original.mp4"
            self.assertTrue(lib.is_file())
            session = data_dir / "local_artifacts" / "team" / "101" / "session.json"
            self.assertTrue(session.is_file())
            rec = json.loads(session.read_text(encoding="utf-8"))
            self.assertTrue(rec["never_delete"])
            self.assertIn("pre", rec["phases"])
            self.assertTrue(saved.get("drive", {}).get("skipped"))
            from unittest.mock import patch

            with patch("drive_persist.upload_named_files", return_value={"ok": True, "files": {"pre_validation.mp4": {"bytes": 9}}}) as mocked:
                persist_phase_artifacts(
                    data_dir,
                    "101",
                    "pre",
                    original_video=video,
                    overlay_json=overlay,
                    unified_video=video,
                )
                names = [item[0] for item in mocked.call_args[0][1]]
                self.assertEqual(names, ["pre_validation.mp4"])

    def test_uploads_original_as_validation_when_unified_missing(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            src = data_dir / "src"
            src.mkdir()
            video = src / "clip.mp4"
            video.write_bytes(b"mp4-bytes")
            with patch(
                "drive_persist.upload_named_files",
                return_value={"ok": True, "files": {"pre_validation.mp4": {"bytes": 9}}},
            ) as mocked:
                saved = persist_phase_artifacts(
                    data_dir,
                    "101",
                    "pre",
                    original_video=video,
                )
                mocked.assert_not_called()
                self.assertTrue(saved.get("drive", {}).get("skipped"))

    def test_same_path_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            dest_dir = data_dir / "local_artifacts" / "team" / "101" / "videos"
            dest_dir.mkdir(parents=True)
            video = dest_dir / "pre_validation_original.mp4"
            video.write_bytes(b"same-file")
            overlay = data_dir / "ov.json"
            overlay.write_text("{}", encoding="utf-8")
            saved = persist_phase_artifacts(
                data_dir, "101", "pre", original_video=video, overlay_json=overlay
            )
            self.assertIn("pre_validation_original.mp4", saved["files"])
            session = data_dir / "local_artifacts" / "team" / "101" / "session.json"
            self.assertTrue(session.is_file())

    def test_persists_pose_csv_without_uploading_it_to_drive(self) -> None:
        from persist_validation import hydrate_output_file
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as raw:
            data_dir = Path(raw)
            src = data_dir / "src"
            src.mkdir()
            csv = src / "baseline_raw_pose.csv"
            csv.write_text("t,x,y\n0,1,2\n", encoding="utf-8")
            with patch("drive_persist.upload_named_files") as mocked:
                saved = persist_phase_artifacts(
                    data_dir,
                    "111_Douan_ertan",
                    "baseline",
                    pose_csv=csv,
                )
                mocked.assert_not_called()
            dest = (
                data_dir
                / "local_artifacts"
                / "team"
                / "111_Douan_ertan"
                / "data"
                / "baseline_raw_pose.csv"
            )
            self.assertTrue(dest.is_file())
            self.assertIn("baseline_pose.csv", saved["files"])
            outputs = Path(raw) / "outputs"
            restored = hydrate_output_file(data_dir, outputs, "baseline_raw_pose.csv")
            self.assertIsNotNone(restored)
            self.assertEqual(restored.read_text(encoding="utf-8"), "t,x,y\n0,1,2\n")


if __name__ == "__main__":
    unittest.main()
