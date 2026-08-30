#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from patch_drive_oauth import HEALTH_OLD, SERVICE_OLD, patch_drive_oauth


class PatchDriveOauthTests(unittest.TestCase):
    def test_patches_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            auth = root / "auth.py"
            auth.write_text(
                SERVICE_OLD
                + "    return None\n\n"
                + HEALTH_OLD
                + "    return out\n",
                encoding="utf-8",
            )
            self.assertEqual(patch_drive_oauth(root), 0)
            text = auth.read_text(encoding="utf-8")
            self.assertIn("oauth_drive_service", text)
            self.assertIn("oauthReady", text)
            self.assertIn("oauth_client_configured", text)
            self.assertIn("Personal Gmail Drive has no quota", text)
            self.assertIn("register_drive_oauth_routes", text)
            self.assertEqual(patch_drive_oauth(root), 0)
            again = auth.read_text(encoding="utf-8")
            self.assertEqual(again.count("from drive_oauth import oauth_client_configured, oauth_drive_service, oauth_ready"), 1)
            self.assertEqual(again.count("register_drive_oauth_routes(router, get_current_user)"), 1)

    def test_upgrades_service_account_fallback(self) -> None:
        from patch_drive_oauth import SERVICE_SA_FALLBACK, patch_drive_oauth

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            auth = root / "auth.py"
            auth.write_text(
                SERVICE_SA_FALLBACK
                + "    return None\n\n"
                + HEALTH_OLD
                + "    return out\n",
                encoding="utf-8",
            )
            self.assertEqual(patch_drive_oauth(root), 0)
            text = auth.read_text(encoding="utf-8")
            self.assertIn("oauth_client_configured", text)
            self.assertIn("Personal Gmail Drive has no quota", text)

    def test_maps_validation_original_and_skips_unified(self) -> None:
        from patch_drive_oauth import (
            BACKUP_FILE_OLD,
            BACKUP_UPLOAD_OLD,
            RESTORE_FILE_OLD,
        )

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            auth = root / "auth.py"
            auth.write_text(
                SERVICE_OLD
                + "    return None\n\n"
                + HEALTH_OLD
                + "    return out\n"
                + BACKUP_FILE_OLD
                + BACKUP_UPLOAD_OLD
                + RESTORE_FILE_OLD,
                encoding="utf-8",
            )
            self.assertEqual(patch_drive_oauth(root), 0)
            text = auth.read_text(encoding="utf-8")
            self.assertIn("original_videos_only", text)
            self.assertIn("clinic_drive_filename", text)


if __name__ == "__main__":
    unittest.main()
