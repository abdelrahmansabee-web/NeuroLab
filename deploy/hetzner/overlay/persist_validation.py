"""Copy validation video + overlay onto server disk using the names the clinic UI restores."""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from local_drive_fallback import artifact_path, artifacts_root


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


def persist_phase_artifacts(
    data_dir: Path,
    patient_key: str,
    phase: str,
    *,
    original_video: Optional[Path] = None,
    overlay_json: Optional[Path] = None,
    unified_video: Optional[Path] = None,
    library_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Save playback files for /auth/restore-file (team/{patientKey}/...)."""
    phase_part = _sanitize(phase) or "pre"
    key = _sanitize(patient_key)[:120] or "anon"
    saved: Dict[str, Any] = {
        "patientKey": key,
        "phase": phase_part,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "files": {},
    }

    mapping = (
        (original_video, f"{phase_part}_validation_original.mp4", "videos"),
        (overlay_json, f"{phase_part}_validation_overlay.json", "data"),
        (unified_video, f"{phase_part}_validation_unified.mp4", "videos"),
    )
    for src, name, sub in mapping:
        if src is None:
            continue
        src_path = Path(src)
        if not src_path.is_file() or src_path.stat().st_size <= 0:
            continue
        dest = artifact_path(data_dir, 0, key, name, sub, "team", _sanitize)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest)
        saved["files"][name] = dest.stat().st_size

    lib_stem = _sanitize(library_name or f"{phase_part}_{key}") or phase_part
    lib = artifacts_root(data_dir) / "library" / lib_stem
    lib.mkdir(parents=True, exist_ok=True)
    for src, name, _sub in mapping:
        if src is None:
            continue
        src_path = Path(src)
        if not src_path.is_file():
            continue
        shutil.copy2(src_path, lib / name)
    (lib / "meta.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    return saved
