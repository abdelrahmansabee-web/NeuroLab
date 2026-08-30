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
            self.assertIn("register_drive_oauth_routes", text)
            self.assertEqual(patch_drive_oauth(root), 0)
            again = auth.read_text(encoding="utf-8")
            self.assertEqual(again.count("from drive_oauth import oauth_drive_service"), 1)
            self.assertEqual(again.count("register_drive_oauth_routes(router, get_current_user)"), 1)


if __name__ == "__main__":
    unittest.main()
