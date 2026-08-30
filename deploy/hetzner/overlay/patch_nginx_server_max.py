#!/usr/bin/env python3
"""Enable HTTP/2 and long-cache hashed static files on clinic nginx vhosts.

Does not change analysis quality or clinic glass CSS.
Safe to run more than once.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INCLUDE_LINE = "    include /etc/nginx/snippets/neurolab-static-cache-locations.conf;\n"
MARKER = "neurolab-static-cache-locations.conf"


def enable_http2(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        line = match.group(0)
        if "http2" in line:
            return line
        return line.replace(" ssl", " ssl http2", 1)

    return re.sub(r"listen\s+(?:\[[^\]]+\]:)?443\s+ssl[^;]*;", _repl, text)


def insert_static_cache(text: str) -> str:
    if MARKER in text:
        return text

    # Only proxy server blocks need the cache locations (not ACME/redirect-only).
    if "proxy_pass http://127.0.0.1:7860" not in text and "proxy_pass http://127.0.0.1:7860;" not in text:
        return text

    # Insert once, before the first location that serves the app.
    for needle in (
        "    location ~ ^/(analyze",
        "    location / {",
    ):
        if needle in text:
            return text.replace(needle, INCLUDE_LINE + "\n" + needle, 1)
    return text


def patch_text(text: str) -> str:
    return insert_static_cache(enable_http2(text))


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = patch_text(original)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "usage: patch_nginx_server_max.py /etc/nginx/sites-available/foo [...]",
            file=sys.stderr,
        )
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
