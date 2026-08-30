#!/usr/bin/env python3
"""Bake the clinic photo filter so iPad does not live-blur a full-screen image.

Keeps original glass: panel opacity and backdrop-filter are not changed.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

FILTER_OLD = 'filter:"blur(24px) brightness(0.55) saturate(0.80)",transform:"scale(1.08)"'
FILTER_NEW = 'filter:"none",transform:"none"'
STATE_OLD = 'useState)("/bg.jpg")'
STATE_NEW = 'useState)("/bg_baked.jpg")'
HARDCODE_OLD = '.concat("/bg.jpg","\')")'
HARDCODE_NEW = '.concat("/bg_baked.jpg","\')")'


def patch_clinic_js(text: str) -> tuple[str, int]:
    hits = 0
    if FILTER_OLD in text:
        n = text.count(FILTER_OLD)
        text = text.replace(FILTER_OLD, FILTER_NEW)
        hits += n
    if STATE_OLD in text:
        n = text.count(STATE_OLD)
        text = text.replace(STATE_OLD, STATE_NEW)
        hits += n
    if HARDCODE_OLD in text:
        n = text.count(HARDCODE_OLD)
        text = text.replace(HARDCODE_OLD, HARDCODE_NEW)
        hits += n
    return text, hits


def patch_build_js(root: Path) -> int:
    js_dir = root / "frontend" / "build" / "static" / "js"
    if not js_dir.is_dir():
        print("WARN: no frontend/build/static/js")
        return 0
    patched = 0
    for path in sorted(js_dir.glob("main.*.js")):
        if path.name.endswith(".map") or "LICENSE" in path.name:
            continue
        original = path.read_text(encoding="utf-8", errors="replace")
        updated, hits = patch_clinic_js(original)
        if hits:
            path.write_text(updated, encoding="utf-8")
            print(f"patched {path.name} ({hits} replacements)")
            patched += 1
        else:
            print(f"unchanged {path.name}")
    return patched


def _copy_baked(overlay: Path, root: Path) -> None:
    src = overlay / "bg_baked.jpg"
    if not src.is_file():
        raise SystemExit(f"missing {src}")
    dests = [
        root / "bg_baked.jpg",
        root / "frontend" / "build" / "bg_baked.jpg",
    ]
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copied bg_baked.jpg -> {dest}")


def patch_index_html(root: Path) -> None:
    idx = root / "frontend" / "build" / "index.html"
    if not idx.is_file():
        print("WARN: index.html missing")
        return
    html = idx.read_text(encoding="utf-8")
    updated = re.sub(
        r"main\.0626212c\.js(?:\?[^\"']*)?",
        "main.0626212c.js?bg=1",
        html,
    )
    if updated != html:
        idx.write_text(updated, encoding="utf-8")
        print("cache-bust index.html main JS ?bg=1")


def patch_ipad_bg(root: Path) -> int:
    overlay = Path(__file__).resolve().parent
    _copy_baked(overlay, root)
    patch_build_js(root)
    patch_index_html(root)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_ipad_bg.py /opt/neurolab", file=sys.stderr)
        return 2
    return patch_ipad_bg(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
