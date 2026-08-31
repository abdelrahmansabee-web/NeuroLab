#!/usr/bin/env python3
"""Play the camera file under the skeleton again, including iPhone .mov."""
from __future__ import annotations

import re
import sys
from pathlib import Path

MOV_OLD = 'r.endsWith(".mp4")||r.endsWith(".webm")?(i=URL.createObjectURL(t),Ae('
MOV_NEW = (
    'r.endsWith(".mp4")||r.endsWith(".webm")||r.endsWith(".mov")||r.endsWith(".m4v")'
    "?(i=URL.createObjectURL(t),Ae("
)

LOCAL_OLD = (
    "if(!t)return;if(!r&&Ne.current[e])return;r&&(Ae(t=>{t[e]&&URL.revokeObjectURL(t[e]);"
    "const n=a({},t);return delete n[e],Ne.current=n,n}),pe(t=>a(a({},t),{},{[e]:!1})));"
    "const i=m[e],s=async()=>{"
)
LOCAL_NEW = (
    "if(!t)return;if(!r&&Ne.current[e])return;r&&(Ae(t=>{t[e]&&URL.revokeObjectURL(t[e]);"
    "const n=a({},t);return delete n[e],Ne.current=n,n}),pe(t=>a(a({},t),{},{[e]:!1})));"
    'const localFile=l["".concat(Re(e),"_file")];'
    "if(!r&&localFile instanceof Blob&&localFile.size>0){const url=URL.createObjectURL(localFile);"
    "Ae(t=>{t[e]&&URL.revokeObjectURL(t[e]);const n=a(a({},t),{},{[e]:url});return Ne.current=n,n}),"
    "Me(e,{videoFilename:t,originalVideoBlob:localFile,kinematicsSnapshot:m[e]});return}"
    "const i=m[e],s=async()=>{"
)

PATCHES = (
    ("play iPhone mov under overlay", MOV_OLD, MOV_NEW),
    ("prefer local camera file for overlay", LOCAL_OLD, LOCAL_NEW),
)


def patch_js_text(text: str) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in PATCHES:
        if new in text:
            applied.append(f"already {label}")
            continue
        if old not in text:
            raise SystemExit(f"pattern not found: {label}")
        text = text.replace(old, new, 1)
        applied.append(label)
    return text, applied


def patch_restore_clinic_overlay(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; clinic overlay not restored")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("restore-clinic-overlay:", ", ".join(applied))
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        busted = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            "main.0626212c.js?kin=3",
            html,
        )
        if busted != html:
            idx.write_text(busted, encoding="utf-8")
            print("cache-bust index.html main JS ?kin=3")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_restore_clinic_overlay.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_restore_clinic_overlay(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
