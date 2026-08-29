#!/usr/bin/env python3
"""Inject compositor-friendly clinic CSS. Does not change pose/analysis quality."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CSS_VER = "2"
LINK = f'<link rel="stylesheet" href="/clinic_smooth.css?v={CSS_VER}"/>'
BOOT = "<script>document.documentElement.classList.add('nl-clinic-smooth')</script>"
HREF_RE = re.compile(r'href="/clinic_smooth\.css(?:\?v=\d+)?"')


def patch_smooth_ui(root: Path) -> int:
    overlay = Path(__file__).resolve().parent
    css_src = overlay / "clinic_smooth.css"
    if not css_src.is_file():
        print(f"error: missing {css_src}", file=sys.stderr)
        return 1

    dest_build = root / "frontend" / "build" / "clinic_smooth.css"
    dest_root = root / "clinic_smooth.css"
    dest_build.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(css_src, dest_build)
    shutil.copy2(css_src, dest_root)
    print("copied clinic_smooth.css")

    idx = root / "frontend" / "build" / "index.html"
    if not idx.is_file():
        print("WARN: index.html missing")
        return 0
    text = idx.read_text(encoding="utf-8", errors="replace")
    if HREF_RE.search(text):
        text = HREF_RE.sub(f'href="/clinic_smooth.css?v={CSS_VER}"', text, count=1)
    elif "clinic_smooth.css" not in text:
        if "</head>" in text:
            text = text.replace("</head>", LINK + "</head>", 1)
        else:
            text = LINK + text
    if "nl-clinic-smooth" not in text:
        if "<head>" in text:
            text = text.replace("<head>", "<head>" + BOOT, 1)
        else:
            text = BOOT + text
    idx.write_text(text, encoding="utf-8")
    print("wired clinic_smooth.css into index.html")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) != 2:
        print("usage: patch_smooth_ui.py /opt/neurolab", file=sys.stderr)
        return 2
    return patch_smooth_ui(Path(argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
