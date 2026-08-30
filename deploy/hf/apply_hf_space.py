"""Apply Drive persistence + iPad touch to a Hugging Face Space checkout.

Does not change clinic glass colors. Does not rewrite the Space wake-up boot copy.
"""
from __future__ import annotations

import sys
from pathlib import Path

OVERLAY = Path(__file__).resolve().parents[1] / "hetzner" / "overlay"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_hf_space.py /path/to/hf-space", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    if not (root / "main.py").is_file():
        print(f"error: {root}/main.py missing", file=sys.stderr)
        return 1
    if not OVERLAY.is_dir():
        print(f"error: overlay missing: {OVERLAY}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(OVERLAY))
    from patch_ipad_touch import patch_ipad_touch
    from patch_persist_videos import main as patch_videos

    videos_rc = patch_videos()
    if videos_rc != 0:
        return videos_rc
    return patch_ipad_touch(root)


if __name__ == "__main__":
    # patch_persist_videos.main reads sys.argv[1] as the space root.
    raise SystemExit(main())
