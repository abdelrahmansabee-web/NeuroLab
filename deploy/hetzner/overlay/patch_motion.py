#!/usr/bin/env python3
"""Push the sidebar with GPU transform, keep form layout with padding-left.

Translating a 100% wide topbar/main clips the right edge (More menu, form).
Animate padding-left on those surfaces so content stays on screen. Keep the
sidebar on transform only. Section changes swap instantly — no fade.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

JS_NAME = "main.0626212c.js"
CSS_NAME = "main.17fa781b.css"
KIN = "19"
NL_VERSION = "31.91"
START_URL = "./?v=29.70-pwa"
DEPLOY_VERSION = "29.70"

PAD_EASE = "padding-left 480ms cubic-bezier(0.33, 0, 0.2, 1)"
SIDEBAR_EASE = "transform 480ms cubic-bezier(0.33, 0, 0.2, 1)"
PANEL_EASE = PAD_EASE

TOPBAR_PAD = (
    'at={left:0,width:it,paddingLeft:rt?X:0,paddingTop:Bw,'
    'boxSizing:"border-box",transition:$w}'
)
MAIN_PAD = (
    'style:{width:it,marginLeft:0,paddingLeft:rt?X:0,minWidth:0,'
    'boxSizing:"border-box",transition:$w}'
)
TOPBAR_GPU = (
    'at={left:0,width:it,paddingTop:Bw,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,willChange:"transform",backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
TOPBAR_GPU_NO_WC = (
    'at={left:0,width:it,paddingTop:Bw,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
MAIN_GPU = (
    'style:{width:it,minWidth:0,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,willChange:"transform",backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
MAIN_GPU_NO_WC = (
    'style:{width:it,minWidth:0,transform:rt?"translate3d(".concat(X,"px,0,0)")'
    ':"translate3d(0,0,0)",transition:$w,backfaceVisibility:"hidden",'
    'WebkitBackfaceVisibility:"hidden"}'
)
NAV_INSTANT = (
    "h(t),E.current=null,L(),g(\"idle\"),N.current=!1,C.current=!1,"
    "T.current=t,_(!1),(0,e.startTransition)(()=>l(t))):E.current=t)}"
)
NAV_EXITING = (
    "h(t),E.current=null,L(),F.current=t,N.current=!1,C.current=!1,"
    'T.current=t,_(!0),g("exiting"),S.current=setTimeout(R,280)):E.current=t)}'
)
NAV_DOM_FADE = (
    "h(t),E.current=null,L(),g(\"idle\"),N.current=!1,C.current=!1,"
    "T.current=t,_(!1),(0,e.startTransition)(()=>{var n=document.querySelector("
    '".section-nav-motion");n&&(n.style.transition="opacity 240ms cubic-bezier(0.45, 0, 0.55, 1)"'
    ',n.style.opacity="0"),setTimeout(function(){l(t);requestAnimationFrame(function(){'
    'var n=document.querySelector(".section-nav-motion");n&&(n.style.opacity="1")})},240)}))'
    ":E.current=t)}"
)

JS_PATCHES = (
    (
        "topbar and main ease padding-left, not transform",
        (
            'const $w="transform 820ms cubic-bezier(0.33, 0, 0.2, 1)"',
            'const $w="transform 700ms cubic-bezier(0.45, 0, 0.55, 1)"',
            'const $w="transform 600ms cubic-bezier(0.16, 1, 0.3, 1)"',
            'const $w="padding-left 520ms cubic-bezier(0.22, 1, 0.36, 1)"',
        ),
        f'const $w="{PAD_EASE}"',
    ),
    (
        "topbar uses padding-left so actions stay on screen",
        (
            TOPBAR_GPU,
            TOPBAR_GPU_NO_WC,
        ),
        TOPBAR_PAD,
    ),
    (
        "main uses padding-left so the form is not clipped",
        (
            MAIN_GPU,
            MAIN_GPU_NO_WC,
        ),
        MAIN_PAD,
    ),
    (
        "sidebar keeps a GPU slide",
        (
            'transition:"transform 820ms cubic-bezier(0.33, 0, 0.2, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 700ms cubic-bezier(0.45, 0, 0.55, 1)",willChange:"transform",backfaceVisibility:"hidden"',
            'transition:"transform 700ms cubic-bezier(0.45, 0, 0.55, 1)",backfaceVisibility:"hidden"',
            'transition:"transform 600ms cubic-bezier(0.16, 1, 0.3, 1)",backfaceVisibility:"hidden"',
            'transition:"transform 520ms cubic-bezier(0.22, 1, 0.36, 1)",backfaceVisibility:"hidden"',
        ),
        f'transition:"{SIDEBAR_EASE}",willChange:"transform",backfaceVisibility:"hidden"',
    ),
    (
        "restore reduced-motion skip for unused KS classes",
        (
            'const d=!1,u="exiting"===i&&!d',
        ),
        'const d=h(),u="exiting"===i&&!d',
    ),
    (
        "swap sections instantly, no fade",
        (
            NAV_EXITING,
            NAV_DOM_FADE,
        ),
        NAV_INSTANT,
    ),
    (
        "restore original enter fallback",
        (
            "A.current=setTimeout(()=>{j()},420)",
        ),
        "A.current=setTimeout(()=>{j()},320)",
    ),
)

CSS_PATCHES = (
    (
        "do not clip the page while the sidebar moves",
        (
            "html,body,#root{overflow-x:hidden}.section-pane{overflow:visible}",
        ),
        ".section-pane{overflow:visible}",
    ),
    (
        "restore OS reduce-motion for unused section animations",
        (
            "@media (prefers-reduced-motion:reduce){.nl-motion-layer{transition:none!important}}",
        ),
        "@media (prefers-reduced-motion:reduce){.nl-motion-layer,.section-nav-motion.section-bounce-in,.section-nav-motion.section-bounce-out,.section-nav-motion.section-fade-in,.section-nav-motion.section-fade-out,.section-pane{animation:none!important;transition:none!important}}",
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
            f"main.17fa781b.css?m=7",
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
            notes.append(f"index kin={KIN} css?m=7 nl-version {NL_VERSION}")
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
