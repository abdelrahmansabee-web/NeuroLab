#!/usr/bin/env python3
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from drive_persist import _sanitize, clinic_drive_filename, drive_configured, upload_named_files, upload_root_bytes


class DrivePersistTests(unittest.TestCase):
    def test_skips_when_unset(self) -> None:
        out = upload_named_files("101", [("pre_validation_original.mp4", Path("/nope"), "videos")])
        self.assertTrue(out.get("skipped"))
        self.assertEqual(out.get("reason"), "drive_unset")
        self.assertTrue(out.get("never_delete"))

    def test_upserts_existing_and_never_calls_delete(self) -> None:
        service = MagicMock()
        service.files.return_value.list.return_value.execute.return_value = {"files": [{"id": "existing"}]}
        service.files.return_value.update.return_value.execute.return_value = {"id": "existing"}
        with self._tmp_mp4() as path:
            out = upload_named_files(
                "p 101",
                [
                    ("pre_validation_original.mp4", path, "videos"),
                    ("pre_validation_unified.mp4", path, "videos"),
                    ("pre_validation_overlay.json", path, "data"),
                ],
                service=service,
                folder_id="root",
            )
        self.assertTrue(out["ok"])
        self.assertIn("pre_validation.mp4", out["files"])
        self.assertNotIn("pre_validation_original.mp4", out["files"])
        self.assertNotIn("pre_original.mp4", out["files"])
        self.assertNotIn("pre_validation_overlay.json", out["files"])
        self.assertTrue(out["ok"])
        self.assertEqual(out["patientKey"], "p_101")
        service.files.return_value.update.assert_called()
        service.files.return_value.delete.assert_not_called()
        service.files.return_value.create.assert_not_called()

    def test_sanitize(self) -> None:
        self.assertEqual(_sanitize("pre/../x"), "pre_.._x")

    def test_drive_keeps_validation_videos_only(self) -> None:
        self.assertEqual(clinic_drive_filename("pre_validation_unified.mp4"), "pre_validation.mp4")
        self.assertEqual(clinic_drive_filename("clip_unified_validation.mp4"), "clip_validation.mp4")
        self.assertIsNone(clinic_drive_filename("pre_validation_original.mp4"))
        self.assertIsNone(clinic_drive_filename("pre_original.mp4"))
        self.assertIsNone(clinic_drive_filename("pre_validation_overlay.json"))
        self.assertEqual(clinic_drive_filename("01_demographics.json"), "01_demographics.json")
        self.assertEqual(clinic_drive_filename("baseline_validation.mp4"), "baseline_validation.mp4")

    def test_oauth_pending_does_not_use_service_account(self) -> None:
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "cid",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec",
            "GOOGLE_SERVICE_ACCOUNT_JSON": "{}",
            "GOOGLE_DRIVE_FOLDER_ID": "folder",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as raw:
                with patch("drive_oauth._data_dir", return_value=Path(raw)):
                    self.assertFalse(drive_configured())

    def test_root_upload_skips_without_oauth(self) -> None:
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "cid",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as raw:
                with patch("drive_oauth._data_dir", return_value=Path(raw)):
                    out = upload_root_bytes("_NEUROLAB_DRIVE_OK.json", b'{"ok":true}')
                    self.assertTrue(out.get("skipped"))

    def test_renames_validation_original_on_drive(self) -> None:
        from drive_persist import promote_original_videos_on_drive

        service = MagicMock()
        listed = [
            {
                "files": [
                    {"id": "vid1", "name": "baseline_validation_original.mp4", "mimeType": "video/mp4"},
                    {"id": "uni1", "name": "baseline_validation_unified.mp4", "mimeType": "video/mp4"},
                ]
            },
            {"files": []},
        ]
        service.files.return_value.list.return_value.execute.side_effect = listed
        service.files.return_value.update.return_value.execute.return_value = {"id": "vid1"}
        with patch("drive_persist.drive_configured", return_value=True):
            with patch("drive_persist._build_service", return_value=(service, "root")):
                out = promote_original_videos_on_drive()
        self.assertTrue(out["ok"])
        self.assertEqual(out["renamed"][0]["to"], "baseline_original.mp4")
        service.files.return_value.update.assert_called()

    def _tmp_mp4(self):
        import tempfile
        from contextlib import contextmanager

        @contextmanager
        def ctx():
            with tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / "clip.mp4"
                path.write_bytes(b"mp4-bytes-xx")
                yield path

        return ctx()


if __name__ == "__main__":
    unittest.main()
