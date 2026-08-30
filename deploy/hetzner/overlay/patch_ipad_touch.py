#!/usr/bin/env python3
"""Fix iPad tap delay without changing clinic glass colors."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CSS_VER = "1"
CSS_NAME = "clinic_touch.css"
LINK = f'<link rel="stylesheet" href="/{CSS_NAME}?v={CSS_VER}"/>'
PWA_SYNC_JS = "pwa_ipad_sync.js"
PWA_SYNC_TAG = f'<script src="/{PWA_SYNC_JS}?v=2"></script>'
HREF_RE = re.compile(rf'href="/{re.escape(CSS_NAME)}(?:\?v=\d+)?"')
WHILE_TAP_RE = re.compile(r"whileTap:(?:x\?void 0:)?Yw\([^)]+\)")
PTR_MOVE_OLD = 'addEventListener("touchmove",r,{passive:!1})'
PTR_MOVE_NEW = 'addEventListener("touchmove",r,{passive:!0})'
PTR_PREVENT_OLD = "n>18&&t.cancelable&&t.preventDefault()"
PTR_PREVENT_NEW = "0"


def patch_touch_js(text: str) -> tuple[str, int]:
    hits = 0
    updated, n = WHILE_TAP_RE.subn("whileTap:void 0", text)
    text = updated
    hits += n
    if PTR_MOVE_OLD in text:
        text = text.replace(PTR_MOVE_OLD, PTR_MOVE_NEW)
        hits += 1
    if PTR_PREVENT_OLD in text:
        text = text.replace(PTR_PREVENT_OLD, PTR_PREVENT_NEW)
        hits += 1
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
        updated, hits = patch_touch_js(original)
        if hits:
            path.write_text(updated, encoding="utf-8")
            print(f"patched iPad touch in {path.name} ({hits} replacements)")
            patched += 1
        else:
            print(f"unchanged touch {path.name}")
    return patched


def wire_index_html(text: str) -> str:
    if "clinic_smooth.css" in text or "nl-clinic-smooth" in text:
        raise SystemExit("refusing to mix touch fix with clinic_smooth")
    if "clinic_ipad_paint.css" in text:
        raise SystemExit("refusing to mix touch fix with iPad frost paint")
    if HREF_RE.search(text):
        text = HREF_RE.sub(f'href="/{CSS_NAME}?v={CSS_VER}"', text, count=1)
    elif CSS_NAME not in text:
        text = text.replace("<head>", f"<head>{LINK}", 1)
        if CSS_NAME not in text:
            text = LINK + text
    text = re.sub(
        r"main\.0626212c\.js(?:\?[^\"']*)?",
        "main.0626212c.js?touch=1",
        text,
    )
    text = re.sub(
        rf'<script src="/{re.escape(PWA_SYNC_JS)}(?:\?v=\d+)?"></script>',
        PWA_SYNC_TAG,
        text,
    )
    if PWA_SYNC_JS not in text:
        if "</body>" in text:
            text = text.replace("</body>", PWA_SYNC_TAG + "</body>", 1)
        else:
            text = text + PWA_SYNC_TAG
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
        print("index.html already wired for iPad touch")


def copy_css(overlay: Path, root: Path) -> None:
    src = overlay / CSS_NAME
    if not src.is_file():
        raise SystemExit(f"missing {src}")
    css = src.read_text(encoding="utf-8")
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"background(?:-color)?\s*:", rules):
        raise SystemExit("touch CSS must not change fills")
    if "backdrop-filter" in rules:
        raise SystemExit("touch CSS must not change glass blur")
    dests = [
        root / CSS_NAME,
        root / "frontend" / "build" / CSS_NAME,
    ]
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copied {CSS_NAME} -> {dest}")
    sync_src = overlay / PWA_SYNC_JS
    if sync_src.is_file():
        for dest in dests:
            shutil.copy2(sync_src, dest.parent / PWA_SYNC_JS)
            print(f"copied {PWA_SYNC_JS} -> {dest.parent / PWA_SYNC_JS}")


def patch_ipad_touch(root: Path) -> int:
    overlay = Path(__file__).resolve().parent
    copy_css(overlay, root)
    patch_build_js(root)
    patch_index_html(root)
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_ipad_touch.py /opt/neurolab", file=sys.stderr)
        return 2
    return patch_ipad_touch(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
