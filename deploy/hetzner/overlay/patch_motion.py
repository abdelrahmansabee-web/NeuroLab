#!/usr/bin/env python3
"""Smooth sidebar show/hide and a light fade/slide between sections.

Live clinic animates width between 100% and calc(100% - Npx). Browsers cannot
interpolate those, so the layout jumps. Keep width at 100% and ease padding-left
in pixels instead. Section keyframes currently move 3–5px with almost no opacity
change; give them a real fade and a short vertical slide.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

JS_NAME = "main.0626212c.js"
CSS_NAME = "main.17fa781b.css"
KIN = "12"
NL_VERSION = "31.84"
START_URL = "./?v=29.66-pwa"
DEPLOY_VERSION = "29.66"

LAYOUT_EASE = "padding-left 520ms cubic-bezier(0.22, 1, 0.36, 1)"
SIDEBAR_EASE = "transform 520ms cubic-bezier(0.22, 1, 0.36, 1)"

JS_PATCHES = (
    (
        "sidebar layout eases padding-left",
        'const $w="left 320ms cubic-bezier(0.32, 0.72, 0, 1), width 320ms cubic-bezier(0.32, 0.72, 0, 1), margin-left 320ms cubic-bezier(0.32, 0.72, 0, 1)"',
        f'const $w="{LAYOUT_EASE}"',
    ),
    (
        "keep main width at 100%",
        'it=rt?"calc(100% - ".concat(X,"px)"):"100%"',
        'it="100%"',
    ),
    (
        "topbar pads instead of jumping left/width",
        "at={left:rt?X:0,width:it,paddingTop:Bw,transition:$w}",
        'at={left:0,width:it,paddingLeft:rt?X:0,paddingTop:Bw,boxSizing:"border-box",transition:$w}',
    ),
    (
        "main pads instead of jumping margin/width",
        "style:{width:it,marginLeft:rt?X:0,minWidth:0,transition:$w}",
        'style:{width:it,marginLeft:0,paddingLeft:rt?X:0,minWidth:0,boxSizing:"border-box",transition:$w}',
    ),
    (
        "sidebar transform eases longer",
        'transition:"transform 320ms cubic-bezier(0.32, 0.72, 0, 1)"',
        f'transition:"{SIDEBAR_EASE}"',
    ),
    (
        "do not snap-hide mobile topbar",
        '.concat(!V&&U?"hidden":"")',
        "",
    ),
)

CSS_PATCHES = (
    (
        "section timing",
        "--section-bounce-out-ms:150ms;--section-bounce-in-ms:280ms;--section-bounce-out-ease:cubic-bezier(0.4,0,0.2,1);--section-bounce-in-ease:cubic-bezier(0.25,0.9,0.35,1)",
        "--section-bounce-out-ms:280ms;--section-bounce-in-ms:420ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
    ),
    (
        "mobile fade timing",
        "--mobile-fade-out-ms:140ms;--mobile-fade-in-ms:180ms;--mobile-fade-ease:cubic-bezier(0.4,0,0.2,1)",
        "--mobile-fade-out-ms:240ms;--mobile-fade-in-ms:360ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
    ),
    (
        "mobile fade mount opacity",
        ".section-transition-host-mobile .section-fade-mount{opacity:.94;pointer-events:none}",
        ".section-transition-host-mobile .section-fade-mount{opacity:0;transform:translate3d(0,10px,0);pointer-events:none}",
    ),
    (
        "mobile fade keyframes",
        "@keyframes nl-mobile-fade-out{0%{opacity:1}to{opacity:.94}}@keyframes nl-mobile-fade-in{0%{opacity:.94}to{opacity:1}}",
        "@keyframes nl-mobile-fade-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-8px,0)}}@keyframes nl-mobile-fade-in{0%{opacity:0;transform:translate3d(0,10px,0)}to{opacity:1;transform:translateZ(0)}}",
    ),
    (
        "desktop bounce mount",
        ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;transform:translate3d(0,5px,0)}",
        ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0;transform:translate3d(0,12px,0)}",
    ),
    (
        "desktop bounce keyframes",
        "@keyframes nl-bounce-out{0%{transform:translateZ(0)}to{transform:translate3d(0,3px,0)}}@keyframes nl-bounce-in{0%{transform:translate3d(0,5px,0)}to{transform:translateZ(0)}}",
        "@keyframes nl-bounce-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-10px,0)}}@keyframes nl-bounce-in{0%{opacity:0;transform:translate3d(0,12px,0)}to{opacity:1;transform:translateZ(0)}}",
    ),
)


def _apply_pairs(text: str, pairs: tuple[tuple[str, str, str], ...]) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, old, new in pairs:
        if old in text:
            text = text.replace(old, new, 1)
            applied.append(label)
            continue
        if new in text:
            applied.append(f"already {label}")
            continue
        raise SystemExit(f"pattern not found: {label}")
    return text, applied


def patch_js_text(text: str) -> tuple[str, list[str]]:
    return _apply_pairs(text, JS_PATCHES)


def patch_css_text(text: str) -> tuple[str, list[str]]:
    return _apply_pairs(text, CSS_PATCHES)


def patch_pwa_reload(root: Path) -> list[str]:
    notes: list[str] = []
    idx = root / "frontend" / "build" / "index.html"
    if idx.is_file():
        html = idx.read_text(encoding="utf-8")
        updated = re.sub(
            r"main\.0626212c\.js(?:\?[^\"']*)?",
            f"main.0626212c.js?kin={KIN}",
            html,
        )
        updated = re.sub(
            r"main\.17fa781b\.css(?:\?[^\"']*)?",
            f"main.17fa781b.css?m=1",
            updated,
        )
        updated = re.sub(
            r'(meta name="nl-version" content=")[^"]+',
            rf"\g<1>{NL_VERSION}",
            updated,
            count=1,
        )
        if updated != html:
            idx.write_text(updated, encoding="utf-8")
            notes.append(f"index kin={KIN} css?m=1 nl-version {NL_VERSION}")
    manifest = root / "frontend" / "build" / "manifest.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return notes
        if data.get("start_url") != START_URL:
            data["start_url"] = START_URL
            manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            notes.append(f"manifest start_url {START_URL.split('=')[-1]}")
    return notes


def patch_deploy_version(root: Path) -> list[str]:
    notes: list[str] = []
    target = f'DEPLOY_VERSION = "{DEPLOY_VERSION}"'
    for rel in ("main.py", "analyze_job_runner.py"):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old in (
            'DEPLOY_VERSION = "29.65"',
            'DEPLOY_VERSION = "29.64"',
            'DEPLOY_VERSION = "29.63"',
            'DEPLOY_VERSION = "29.62"',
            'DEPLOY_VERSION = "29.61"',
        ):
            updated = updated.replace(old, target)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            notes.append(f"{rel} {DEPLOY_VERSION}")
    return notes


def patch_motion(root: Path) -> int:
    js = root / "frontend" / "build" / "static" / "js" / JS_NAME
    if not js.is_file():
        print("WARN: frontend bundle missing; motion not patched")
        return 0
    original = js.read_text(encoding="utf-8", errors="replace")
    updated, applied = patch_js_text(original)
    if updated != original:
        js.write_text(updated, encoding="utf-8")
    print("motion-js:", ", ".join(applied))

    css = root / "frontend" / "build" / "static" / "css" / CSS_NAME
    if css.is_file():
        css_original = css.read_text(encoding="utf-8", errors="replace")
        css_updated, css_applied = patch_css_text(css_original)
        if css_updated != css_original:
            css.write_text(css_updated, encoding="utf-8")
        print("motion-css:", ", ".join(css_applied))
    else:
        print("WARN: frontend CSS missing; section motion not patched")

    notes = patch_pwa_reload(root)
    notes.extend(patch_deploy_version(root))
    if notes:
        print("motion extra:", ", ".join(notes))
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_motion.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_motion(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
