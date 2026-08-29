#!/usr/bin/env python3
"""Enable gzip + buffered proxy for static clinic files on HTTPS vhosts.

Does not change analyze/upload streaming. Safe to run more than once.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

GZIP_BLOCK = """
    gzip on;
    gzip_vary on;
    gzip_comp_level 5;
    gzip_proxied any;
    gzip_min_length 256;
    gzip_types text/plain text/css application/javascript application/json application/xml image/svg+xml;
"""

STREAM_LOCATION = """
    location ~ ^/(analyze|analyze-progress|auth/backup|auth/backup-file|auth/restore-file) {
        proxy_pass http://127.0.0.1:7860;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_connect_timeout 60s;
        proxy_buffering off;
        proxy_request_buffering off;
    }
"""


def patch_text(text: str) -> str:
    if "gzip on;" not in text:
        text = re.sub(
            r"(client_max_body_size\s+[^;]+;)",
            r"\1" + GZIP_BLOCK,
            text,
            count=1,
        )
        if "gzip on;" not in text:
            text = re.sub(r"(server\s*\{)", r"\1" + GZIP_BLOCK, text, count=1)

    if "analyze-progress" not in text:
        text = text.replace("location / {", STREAM_LOCATION + "\n    location / {", 1)

    # Allow nginx to gzip JS/CSS on the default location.
    text = text.replace("proxy_buffering off;", "proxy_buffering on;", 1) if (
        "location /" in text and "proxy_buffering on;" not in text.split("location /", 1)[-1][:800]
    ) else text

    # More reliable: in the last location / block, turn buffering on unless already streaming.
    parts = text.split("location / {")
    if len(parts) >= 2:
        head, rest = parts[0], "location / {".join(parts[1:])
        # Only flip the first proxy_buffering in the default location.
        rest = re.sub(
            r"proxy_buffering\s+off;",
            "proxy_buffering on;",
            rest,
            count=1,
        )
        text = head + "location / {" + rest
    return text


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = patch_text(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: patch_nginx_https_gzip.py /etc/nginx/sites-available/foo [...]", file=sys.stderr)
        return 2
    changed = 0
    for raw in sys.argv[1:]:
        path = Path(raw)
        if not path.is_file():
            print(f"skip missing {path}")
            continue
        if patch_file(path):
            print(f"patched {path}")
            changed += 1
        else:
            print(f"unchanged {path}")
    print(f"changed {changed} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
