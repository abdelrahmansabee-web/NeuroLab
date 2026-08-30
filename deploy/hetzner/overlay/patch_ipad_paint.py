#!/usr/bin/env python3
"""Stop live backdrop-filter on iPad only. Do not change glass colors."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CSS_VER = "1"
CSS_NAME = "clinic_ipad_paint.css"
LINK = f'<link rel="stylesheet" href="/{CSS_NAME}?v={CSS_VER}"/>'
BOOT = (
    "<script>(function(){var n=navigator;var i=/iPad|iPhone|iPod/.test(n.userAgent)"
    '||(n.platform==="MacIntel"&&n.maxTouchPoints>1);'
    "if(i)document.documentElement.classList.add('nl-ipad-paint');})();</script>"
)
HREF_RE = re.compile(rf'href="/{re.escape(CSS_NAME)}(?:\?v=\d+)?"')
BOOT_RE = re.compile(
    r"<script>\(function\(\)\{var n=navigator;var i=/iPad\|iPhone\|iPod/"
    r".*?nl-ipad-paint.*?</script>"
)


def wire_index_html(text: str) -> str:
    if "clinic_smooth.css" in text or "nl-clinic-smooth" in text:
        raise SystemExit("refusing to mix iPad paint with clinic_smooth glass override")
    if HREF_RE.search(text):
        text = HREF_RE.sub(f'href="/{CSS_NAME}?v={CSS_VER}"', text, count=1)
    elif CSS_NAME not in text:
        text = text.replace("<head>", f"<head>{LINK}", 1)
        if CSS_NAME not in text:
            text = LINK + text
    if BOOT_RE.search(text):
        text = BOOT_RE.sub(BOOT, text, count=1)
    elif "nl-ipad-paint" not in text:
        text = text.replace("<head>", f"<head>{BOOT}", 1)
        if "nl-ipad-paint" not in text:
            text = BOOT + text
    text = re.sub(
        r"main\.0626212c\.js(?:\?[^\"']*)?",
        "main.0626212c.js?paint=1",
        text,
    )
    return text


def patch_index_html(root: Path) -> None:
    idx = root / "frontend" / "build" / "index.html"
    if not idx.is_file():
        print("WARN: index.html missing")
        return
    original = idx.read_text(encoding="utf-8")
    updated = wire_index_html(original)
    if updated != original:
        idx.write_text(updated, encoding="utf-8")
        print(f"wired {CSS_NAME} into index.html")
    else:
        print("index.html already wired for iPad paint")


def copy_css(overlay: Path, root: Path) -> None:
    src = overlay / CSS_NAME
    if not src.is_file():
        raise SystemExit(f"missing {src}")
    css = src.read_text(encoding="utf-8")
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"background(?:-color)?\s*:", rules):
        raise SystemExit("iPad paint CSS must not change fills")
    dests = [
        root / CSS_NAME,
        root / "frontend" / "build" / CSS_NAME,
    ]
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copied {CSS_NAME} -> {dest}")


def patch_ipad_paint(root: Path) -> int:
    overlay = Path(__file__).resolve().parent
    copy_css(overlay, root)
    patch_index_html(root)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_ipad_paint.py /opt/neurolab", file=sys.stderr)
        return 2
    return patch_ipad_paint(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
