#!/usr/bin/env python3
"""Do not block Analyze complete on re-downloading the camera file.

After the job finishes, the live clinic awaited a force /video/ fetch of the
original (often a large iPhone .mov) before writing kinematicsResults. The card
stayed on Analyzing and nothing below it appeared. Use the local File immediately.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WE_OLD = (
    "We=(0,e.useCallback)(async(e,t,n)=>{var r;"
    "const i=(null===t||void 0===t||null===(r=t.name)||void 0===r?void 0:r.toLowerCase())||\"\","
    's=i.endsWith(".csv"),o=i.endsWith(".mp4")||i.endsWith(".webm");'
    "if(n&&(await Ge(e,n,{force:!0}),Ne.current[e]))return!0;"
    "if(Ne.current[e])return!0;"
    "if(t&&!s&&o){const n=URL.createObjectURL(t);"
    "return Ae(t=>{if(t[e])return URL.revokeObjectURL(n),t;"
    "const r=a(a({},t),{},{[e]:n});return Ne.current=r,r}),!0}"
    "return!!n&&(await Ge(e,n),Boolean(Ne.current[e]))},[Ge]);"
)
WE_NEW = (
    "We=(0,e.useCallback)(async(e,t,n)=>{var r;"
    "const i=(null===t||void 0===t||null===(r=t.name)||void 0===r?void 0:r.toLowerCase())||\"\","
    's=i.endsWith(".csv");'
    "if(Ne.current[e])return!0;"
    "if(t&&!s&&t instanceof Blob&&t.size>0){const n=URL.createObjectURL(t);"
    "return Ae(t=>{t[e]&&URL.revokeObjectURL(t[e]);"
    "const r=a(a({},t),{},{[e]:n});return Ne.current=r,r}),!0}"
    "return!!n&&(await Ge(e,n),Boolean(Ne.current[e]))},[Ge]);"
)

AWAIT_OLD = (
    "!i&&A&&await We(t,n,A);"
    "const P=a(a({},S),{},{video_filename:A}),F=a(a({},m),{},{[t]:P});"
    'g(F),K(!0),d(a(a({},l),{},{analysisResults:yk(F),[De(t)]:vk(S),[Oe(t)]:"completed"})),'
    'u("\\u2713 Analysis complete for ".concat(t)'
)
AWAIT_NEW = (
    "const P=a(a({},S),{},{video_filename:A}),F=a(a({},m),{},{[t]:P});"
    'g(F),K(!0),d(a(a({},l),{},{analysisResults:yk(F),[De(t)]:vk(S),[Oe(t)]:"completed"}));'
    "!i&&A&&We(t,n,A).catch(function(){});"
    'u("\\u2713 Analysis complete for ".concat(t)'
)

CARD_OLD = '})]}),p&&(0,Un.jsx)("div",{className:"grid grid-cols-2 gap-1.5"'
CARD_NEW = (
    '})]}),p&&(Se[t.k]||l["".concat(Re(t.k),"_url")])?(0,Un.jsx)("video",{'
    'src:Se[t.k]||l["".concat(Re(t.k),"_url")],'
    'className:"w-full rounded-lg bg-black mb-1.5",controls:!0,playsInline:!0,muted:!0,autoPlay:!0'
    "}):null,"
    'p&&(0,Un.jsx)("div",{className:"grid grid-cols-2 gap-1.5"'
)

PATCHES = (
    ("use local camera file instead of force /video/ download", WE_OLD, WE_NEW),
    ("show results before original-video hydrate", AWAIT_OLD, AWAIT_NEW),
    ("play camera file on the phase card after analyze", CARD_OLD, CARD_NEW),
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
            "main.0626212c.js?kin=5",
            html,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r"\g<1>31.77",
            updated,
            count=1,
        )
        updated = updated.replace("manifest.json?v=29.14", "manifest.json?v=29.59")
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append("index kin=5 nl-version 31.77")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != "./?v=29.59-pwa":
            data["start_url"] = "./?v=29.59-pwa"
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append("manifest start_url 29.59-pwa")
    return notes


def patch_unblock_analyze_ui(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; unblock-analyze-ui not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("unblock-analyze-ui:", ", ".join(applied))
    notes = patch_pwa_reload(root)
    if notes:
        print("pwa reload:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_unblock_analyze_ui.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_unblock_analyze_ui(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
