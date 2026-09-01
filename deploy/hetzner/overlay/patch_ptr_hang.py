#!/usr/bin/env python3
"""Stop iPad pull-to-refresh from hanging on Drive/server sync.

Pulling down shows the top spinner and awaits /auth/me (no timeout) plus a
full patient restore from Google Drive. On the Home Screen app that often
never finishes, so the spinner stays over the clinic.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KK_OLD = (
    'Promise.resolve("function"===typeof i?i():void 0).catch(()=>{}).finally(()=>'
    "{c.current=!1,b(e,0,\"idle\")})"
)
KK_NEW = (
    'Promise.race([Promise.resolve("function"===typeof i?i():void 0),'
    "new Promise(function(e){setTimeout(e,6e3)})]).catch(()=>{}).finally(()=>"
    "{c.current=!1,b(e,0,\"idle\")})"
)

ZE_OLD = (
    "ze=(0,e.useCallback)(async()=>{if(Sk())Be(\"Sync paused while video analysis is running\",\"info\");"
    "else try{const e=await fetch(\"/auth/me\",{credentials:\"same-origin\",headers:z_()});"
    "if(e.ok){const t=await e.json();t&&de(t)}await Bk({silent:!0})}catch(e){}},[])"
)
ZE_NEW = (
    "ze=(0,e.useCallback)(async()=>{if(Sk())Be(\"Sync paused while video analysis is running\",\"info\");"
    "else{try{const e=await jk(\"/auth/me\",{},5e3);if(e.ok){const t=await e.json();t&&de(t)}}catch(e){}"
    "Bk({silent:!0})}},[])"
)

PATCHES = (
    ("hide pull-to-refresh spinner after 6s", KK_OLD, KK_NEW),
    ("do not wait on Drive restore for pull-to-refresh", ZE_OLD, ZE_NEW),
)


def patch_js_text(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in PATCHES:
        if old in text:
            text = text.replace(old, new, 1)
            applied.append(label)
            continue
        if new in text:
            applied.append(f"already {label}")
            continue
        raise SystemExit(f"pattern not found: {label}")
    return text, applied


def patch_pwa_reload(root: Path) -> list[str]:
    notes: list[str] = []
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        updated = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            "main.0626212c.js?kin=8",
            html,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r"\g<1>31.80",
            updated,
            count=1,
        )
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append("index kin=8 nl-version 31.80")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != "./?v=29.62-pwa":
            data["start_url"] = "./?v=29.62-pwa"
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append("manifest start_url 29.62-pwa")
    return notes


def patch_ptr_hang(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; ptr-hang not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("ptr-hang:", ", ".join(applied))
    notes = patch_pwa_reload(root)
    if notes:
        print("pwa reload:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_ptr_hang.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_ptr_hang(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
