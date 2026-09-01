#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path


class DriveOauthRoutesTests(unittest.TestCase):
    def test_html_uses_auth_prefixed_paths(self) -> None:
        html = Path(__file__).with_name("connect_drive.html").read_text(encoding="utf-8")
        self.assertIn("/auth/drive/oauth-status", html)
        self.assertIn("/auth/drive/connect-cookie", html)
        self.assertIn("/auth/drive/connect", html)
        self.assertIn("/auth/drive/folder-status", html)
        self.assertIn("Folder", html)
        self.assertNotIn("الفولدر", html)

    def test_route_decorators_in_source(self) -> None:
        src = Path(__file__).with_name("drive_oauth_routes.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/drive/oauth-status")', src)
        self.assertIn('@router.post("/drive/connect-cookie")', src)
        self.assertIn('@router.get("/drive/connect")', src)
        self.assertIn('@router.get("/drive/folder-status")', src)
        self.assertIn("write_drive_connected_marker", src)


if __name__ == "__main__":
    unittest.main()
