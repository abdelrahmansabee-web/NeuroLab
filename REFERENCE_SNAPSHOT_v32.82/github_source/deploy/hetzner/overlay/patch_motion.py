#!/usr/bin/env python3
"""Stop sidebar show/hide cutting.

Padding-left on the topbar/main is a layout animation. It fights the GPU
sidebar slide and looks like a cut. Keep the original padded topbar, but do
not animate padding. Only the sidebar slides, on the GPU.

Do not translate a 100% wide topbar/main (clips New/Save/More).
Do not pin the topbar with left/right (changes the chrome).
Section bounce stays the soft 29.72 motion.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

JS_NAME = "main.0626212c.js"
CSS_NAME = "main.17fa781b.css"
KIN = "22"
NL_VERSION = "31.94"
CSS_Q = "10"
START_URL = "./?v=29.73-pwa"
DEPLOY_VERSION = "29.73"

PAD_EASE = "none"
SIDEBAR_EASE = "transform 1100ms cubic-bezier(0.45, 0, 0.55, 1)"
PANEL_EASE = PAD_EASE

TOPBAR_PAD = (
    'at={left:0,width:it,paddingLeft:rt?X:0,paddingTop:Bw,'
    'boxSizing:"border-box",transition:$w}'
)
MAIN_PAD = (
    'style:{width:it,marginLeft:0,paddingLeft:rt?X:0,minWidth:0,'
    'boxSizing:"border-box",transition:$w}'
)
TOPBAR_PINNED = (
    'at={left:rt?X:0,right:0,width:"auto",paddingTop:Bw,'
    'boxSizing:"border-box",transition:$w}'
)
MAIN_PINNED = (
    'style:{marginLeft:rt?X:0,width:"auto",minWidth:0,'
    'boxSizing:"border-box",transition:$w}'
)
TOPBAR_GPU = (
    'at={left:0,width:it,paddingTop:Bw,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,willChange:"transform",backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
MAIN_GPU = (
    'style:{width:it,minWidth:0,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,willChange:"transform",backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
NAV_SOFT = (
    "h(t),E.current=null,L(),F.current=t,N.current=!1,C.current=!1,"
    'T.current=t,_(!0),g("exiting"),S.current=setTimeout(R,320)):E.current=t)}'
)
NAV_BOUNCE_180 = (
    "h(t),E.current=null,L(),F.current=t,N.current=!1,C.current=!1,"
    'T.current=t,_(!0),g("exiting"),S.current=setTimeout(R,180)):E.current=t)}'
)
NAV_EXITING_280 = (
    "h(t),E.current=null,L(),F.current=t,N.current=!1,C.current=!1,"
    'T.current=t,_(!0),g("exiting"),S.current=setTimeout(R,280)):E.current=t)}'
)
NAV_INSTANT = (
    "h(t),E.current=null,L(),g(\"idle\"),N.current=!1,C.current=!1,"
    "T.current=t,_(!1),(0,e.startTransition)(()=>l(t))):E.current=t)}"
)

JS_PATCHES = (
    (
        "do not animate padding with the GPU sidebar",
        (
            'const $w="padding-left 600ms cubic-bezier(0.33, 0, 0.2, 1)"',
            'const $w="left 600ms cubic-bezier(0.33, 0, 0.2, 1),margin-left 600ms cubic-bezier(0.33, 0, 0.2, 1)"',
            'const $w="padding-left 480ms cubic-bezier(0.33, 0, 0.2, 1)"',
            'const $w="padding-left 520ms cubic-bezier(0.22, 1, 0.36, 1)"',
            'const $w="transform 820ms cubic-bezier(0.33, 0, 0.2, 1)"',
            'const $w="transform 700ms cubic-bezier(0.45, 0, 0.55, 1)"',
        ),
        f'const $w="{PAD_EASE}"',
    ),
    (
        "restore the original padded topbar",
        (
            TOPBAR_PINNED,
            TOPBAR_GPU,
        ),
        TOPBAR_PAD,
    ),
    (
        "restore padded main layout",
        (
            MAIN_PINNED,
            MAIN_GPU,
        ),
        MAIN_PAD,
    ),
    (
        "sidebar GPU slide only, slow ease-in-out",
        (
            'transition:"transform 600ms cubic-bezier(0.33, 0, 0.2, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 480ms cubic-bezier(0.33, 0, 0.2, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 820ms cubic-bezier(0.33, 0, 0.2, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 700ms cubic-bezier(0.45, 0, 0.55, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 520ms cubic-bezier(0.22, 1, 0.36, 1)",backfaceVisibility:"hidden"',
        ),
        f'transition:"{SIDEBAR_EASE}",willChange:"transform",backfaceVisibility:"hidden"',
    ),
    (
        "keep section motion even if the OS asks for reduced motion",
        (
            'const d=h(),u="exiting"===i&&!d',
            'const d=!1,u="exiting"===i&&!d',
        ),
        'const d=!1,u="exiting"===i&&!d',
    ),
    (
        "play a softer bounce when changing sections",
        (
            NAV_BOUNCE_180,
            NAV_EXITING_280,
            NAV_INSTANT,
        ),
        NAV_SOFT,
    ),
    (
        "keep enter fallback in sync with the slower bounce",
        (
            "A.current=setTimeout(()=>{j()},480)",
            "A.current=setTimeout(()=>{j()},420)",
            "A.current=setTimeout(()=>{j()},320)",
        ),
        "A.current=setTimeout(()=>{j()},760)",
    ),
)

BOUNCE_OUT = (
    "@keyframes nl-bounce-out{0%{opacity:1;transform:translateZ(0)}"
    "to{opacity:0;transform:translate3d(0,-4px,0)}}"
)
BOUNCE_IN = (
    "@keyframes nl-bounce-in{0%{opacity:0;transform:translate3d(0,8px,0)}"
    "to{opacity:1;transform:translateZ(0)}}"
)
BOUNCE_OUT_SNappy = (
    "@keyframes nl-bounce-out{0%{opacity:1;transform:translateZ(0)}"
    "to{opacity:0;transform:translate3d(0,-8px,0)}}"
)
BOUNCE_IN_SNappy = (
    "@keyframes nl-bounce-in{0%{opacity:0;transform:translate3d(0,14px,0)}"
    "to{opacity:1;transform:translateZ(0)}}"
)
MOBILE_OUT = (
    "@keyframes nl-mobile-fade-out{0%{opacity:1;transform:translateZ(0)}"
    "to{opacity:0;transform:translate3d(0,-4px,0)}}"
)
MOBILE_IN = (
    "@keyframes nl-mobile-fade-in{0%{opacity:0;transform:translate3d(0,8px,0)}"
    "to{opacity:1;transform:translateZ(0)}}"
)
MOBILE_OUT_SNappy = (
    "@keyframes nl-mobile-fade-out{0%{opacity:1;transform:translateZ(0)}"
    "to{opacity:0;transform:translate3d(0,-6px,0)}}"
)
MOBILE_IN_SNappy = (
    "@keyframes nl-mobile-fade-in{0%{opacity:0;transform:translate3d(0,12px,0)}"
    "to{opacity:1;transform:translateZ(0)}}"
)

CSS_PATCHES = (
    (
        "section bounce timing",
        (
            "--section-bounce-out-ms:140ms;--section-bounce-in-ms:420ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.34,1.4,0.64,1)",
            "--section-bounce-out-ms:200ms;--section-bounce-in-ms:360ms;--section-bounce-out-ease:cubic-bezier(0.4,0,0.2,1);--section-bounce-in-ease:cubic-bezier(0.33,0,0.2,1)",
            "--section-bounce-out-ms:280ms;--section-bounce-in-ms:420ms;--section-bounce-out-ease:cubic-bezier(0.4,0,1,1);--section-bounce-in-ease:cubic-bezier(0.22,1,0.36,1)",
        ),
        "--section-bounce-out-ms:280ms;--section-bounce-in-ms:700ms;--section-bounce-out-ease:cubic-bezier(0.4,0,0.2,1);--section-bounce-in-ease:cubic-bezier(0.16,1,0.3,1)",
    ),
    (
        "mobile bounce timing",
        (
            "--mobile-fade-out-ms:140ms;--mobile-fade-in-ms:420ms;--mobile-fade-ease:cubic-bezier(0.34,1.4,0.64,1)",
            "--mobile-fade-out-ms:200ms;--mobile-fade-in-ms:360ms;--mobile-fade-ease:cubic-bezier(0.33,0,0.2,1)",
            "--mobile-fade-out-ms:240ms;--mobile-fade-in-ms:360ms;--mobile-fade-ease:cubic-bezier(0.22,1,0.36,1)",
        ),
        "--mobile-fade-out-ms:280ms;--mobile-fade-in-ms:700ms;--mobile-fade-ease:cubic-bezier(0.16,1,0.3,1)",
    ),
    (
        "mobile fade mount starts below",
        (
            ".section-transition-host-mobile .section-fade-mount{opacity:0;transform:translate3d(0,12px,0);pointer-events:none}",
            ".section-transition-host-mobile .section-fade-mount{opacity:0;pointer-events:none}",
            ".section-transition-host-mobile .section-fade-mount{opacity:0;transform:translate3d(0,10px,0);pointer-events:none}",
        ),
        ".section-transition-host-mobile .section-fade-mount{opacity:0;transform:translate3d(0,8px,0);pointer-events:none}",
    ),
    (
        "mobile fade keyframes bounce",
        (
            MOBILE_OUT_SNappy + MOBILE_IN_SNappy,
            "@keyframes nl-mobile-fade-out{0%{opacity:1}to{opacity:0}}@keyframes nl-mobile-fade-in{0%{opacity:0}to{opacity:1}}",
            "@keyframes nl-mobile-fade-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-8px,0)}}@keyframes nl-mobile-fade-in{0%{opacity:0;transform:translate3d(0,10px,0)}to{opacity:1;transform:translateZ(0)}}",
        ),
        MOBILE_OUT + MOBILE_IN,
    ),
    (
        "desktop bounce mount starts below",
        (
            ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0;transform:translate3d(0,14px,0)}",
            ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0}",
            ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0;transform:translate3d(0,12px,0)}",
        ),
        ".section-nav-motion.section-bounce-mount:not(.section-bounce-in){pointer-events:none;opacity:0;transform:translate3d(0,8px,0)}",
    ),
    (
        "desktop bounce keyframes",
        (
            BOUNCE_OUT_SNappy + BOUNCE_IN_SNappy,
            "@keyframes nl-bounce-out{0%{opacity:1}to{opacity:0}}@keyframes nl-bounce-in{0%{opacity:0}to{opacity:1}}",
            "@keyframes nl-bounce-out{0%{opacity:1;transform:translateZ(0)}to{opacity:0;transform:translate3d(0,-10px,0)}}@keyframes nl-bounce-in{0%{opacity:0;transform:translate3d(0,12px,0)}to{opacity:1;transform:translateZ(0)}}",
        ),
        BOUNCE_OUT + BOUNCE_IN,
    ),
    (
        "section will-change transform and opacity",
        (
            ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:transform,opacity}",
            ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:opacity}",
            ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:transform}",
        ),
        ".section-transition-host:not(.section-transition-host-mobile).section-transition-animating .section-nav-motion{will-change:transform,opacity}",
    ),
    (
        "do not let OS reduce-motion kill the bounce",
        (
            "@media (prefers-reduced-motion:reduce){.nl-motion-layer{transition:none!important}}",
            "@media (prefers-reduced-motion:reduce){.nl-motion-layer,.section-nav-motion.section-bounce-in,.section-nav-motion.section-bounce-out,.section-nav-motion.section-fade-in,.section-nav-motion.section-fade-out,.section-pane{animation:none!important;transition:none!important}}",
        ),
        "@media (prefers-reduced-motion:reduce){.nl-motion-layer{transition:none!important}}",
    ),
)


def _apply_pairs(
    text: str, pairs: tuple[tuple[str, str | tuple[str, ...], str], ...]
) -> tuple[str, list[str]]:
    applied: list[str] = []
    for label, olds, new in pairs:
        if isinstance(olds, str):
            olds = (olds,)
        matched = False
        for old in olds:
            if old != new and old in text:
                text = text.replace(old, new, 1)
                applied.append(label)
                matched = True
                break
        if matched:
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
            f"main.17fa781b.css?m={CSS_Q}",
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
            notes.append(f"index kin={KIN} css?m={CSS_Q} nl-version {NL_VERSION}")
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
            'DEPLOY_VERSION = "29.73"',
            'DEPLOY_VERSION = "29.72"',
            'DEPLOY_VERSION = "29.71"',
            'DEPLOY_VERSION = "29.70"',
            'DEPLOY_VERSION = "29.69"',
            'DEPLOY_VERSION = "29.68"',
            'DEPLOY_VERSION = "29.67"',
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
