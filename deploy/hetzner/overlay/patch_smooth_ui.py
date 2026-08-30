#!/usr/bin/env python3
"""Inject compositor-friendly clinic CSS/JS. Does not change pose/analysis quality."""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

CSS_VER = "4"
LINK = f'<link rel="stylesheet" href="/clinic_smooth.css?v={CSS_VER}"/>'
BOOT = "<script>document.documentElement.classList.add('nl-clinic-smooth')</script>"
SCRIPT = f'<script src="/clinic_smooth.js?v={CSS_VER}"></script>'
HREF_RE = re.compile(r'href="/clinic_smooth\.css(?:\?v=\d+)?"')
SRC_RE = re.compile(r'src="/clinic_smooth\.js(?:\?v=\d+)?"')
BACKDROP_RE = re.compile(
    r"(-webkit-)?backdrop-filter:\s*blur\([^)]+\)(?:\s+saturate\([^)]+\))?\s*(!important)?"
)
TAILWIND_BLUR = (
    "backdrop-blur-3xl",
    "backdrop-blur-2xl",
    "backdrop-blur-xl",
    "backdrop-blur-lg",
    "backdrop-blur-md",
    "backdrop-blur-sm",
    "backdrop-saturate-[2.25]",
    "backdrop-saturate-[1.1]",
)
BG_FILTER_OLD = 'filter:"blur(24px) brightness(0.55) saturate(0.80)",transform:"scale(1.08)"'
BG_FILTER_NEW = 'filter:"none",transform:"none"'


def _backdrop_repl(match: re.Match[str]) -> str:
    prefix = match.group(1) or ""
    important = " !important" if match.group(2) else ""
    return f"{prefix}backdrop-filter: none{important}"


def patch_clinic_js(text: str) -> tuple[str, int]:
    hits = 0
    if BG_FILTER_OLD in text:
        n = text.count(BG_FILTER_OLD)
        text = text.replace(BG_FILTER_OLD, BG_FILTER_NEW)
        hits += n
    if '"/bg.jpg"' in text:
        n = text.count('"/bg.jpg"')
        text = text.replace('"/bg.jpg"', '"/bg_soft.jpg"')
        hits += n
    text, n = BACKDROP_RE.subn(_backdrop_repl, text)
    hits += n
    for cls in TAILWIND_BLUR:
        if cls in text:
            text = text.replace(cls, "")
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
        updated, hits = patch_clinic_js(original)
        if hits:
            path.write_text(updated, encoding="utf-8")
            print(f"patched {path.name} ({hits} replacements)")
            patched += 1
        else:
            print(f"unchanged {path.name}")
    return patched


def _copy(overlay: Path, name: str, *dests: Path) -> None:
    src = overlay / name
    if not src.is_file():
        raise FileNotFoundError(src)
    for dest in dests:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def patch_smooth_ui(root: Path) -> int:
    overlay = Path(__file__).resolve().parent
    try:
        _copy(
            overlay,
            "clinic_smooth.css",
            root / "frontend" / "build" / "clinic_smooth.css",
            root / "clinic_smooth.css",
        )
        _copy(
            overlay,
            "clinic_smooth.js",
            root / "frontend" / "build" / "clinic_smooth.js",
            root / "clinic_smooth.js",
        )
        _copy(
            overlay,
            "bg_soft.jpg",
            root / "frontend" / "build" / "bg_soft.jpg",
            root / "bg_soft.jpg",
        )
    except FileNotFoundError as exc:
        print(f"error: missing {exc}", file=sys.stderr)
        return 1
    print("copied clinic_smooth.css, clinic_smooth.js, bg_soft.jpg")

    idx = root / "frontend" / "build" / "index.html"
    if not idx.is_file():
        print("WARN: index.html missing")
        return 0
    text = idx.read_text(encoding="utf-8", errors="replace")
    if HREF_RE.search(text):
        text = HREF_RE.sub(f'href="/clinic_smooth.css?v={CSS_VER}"', text, count=1)
    elif "clinic_smooth.css" not in text:
        text = text.replace("</head>", LINK + "</head>", 1) if "</head>" in text else LINK + text
    if SRC_RE.search(text):
        text = SRC_RE.sub(f'src="/clinic_smooth.js?v={CSS_VER}"', text, count=1)
    elif "clinic_smooth.js" not in text:
        text = text.replace("</head>", SCRIPT + "</head>", 1) if "</head>" in text else SCRIPT + text
    text, n = re.subn(
        r'(src="/static/js/main\.[a-zA-Z0-9]+\.js)(?:\?v=\d+)?(")',
        rf"\1?v={CSS_VER}\2",
        text,
        count=1,
    )
    if n:
        print("cache-busted main.js")
    if "nl-clinic-smooth" not in text:
        text = text.replace("<head>", "<head>" + BOOT, 1) if "<head>" in text else BOOT + text
    idx.write_text(text, encoding="utf-8")
    print("wired clinic_smooth assets into index.html")
    patch_build_js(root)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if len(argv) != 2:
        print("usage: patch_smooth_ui.py /opt/neurolab", file=sys.stderr)
        return 2
    return patch_smooth_ui(Path(argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
