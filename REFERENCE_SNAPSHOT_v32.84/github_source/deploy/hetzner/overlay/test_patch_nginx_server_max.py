#!/usr/bin/env python3
from __future__ import annotations

import unittest

from patch_nginx_server_max import patch_text

HTTPS_PROXY = """
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name medlabai.duckdns.org;
    client_max_body_size 512M;

    location ~ ^/(analyze|analyze-progress|auth/backup|auth/backup-file|auth/restore-file) {
        proxy_pass http://127.0.0.1:7860;
        proxy_buffering off;
    }

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_buffering on;
    }
}
"""

REDIRECT_ONLY = """
server {
    listen 443 ssl default_server;
    server_name _;
    location / {
        return 301 https://medlabai.duckdns.org$request_uri;
    }
}
"""

ALREADY = """
server {
    listen 443 ssl http2;
    location / {
        proxy_pass http://127.0.0.1:7860;
    }
    include /etc/nginx/snippets/neurolab-static-cache-locations.conf;
}
"""


class NginxServerMaxTests(unittest.TestCase):
    def test_enables_http2_and_static_cache_on_proxy_vhost(self) -> None:
        out = patch_text(HTTPS_PROXY)
        self.assertIn("listen 443 ssl http2;", out)
        self.assertIn("listen [::]:443 ssl http2;", out)
        self.assertIn("neurolab-static-cache-locations.conf", out)
        self.assertLess(
            out.index("neurolab-static-cache-locations.conf"),
            out.index("location ~ ^/(analyze"),
        )
        self.assertIn("auth/restore-file", out)

    def test_skips_redirect_only_vhost(self) -> None:
        out = patch_text(REDIRECT_ONLY)
        self.assertIn("listen 443 ssl http2 default_server;", out)
        self.assertNotIn("neurolab-static-cache-locations.conf", out)

    def test_idempotent(self) -> None:
        once = patch_text(HTTPS_PROXY)
        twice = patch_text(once)
        self.assertEqual(once, twice)
        self.assertEqual(once.count("http2"), 2)
        self.assertEqual(once.count("neurolab-static-cache-locations.conf"), 1)

    def test_already_patched(self) -> None:
        out = patch_text(ALREADY)
        self.assertEqual(out.count("http2"), 1)
        self.assertEqual(out.count("neurolab-static-cache-locations.conf"), 1)


if __name__ == "__main__":
    unittest.main()
