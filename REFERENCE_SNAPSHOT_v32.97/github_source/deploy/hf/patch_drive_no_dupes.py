"""Copy canonical Drive document identity onto a Hugging Face Space checkout."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

OVERLAY = Path(__file__).resolve().parents[1] / "hetzner" / "overlay"
SRC = OVERLAY / "drive_doc_identity.py"


def apply_drive_no_dupes(root: Path) -> int:
    if not SRC.is_file():
        print(f"error: missing {SRC}", file=sys.stderr)
        return 1
    dest = root / "drive_doc_identity.py"
    shutil.copy2(SRC, dest)
    print(f"copied {SRC.name} -> {dest}")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_drive_no_dupes.py /path/to/hf-space", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    if not (root / "main.py").is_file():
        print(f"error: {root}/main.py missing", file=sys.stderr)
        return 1
    return apply_drive_no_dupes(root)


if __name__ == "__main__":
    raise SystemExit(main())
