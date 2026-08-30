#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import drive_oauth


class DriveOauthTests(unittest.TestCase):
    def test_not_ready_without_secrets(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_OAUTH_CLIENT_ID": "", "GOOGLE_OAUTH_CLIENT_SECRET": ""}, clear=False):
            self.assertFalse(drive_oauth.oauth_client_configured())
            self.assertFalse(drive_oauth.oauth_ready())

    def test_token_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with patch.object(drive_oauth, "_data_dir", return_value=Path(raw)):
                with patch.dict(os.environ, {"JWT_SECRET": "unit-test-secret"}, clear=False):
                    drive_oauth.save_token({"refresh_token": "rt-1", "email": "a@b.c"})
                    loaded = drive_oauth.load_token()
                    self.assertEqual(loaded["refresh_token"], "rt-1")
                    self.assertEqual(loaded["email"], "a@b.c")
                    disk = Path(raw) / drive_oauth.TOKEN_FILE
                    self.assertTrue(disk.is_file())
                    raw_bytes = disk.read_bytes()
                    self.assertNotIn(b"rt-1", raw_bytes)

    def test_redirect_default(self) -> None:
        with patch.dict(os.environ, {"GOOGLE_OAUTH_REDIRECT_URI": ""}, clear=False):
            self.assertIn("auth/drive/callback", drive_oauth.redirect_uri())

    def test_status_asks_for_reconnect_when_client_set(self) -> None:
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "cid",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec",
            "GOOGLE_OAUTH_REFRESH_TOKEN": "",
            "GOOGLE_DRIVE_FOLDER_ID": "1o30Gi0XlWtpHoI5rsUoc8217IWoJUInK",
        }
        with patch.dict(os.environ, env, clear=False):
            with tempfile.TemporaryDirectory() as raw:
                with patch.object(drive_oauth, "_data_dir", return_value=Path(raw)):
                    status = drive_oauth.oauth_status()
                    self.assertTrue(status["clientConfigured"])
                    self.assertFalse(status["ready"])
                    self.assertTrue(status["needsReconnect"])
                    self.assertEqual(status["folderId"], "1o30Gi0XlWtpHoI5rsUoc8217IWoJUInK")

    def test_persist_refresh_skips_without_hub_token(self) -> None:
        with patch.dict(os.environ, {"HF_TOKEN": "", "HUGGINGFACE_HUB_TOKEN": "", "HUGGINGFACE_TOKEN": ""}, clear=False):
            drive_oauth.persist_refresh_token_secret("rt-should-not-upload")
        src = Path(drive_oauth.__file__).read_text(encoding="utf-8")
        self.assertIn('access_type="offline"', src)
        self.assertIn('prompt="consent"', src)
        self.assertNotIn("include_granted_scopes", src)


if __name__ == "__main__":
    unittest.main()
