#!/usr/bin/env python3
from __future__ import annotations

import unittest

from patch_nginx_https_gzip import patch_text

SAMPLE = """
server {
    listen 443 ssl;
    server_name medlabai.duckdns.org;
    client_max_body_size 512M;
    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_buffering off;
        proxy_request_buffering off;
    }
}
"""


class NginxGzipPatchTests(unittest.TestCase):
    def test_adds_gzip_and_stream_location(self) -> None:
        out = patch_text(SAMPLE)
        self.assertIn("gzip on;", out)
        self.assertIn("analyze-progress", out)
        default = out.split("location / {", 1)[1]
        self.assertIn("proxy_buffering on;", default)

    def test_idempotent(self) -> None:
        once = patch_text(SAMPLE)
        twice = patch_text(once)
        self.assertEqual(once.count("gzip on;"), twice.count("gzip on;"))
        self.assertEqual(once.count("analyze-progress"), twice.count("analyze-progress"))


if __name__ == "__main__":
    unittest.main()
