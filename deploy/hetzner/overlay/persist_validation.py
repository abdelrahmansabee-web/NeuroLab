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
        if dest.resolve() != src_path.resolve():
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
        dest_lib = lib / name
        if dest_lib.resolve() != src_path.resolve():
            shutil.copy2(src_path, dest_lib)
    (lib / "meta.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")

    session_path = artifacts_root(data_dir) / "team" / key / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session: Dict[str, Any] = {}
    if session_path.is_file():
        try:
            loaded = json.loads(session_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                session = loaded
        except Exception:
            session = {}
    phases = session.get("phases") if isinstance(session.get("phases"), dict) else {}
    phases[phase_part] = {
        "saved_at": saved["saved_at"],
        "files": saved["files"],
        "never_delete": True,
    }
    session.update(
        {
            "_id": key,
            "demographics": {"participantId": key},
            "patientKey": key,
            "never_delete": True,
            "updated_at": saved["saved_at"],
            "phases": phases,
        }
    )
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    saved["session"] = str(session_path)

    drive_files = []
    uni_name = f"{phase_part}_validation_unified.mp4"
    uni_dest = artifact_path(data_dir, 0, key, uni_name, "videos", "team", _sanitize)
    if uni_dest.is_file() and uni_dest.stat().st_size > 0:
        phase_key = phase_part.lower()
        if phase_key in ("baseline", "healthy", "healthy_side"):
            drive_name = "healthy_validation.mp4"
        elif phase_key.startswith("post"):
            drive_name = "post_validation.mp4"
        else:
            drive_name = "pre_validation.mp4"
        drive_files.append((drive_name, uni_dest, "videos"))
    try:
        from drive_persist import upload_named_files

        saved["drive"] = upload_named_files(key, drive_files) if drive_files else {
            "ok": False,
            "skipped": True,
            "reason": "no_validation_video",
            "never_delete": True,
        }
    except Exception as exc:
        print(f"Drive validation-video upload warning: {exc}", flush=True)
        saved["drive_error"] = str(exc)
    return saved
