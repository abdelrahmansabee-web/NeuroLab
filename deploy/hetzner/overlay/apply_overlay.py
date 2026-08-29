#!/usr/bin/env python3
"""Copy iPad cache helpers into a Hugging Face Space checkout and wire the routes."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

MARKER = "# Serve root-level static files from the frontend build directory"
SNIPPET = """
from validation_cache import register_validation_cache
register_validation_cache(app, DATA_DIR, Path(__file__).resolve().parent / "sync_ipad_cache.html")

"""


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_overlay.py /opt/neurolab", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    overlay = Path(__file__).resolve().parent
    if not (root / "main.py").exists():
        print(f"error: {root}/main.py missing", file=sys.stderr)
        return 1

    for name in ("validation_cache.py", "sync_ipad_cache.html", "local_drive_fallback.py"):
        src = overlay / name
        if not src.exists():
            print(f"error: overlay file missing: {src}", file=sys.stderr)
            return 1
        shutil.copy2(src, root / name)
        print(f"copied {name}")

    main_py = root / "main.py"
    text = main_py.read_text(encoding="utf-8")
    if "register_validation_cache(" in text:
        print("main.py already wired for /sync-ipad")
    elif MARKER not in text:
        print("error: expected marker not found in main.py", file=sys.stderr)
        return 1
    else:
        main_py.write_text(text.replace(MARKER, SNIPPET + MARKER, 1), encoding="utf-8")
        print("wired /sync-ipad and /api/validation-cache into main.py")

    sys.path.insert(0, str(overlay))
    from patch_auth_drive import main as patch_drive
    return patch_drive()


if __name__ == "__main__":
    raise SystemExit(main())
