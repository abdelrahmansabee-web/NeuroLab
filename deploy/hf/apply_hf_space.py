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
    from patch_drive_oauth import patch_drive_oauth
    from patch_ipad_touch import patch_ipad_touch
    from patch_persist_videos import main as patch_videos

    videos_rc = patch_videos()
    if videos_rc != 0:
        return videos_rc
    oauth_rc = patch_drive_oauth(root)
    if oauth_rc != 0:
        return oauth_rc
    touch_rc = patch_ipad_touch(root)
    if touch_rc != 0:
        return touch_rc
    for rel in ("main.py", "analyze_job_runner.py"):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old in (
            'DEPLOY_VERSION = "29.48"',
            'DEPLOY_VERSION = "29.47"',
            'DEPLOY_VERSION = "29.46"',
            'DEPLOY_VERSION = "29.45"',
            'DEPLOY_VERSION = "29.44"',
            'DEPLOY_VERSION = "29.43"',
            'DEPLOY_VERSION = "29.42"',
            'DEPLOY_VERSION = "29.41"',
            'DEPLOY_VERSION = "29.40"',
            'DEPLOY_VERSION = "29.39"',
            'DEPLOY_VERSION = "29.38"',
            'DEPLOY_VERSION = "29.37"',
            'DEPLOY_VERSION = "29.36"',
            'DEPLOY_VERSION = "29.35"',
            'DEPLOY_VERSION = "29.34"',
            'DEPLOY_VERSION = "29.33"',
            'DEPLOY_VERSION = "29.32"',
        ):
            updated = updated.replace(old, 'DEPLOY_VERSION = "29.49"')
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"bumped {rel} to 29.49")
    _ensure_weasyprint(root)
    return 0


WEASY_MARKER = "weasyprint==63.1"


def _ensure_weasyprint(root: Path) -> None:
    docker = root / "Dockerfile"
    if not docker.is_file():
        return
    text = docker.read_text(encoding="utf-8")
    if WEASY_MARKER in text:
        print("Dockerfile already has weasyprint")
        return
    snippet = """
# Glass Export Report HTML -> PDF (same document as Download PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \\
    libgdk-pixbuf-2.0-0 libcairo2 fonts-dejavu-core \\
    && rm -rf /var/lib/apt/lists/* \\
    && pip install --no-cache-dir weasyprint==63.1
"""
    if "COPY . ." in text:
        text = text.replace("COPY . .", "COPY . .\n" + snippet, 1)
        docker.write_text(text, encoding="utf-8")
        print("added weasyprint to Dockerfile after COPY")
        return
    print("WARN: Dockerfile COPY . . not found; weasyprint not added")


if __name__ == "__main__":
    # patch_persist_videos.main reads sys.argv[1] as the space root.
    raise SystemExit(main())
