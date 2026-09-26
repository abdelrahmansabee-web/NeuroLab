"""Stop live serve_index from 302/307-bouncing the iPad Home Screen icon.

The icon start_url is /. A 307 to /?_v=&_r=&_ios= leaves iOS standalone on
AuthGate Loading because WebKit never stably follows that navigation.
"""
from __future__ import annotations

from pathlib import Path

START = "    # Home Screen icons keep a cached start_url."
END = "    # HF Spaces: serve file directly"


def patch_serve_index(src: str) -> str:
    start = src.find(START)
    end = src.find(END)
    if start < 0 or end < 0 or end <= start:
        return src
    return src[:start] + src[end:]


def main(root: Path) -> int:
    path = root / "main.py"
    src = path.read_text(encoding="utf-8")
    out = patch_serve_index(src)
    if out == src:
        print("home-screen redirect already absent")
        return 0
    if "ios_stamp" in out or "status_code=307" in out:
        raise RuntimeError("serve_index still redirects after patch")
    path.write_text(out, encoding="utf-8")
    print("removed Home Screen 307/302 from serve_index")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
