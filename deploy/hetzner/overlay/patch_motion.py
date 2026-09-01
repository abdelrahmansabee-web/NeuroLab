#!/usr/bin/env python3
"""GPU-only sidebar push and a short opacity dissolve between sections.

Padding/width/margin animations reflow every frame. A snappy ease-out still
looks like a cut because most of the travel happens in the first 100ms.
Slide the sidebar, topbar, and main together with translate3d and a slow
ease-in-out. Section changes fade only — no bounce or slide.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

JS_NAME = "main.0626212c.js"
CSS_NAME = "main.17fa781b.css"
KIN = "16"
NL_VERSION = "31.88"
START_URL = "./?v=29.67-pwa"
DEPLOY_VERSION = "29.67"

PANEL_EASE = "transform 700ms cubic-bezier(0.45, 0, 0.55, 1)"

JS_PATCHES = (
    (
        "panel motion uses a slow transform ease",
        (
            'const $w="padding-left 520ms cubic-bezier(0.22, 1, 0.36, 1)"',
            'const $w="transform 600ms cubic-bezier(0.16, 1, 0.3, 1)"',
        ),
        f'const $w="{PANEL_EASE}"',
    ),
    (
        "topbar slides with translate3d",
        (
            'at={left:0,width:it,paddingLeft:rt?X:0,paddingTop:Bw,boxSizing:"border-box",transition:$w}',
            'at={left:0,width:it,paddingTop:Bw,transform:rt?"translate3d(".concat(X,"px,0,0)"):"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",WebkitBackfaceVisibility:"hidden"}',
        ),
        'at={left:0,width:it,paddingTop:Bw,transform:rt?"translate3d(".concat(X,"px,0,0)"):"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",WebkitBackfaceVisibility:"hidden"}',
    ),
    (
        "main slides with translate3d",
        (
            'style:{width:it,marginLeft:0,paddingLeft:rt?X:0,minWidth:0,boxSizing:"border-box",transition:$w}',
            'style:{width:it,minWidth:0,transform:rt?"translate3d(".concat(X,"px,0,0)"):"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",WebkitBackfaceVisibility:"hidden"}',
        ),
        'style:{width:it,minWidth:0,transform:rt?"translate3d(".concat(X,"px,0,0)"):"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",WebkitBackfaceVisibility:"hidden"}',
    ),
    (
        "sidebar uses the same transform ease",
        (
            'transition:"transform 520ms cubic-bezier(0.22, 1, 0.36, 1)"',
            'transition:"transform 600ms cubic-bezier(0.16, 1, 0.3, 1)"',
        ),
        f'transition:"{PANEL_EASE}"',
    ),
    (
        "do not skip section fades for reduced-motion",
        (
            'const d=h(),u="exiting"===i&&!d',
        ),
        'const d=!1,u="exiting"===i&&!d',
    ),
    (
        "fade the current section before swapping content",
        (
            "T.current=t,_(!1),(0,e.startTransition)(()=>l(t))):E.current=t)}",
        ),
        "T.current=t,_(!1),(0,e.startTransition)(()=>{var n=document.querySelector(\".section-nav-motion\");n&&(n.style.transition=\"opacity 240ms cubic-bezier(0.45, 0, 0.55, 1)\",n.style.opacity=\"0\"),setTimeout(function(){l(t);requestAnimationFrame(function(){var n=document.querySelector(\".section-nav-motion\");n&&(n.style.opacity=\"1\")})},240)})):E.current=t)}",
    ),
)

CSS_PATCHES = (
    (
        "section timing",
        (
            "--section-bounce-out-ms:280ms;--section-bounce-in-ms:420ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
            "--section-bounce-out-ms:140ms;--section-bounce-in-ms:220ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
            "--section-bounce-out-ms:200ms;--section-bounce-in-ms:280ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
        ),
        "--section-bounce-out-ms:240ms;--section-bounce-in-ms:320ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
    ),
    (
        "mobile fade timing",
        (
            "--mobile-fade-out-ms:240ms;--mobile-fade-in-ms:360ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
            "--mobile-fade-out-ms:140ms;--mobile-fade-in-ms:220ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
            "--mobile-fade-out-ms:200ms;--mobile-fade-in-ms:280ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
        ),
        "--mobile-fade-out-ms:240ms;--mobile-fade-in-ms:320ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
    ),
    (
        "mobile fade mount opacity",
        (
            ".section-transition-host-mobile .section-fade-mount{opacity:0;transform:translate3d(0,10px,0);pointer-events:none}",
            ".section-transition-host-mobile .section-fade-mount{opacity:0;pointer-events:none}",
        ),
        ".section-transition-host-mobile .section-fade-mount{opacity:0;pointer-events:none}",
    ),
    (
        "mobile fade keyframes",
        (
            "@keyframes nl-mobile-fade-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-8px,0)}}@keyframes nl-mobile-fade-in{0%{opacity:0;transform:translate3d(0,10px,0)}to{opacity:1;transform:translateZ(0)}}",
            "@keyframes nl-mobile-fade-out{0%{opacity:1}to{opacity:0}}@keyframes nl-mobile-fade-in{0%{opacity:0}to{opacity:1}}",
        ),
        "@keyframes nl-mobile-fade-out{0%{opacity:1}to{opacity:0}}@keyframes nl-mobile-fade-in{0%{opacity:0}to{opacity:1}}",
    ),
    (
        "desktop bounce mount",
        (
            ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0;transform:translate3d(0,12px,0)}",
            ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0}",
        ),
        ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0}",
    ),
    (
        "desktop bounce keyframes",
        (
            "@keyframes nl-bounce-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-10px,0)}}@keyframes nl-bounce-in{0%{opacity:0;transform:translate3d(0,12px,0)}to{opacity:1;transform:translateZ(0)}}",
            "@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}@keyframes nl-bounce-in{0%{opacity:0}to{opacity:1}}",
        ),
        "@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}@keyframes nl-bounce-in{0%{opacity:0}to{opacity:1}}",
    ),
    (
        "section will-change opacity",
        (
            ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:transform}",
            ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:opacity}",
        ),
        ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:opacity}",
    ),
    (
        "clip horizontal overflow while panels slide",
        (
            ".section-pane{overflow:visible}",
            "html,body,#root{overflow-x:hidden}.section-pane{overflow:visible}",
        ),
        "html,body,#root{overflow-x:hidden}.section-pane{overflow:visible}",
    ),
)


def _apply_pairs(
    text: str, pairs: tuple[tuple[str, str | tuple[str, ...], str], ...]
) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, olds, new in pairs:
        if isinstance(olds, str):
            olds = (olds,)
        if new in text:
            applied.append(f"already {label}")
            continue
        for old in olds:
            if old in text:
                text = text.replace(old, new, 1)
                applied.append(label)
                break
        else:
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
            f"main.17fa781b.css?m=4",
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
            notes.append(f"index kin={KIN} css?m=4 nl-version {NL_VERSION}")
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
            'DEPLOY_VERSION = "29.66"',
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
