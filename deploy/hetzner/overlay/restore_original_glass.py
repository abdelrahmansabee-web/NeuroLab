#!/usr/bin/env python3
"""Remove clinic smoothness overlays and restore original glass CSS/JS."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

BOOT_RE = re.compile(
    r"<script>document\.documentElement\.classList\.add\('nl-clinic-smooth'\)</script>"
)
CSS_RE = re.compile(r'<link rel="stylesheet" href="/clinic_smooth\.css\?v=\d+"/>')
JS_RE = re.compile(r'<script src="/clinic_smooth\.js\?v=\d+"></script>')
MAIN_SRC_RE = re.compile(r'(src="/static/js/main\.[a-zA-Z0-9]+\.js)(?:\?[^"]*)?"')


def restore_index_html(text: str) -> str:
    text = BOOT_RE.sub("", text)
    text = CSS_RE.sub("", text)
    text = JS_RE.sub("", text)
    text = MAIN_SRC_RE.sub(r'\1?orig=1"', text, count=1)
    return text


def restore_original_glass(root: Path) -> int:
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        original = idx.read_text(encoding="utf-8", errors="replace")
        updated = restore_index_html(original)
        if updated != original:
            idx.write_text(updated, encoding="utf-8")
            print("restored index.html (removed clinic_smooth)")
        else:
            print("index.html already without clinic_smooth")
    else:
        print("WARN: index.html missing")

    js_dir = root / "frontend" / "build" / "static" / "js"
    if js_dir.is_dir():
        for path in sorted(js_dir.glob("main.*.js")):
            if path.name.endswith(".map") or "LICENSE" in path.name:
                continue
            bak = path.with_name(path.name + ".bak-preblur")
            if bak.is_file():
                shutil.copy2(bak, path)
                print(f"restored {path.name} from {bak.name}")
            else:
                print(f"WARN: no backup for {path.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) != 2:
        print("usage: restore_original_glass.py /opt/neurolab", file=sys.stderr)
        return 2
    return restore_original_glass(Path(argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
