#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copy the 14 Sep 2026 validation-overlay snapshot back into a checkout."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SNAP = Path(__file__).resolve().parent


def copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"  {src.relative_to(SNAP)} -> {dest}")


def restore_hf(hf_root: Path) -> int:
    if not (hf_root / "main.py").is_file():
        print(f"error: {hf_root} is not an HF Space checkout (main.py missing)", file=sys.stderr)
        return 1
    hf_src = SNAP / "hf_repo"
    for src in sorted(hf_src.glob("*.py")):
        copy_file(src, hf_root / src.name)
    live = SNAP / "frontend_build_live"
    copy_file(live / "index.html", hf_root / "frontend" / "build" / "index.html")
    copy_file(
        live / "static" / "js" / "main.a0625928.js",
        hf_root / "frontend" / "build" / "static" / "js" / "main.a0625928.js",
    )
    map_js = live / "static" / "js" / "main.a0625928.js.map"
    if map_js.is_file():
        copy_file(map_js, hf_root / "frontend" / "build" / "static" / "js" / "main.a0625928.js.map")
    copy_file(
        live / "static" / "css" / "main.23ef7b0e.css",
        hf_root / "frontend" / "build" / "static" / "css" / "main.23ef7b0e.css",
    )
    map_css = live / "static" / "css" / "main.23ef7b0e.css.map"
    if map_css.is_file():
        copy_file(map_css, hf_root / "frontend" / "build" / "static" / "css" / "main.23ef7b0e.css.map")
    print("HF restore copied. Commit and push the Space to make it live.")
    return 0


def restore_github_frontend(repo_root: Path) -> int:
    src_root = SNAP / "frontend" / "src"
    dest_root = repo_root / "frontend" / "src"
    if not dest_root.is_dir():
        print(f"error: {dest_root} missing", file=sys.stderr)
        return 1
    for name in (
        "ValidationOverlayPlayer.js",
        "clinicalSkeleton.js",
        "handSkeletonTemplate.js",
        "overlayMetricEvidence.js",
        "App.js",
    ):
        copy_file(src_root / name, dest_root / name)
    print("GitHub frontend overlay sources copied. Rebuild only if you are not restoring the live JS bundle.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore the 14 Sep 2026 validation overlay snapshot")
    parser.add_argument("--hf-root", type=Path, help="Hugging Face Space checkout")
    parser.add_argument("--github-root", type=Path, help="NeuroLab GitHub checkout (frontend sources)")
    args = parser.parse_args()
    if not args.hf_root and not args.github_root:
        parser.print_help()
        return 2
    rc = 0
    if args.hf_root:
        rc = restore_hf(args.hf_root.resolve()) or rc
    if args.github_root:
        rc = restore_github_frontend(args.github_root.resolve()) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
