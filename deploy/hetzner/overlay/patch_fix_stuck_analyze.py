#!/usr/bin/env python3
"""Unstick Analyze after a reload: clear hung 'analyzing' status and reuse the local video.

PWA reloads drop the in-memory File. Filename stays, status can stay 'analyzing',
so the play button never comes back or toast-only 'select a file first'.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FD_OLD = (
    "JSON.parse(localStorage.getItem(hS));if(e&&\"object\"===typeof e)return e}"
    "catch(e){}return{demographics:{participantId:String(mS())}"
)
FD_NEW = (
    "JSON.parse(localStorage.getItem(hS));if(e&&\"object\"===typeof e){"
    'const t=e.kinematics&&"object"===typeof e.kinematics?e.kinematics:e;'
    '["pre","post","baseline"].forEach(function(n){const r="status_"+n;'
    '"analyzing"===t[r]&&(t[r]="uploaded");"analyzing"===e[r]&&(e[r]="uploaded")});'
    "return e}}"
    "catch(e){}return{demographics:{participantId:String(mS())}"
)

ANALYZE_OLD = (
    'const n=l["".concat(Re(t),"_file")];'
    'if(!n)return void u("Please select a file first","error");'
)
ANALYZE_NEW = (
    'let n=l["".concat(Re(t),"_file")];'
    "if(!(n instanceof Blob)||!n.size){try{const rec=Ce?await H_(Ce,t):null;"
    "n=null!==rec&&void 0!==rec?rec.originalVideoBlob:null}catch(z){n=null}}"
    "if(!(n instanceof Blob)||!n.size){"
    'u("Tap the video card and choose the file again","error");'
    'return void d(a(a({},l),{},{[Oe(t)]:"uploaded"}))}'
    'if(!n.name)n=new File([n],l[Re(t)]||"video.mp4",{type:n.type||"video/mp4"});'
)

CARD_PLAY_OLD = (
    'className:"w-full rounded-lg bg-black mb-1.5",controls:!0,playsInline:!0,muted:!0,autoPlay:!0'
)
CARD_PLAY_NEW = (
    'className:"w-full rounded-lg bg-black mb-1.5",controls:!0,playsInline:!0,muted:!0,autoPlay:!1'
)

PATCHES = (
    ("clear hung analyzing status on reload", FD_OLD, FD_NEW),
    ("analyze from IndexedDB blob if File was dropped", ANALYZE_OLD, ANALYZE_NEW),
    ("do not autoplay camera file on the phase card", CARD_PLAY_OLD, CARD_PLAY_NEW),
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
            "main.0626212c.js?kin=6",
            html,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r"\g<1>31.78",
            updated,
            count=1,
        )
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append("index kin=6 nl-version 31.78")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != "./?v=29.60-pwa":
            data["start_url"] = "./?v=29.60-pwa"
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append("manifest start_url 29.60-pwa")
    return notes


def patch_fix_stuck_analyze(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; stuck-analyze not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("fix-stuck-analyze:", ", ".join(applied))
    notes = patch_pwa_reload(root)
    if notes:
        print("pwa reload:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_fix_stuck_analyze.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_fix_stuck_analyze(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
