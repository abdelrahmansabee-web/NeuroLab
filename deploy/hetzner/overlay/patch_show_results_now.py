#!/usr/bin/env python3
"""Show kinematic numbers and the camera video as soon as analysis finishes.

The live clinic hid the results table until overlay-data JSON arrived, hid the
iPad card metrics at sm+, left autoPlay/autoRender off, and swapped the player
for a spinner while overlay-data rebuilt on cpu-basic. After Analyze the screen
looked unchanged: filename + play, nothing below.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

TABLE_GATE_OLD = (
    "(0,e.useEffect)(()=>{const e=Ie.filter(e=>m[e.k]);"
    "if(0===e.length)return void K(!1);"
    "const t=e.some(e=>!le[e.k]&&!Xe[e.k]);K(!t)},[m,Xe,le])"
)
TABLE_GATE_NEW = (
    "(0,e.useEffect)(()=>{const e=Ie.filter(e=>m[e.k]);K(e.length>0)},[m])"
)

UV_HIDE_START_OLD = (
    'B(t=>a(a({},t),{},{[e]:"generating_unified"})),K(!1);try{const t=new FormData'
)
UV_HIDE_START_NEW = (
    'B(t=>a(a({},t),{},{[e]:"generating_unified"}));try{const t=new FormData'
)

UV_HIDE_READY_OLD = (
    'u("Unified validation video ready","success"),K(!1),void B'
)
UV_HIDE_READY_NEW = (
    'u("Unified validation video ready","success"),K(!0),void B'
)

AUTOPLAY_OLD = "autoPlay:!1,autoRender:!1"
AUTOPLAY_NEW = "autoPlay:!0,autoRender:!0"

COMPLETE_OLD = (
    "g(F),d(a(a({},l),{},{analysisResults:yk(F),[De(t)]:vk(S),[Oe(t)]:\"completed\"}))"
)
COMPLETE_NEW = (
    "g(F),K(!0),d(a(a({},l),{},{analysisResults:yk(F),[De(t)]:vk(S),[Oe(t)]:\"completed\"}))"
)

CARD_METRICS_OLD = 'p&&(0,Un.jsx)("div",{className:"sm:hidden grid grid-cols-2 gap-1.5"'
CARD_METRICS_NEW = 'p&&(0,Un.jsx)("div",{className:"grid grid-cols-2 gap-1.5"'

VALIDATION_ID_OLD = (
    'Object.keys(m).length>0&&(0,Un.jsxs)(zk,{className:"p-4 sm:p-5",children:['
    '(0,Un.jsxs)("div",{className:"flex items-center justify-between mb-3 gap-2",children:['
    '(0,Un.jsx)("p",{className:"text-sm font-extrabold text-white/80",children:"Validation Video"})'
)
VALIDATION_ID_NEW = (
    'Object.keys(m).length>0&&(0,Un.jsxs)(zk,{id:"kin-validation-video",className:"p-4 sm:p-5",children:['
    '(0,Un.jsxs)("div",{className:"flex items-center justify-between mb-3 gap-2",children:['
    '(0,Un.jsx)("p",{className:"text-sm font-extrabold text-white/80",children:"Validation Video"})'
)

PREPARING_OLD = (
    '(0,Un.jsxs)("div",{className:"aspect-video rounded-lg bg-black/50 flex flex-col '
    'items-center justify-center text-center p-3",children:['
    '(0,Un.jsx)("p",{className:"text-[11px] text-white/50 mb-2",'
    'children:"Preparing validation overlay\\u2026"}),'
    '(0,Un.jsx)("div",{className:"w-8 h-8 border-2 border-white/20 border-t-white/60 '
    'rounded-full animate-spin"})]})'
)
PREPARING_NEW = (
    'Se[e.k]?(0,Un.jsxs)("div",{className:"rounded-lg overflow-hidden bg-black",children:['
    '(0,Un.jsx)("video",{src:Se[e.k],className:"w-full rounded-lg bg-black",'
    "controls:!0,autoPlay:!0,muted:!0,playsInline:!0}),"
    '(0,Un.jsx)("p",{className:"text-[11px] text-white/50 mt-2 mb-1 text-center",'
    'children:"Preparing skeleton overlay\\u2026"})]}):'
    '(0,Un.jsxs)("div",{className:"aspect-video rounded-lg bg-black/50 flex flex-col '
    'items-center justify-center text-center p-3",children:['
    '(0,Un.jsx)("p",{className:"text-[11px] text-white/50 mb-2",'
    'children:"Preparing validation overlay\\u2026"}),'
    '(0,Un.jsx)("div",{className:"w-8 h-8 border-2 border-white/20 border-t-white/60 '
    'rounded-full animate-spin"})]})'
)

PATCHES = (
    ("show results table as soon as analysis exists", TABLE_GATE_OLD, TABLE_GATE_NEW),
    ("do not hide table when UV starts", UV_HIDE_START_OLD, UV_HIDE_START_NEW),
    ("keep table visible when UV finishes", UV_HIDE_READY_OLD, UV_HIDE_READY_NEW),
    ("autoplay overlay and auto-export for Drive", AUTOPLAY_OLD, AUTOPLAY_NEW),
    ("show table immediately on analyze complete", COMPLETE_OLD, COMPLETE_NEW),
    ("show metric preview on iPad cards", CARD_METRICS_OLD, CARD_METRICS_NEW),
    ("mark validation video section for scroll", VALIDATION_ID_OLD, VALIDATION_ID_NEW),
    ("play camera file while overlay JSON loads", PREPARING_OLD, PREPARING_NEW),
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


def patch_show_results_now(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / "main.0626212c.js"
    if not js.is_file():
        print("WARN: frontend bundle missing; show-results-now not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("show-results-now:", ", ".join(applied))
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        busted = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            "main.0626212c.js?kin=4",
            html,
        )
        if busted != html:
            idx.write_text(busted, encoding="utf-8")
            print("cache-bust index.html main JS ?kin=4")
        html2 = idx.read_text(encoding="utf-8")
        versioned = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            r'\g<1>31.76',
            html2,
            count=1,
        )
        if versioned != html2:
            idx.write_text(versioned, encoding="utf-8")
            print("bumped nl-version to 31.76 for PWA reload")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_show_results_now.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_show_results_now(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
