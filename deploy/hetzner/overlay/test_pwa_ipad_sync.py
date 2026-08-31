#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import unittest


class PwaIpadSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.js = Path(__file__).resolve().parent.joinpath("pwa_ipad_sync.js").read_text(
            encoding="utf-8"
        )

    def test_only_runs_in_home_screen_app(self) -> None:
        self.assertIn("display-mode: standalone", self.js)
        self.assertIn("navigator.standalone", self.js)

    def test_uploads_unified_overlay_only(self) -> None:
        self.assertIn("/api/validation-cache", self.js)
        self.assertIn('fd.append("unifiedVideo"', self.js)
        self.assertIn("unifiedVideoBlob", self.js)
        self.assertNotIn('fd.append("originalVideo"', self.js)
        self.assertNotIn("overlay.json", self.js)

    def test_skips_records_without_overlay_video(self) -> None:
        self.assertIn("no_validation_video", self.js)
        self.assertIn("Generate Unified", self.js)
        self.assertIn("cameraOnly", self.js)
        self.assertNotIn("فيديوهات الفاليديشن متزامنة مع ملفات المرضى", self.js)

    def test_requires_drive_ok_before_success(self) -> None:
        self.assertIn("driveOk", self.js)
        self.assertIn("body.drive && body.drive.ok", self.js)
        self.assertIn("/api/ipad-sync-report", self.js)
        self.assertIn("nl_pwa_drive_ok_v1", self.js)

    def test_maps_to_drive_patient_files_from_home_screen(self) -> None:
        self.assertIn("رفع الفاليديشن للدرايف", self.js)
        self.assertIn("/connect-drive", self.js)
        self.assertIn("syncVideos(true)", self.js)
        self.assertIn("syncVideos(false)", self.js)
        self.assertIn("/api/ipad-localstorage", self.js)


if __name__ == "__main__":
    unittest.main()
