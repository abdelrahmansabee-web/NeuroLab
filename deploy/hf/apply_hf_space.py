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
    from patch_keep_kin_results import patch_keep_kin_results
    from patch_persist_videos import main as patch_videos
    from patch_restore_clinic_overlay import patch_restore_clinic_overlay
    from patch_show_results_now import patch_show_results_now
    from patch_fix_stuck_analyze import patch_fix_stuck_analyze
    from patch_unblock_analyze_ui import patch_unblock_analyze_ui
    from patch_clinic_card_and_drive import patch_clinic_card_and_drive
    from patch_ptr_hang import patch_ptr_hang
    from patch_database_groups import patch_database_groups
    from patch_motion import patch_motion
    from patch_uv_csv_restore import patch_uv_csv_restore

    videos_rc = patch_videos()
    if videos_rc != 0:
        return videos_rc
    oauth_rc = patch_drive_oauth(root)
    if oauth_rc != 0:
        return oauth_rc
    touch_rc = patch_ipad_touch(root)
    if touch_rc != 0:
        return touch_rc
    kin_rc = patch_keep_kin_results(root)
    if kin_rc != 0:
        return kin_rc
    uv_rc = patch_uv_csv_restore(root)
    if uv_rc != 0:
        return uv_rc
    overlay_rc = patch_restore_clinic_overlay(root)
    if overlay_rc != 0:
        return overlay_rc
    results_rc = patch_show_results_now(root)
    if results_rc != 0:
        return results_rc
    unblock_rc = patch_unblock_analyze_ui(root)
    if unblock_rc != 0:
        return unblock_rc
    stuck_rc = patch_fix_stuck_analyze(root)
    if stuck_rc != 0:
        return stuck_rc
    card_rc = patch_clinic_card_and_drive(root)
    if card_rc != 0:
        return card_rc
    ptr_rc = patch_ptr_hang(root)
    if ptr_rc != 0:
        return ptr_rc
    db_rc = patch_database_groups(root)
    if db_rc != 0:
        return db_rc
    motion_rc = patch_motion(root)
    if motion_rc != 0:
        return motion_rc
    for rel in ("main.py", "analyze_job_runner.py"):
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = text
        for old in (
            'DEPLOY_VERSION = "29.61"',
            'DEPLOY_VERSION = "29.62"',
            'DEPLOY_VERSION = "29.64"',
            'DEPLOY_VERSION = "29.63"',
            'DEPLOY_VERSION = "29.65"',
            'DEPLOY_VERSION = "29.71"',
            'DEPLOY_VERSION = "29.70"',
            'DEPLOY_VERSION = "29.69"',
            'DEPLOY_VERSION = "29.68"',
            'DEPLOY_VERSION = "29.67"',
            'DEPLOY_VERSION = "29.66"',
            'DEPLOY_VERSION = "29.59"',
            'DEPLOY_VERSION = "29.58"',
            'DEPLOY_VERSION = "29.57"',
            'DEPLOY_VERSION = "29.56"',
            'DEPLOY_VERSION = "29.55"',
            'DEPLOY_VERSION = "29.54"',
            'DEPLOY_VERSION = "29.53"',
            'DEPLOY_VERSION = "29.52"',
            'DEPLOY_VERSION = "29.51"',
            'DEPLOY_VERSION = "29.50"',
            'DEPLOY_VERSION = "29.49"',
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
            updated = updated.replace(old, 'DEPLOY_VERSION = "29.71"')
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            print(f"bumped {rel} to 29.71")
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
