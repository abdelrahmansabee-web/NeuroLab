"""Scan local clinic artifacts and upload them to Google Drive."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from persist_validation import persist_phase_artifacts


def _phase_from_name(name: str) -> str:
    if name.endswith("_validation_original.mp4"):
        return name[: -len("_validation_original.mp4")] or "pre"
    if name.endswith("_validation_overlay.json"):
        return name[: -len("_validation_overlay.json")] or "pre"
    if name.endswith("_validation_unified.mp4"):
        return name[: -len("_validation_unified.mp4")] or "pre"
    return "pre"


def collect_local_sessions(data_dir: Path) -> List[Tuple[str, str, Dict[str, Path]]]:
    """Return (patientKey, phase, files) for every local validation set."""
    found: Dict[Tuple[str, str], Dict[str, Path]] = {}
    team = Path(data_dir) / "local_artifacts" / "team"
    if team.is_dir():
        for patient_dir in sorted(team.iterdir()):
            if not patient_dir.is_dir():
                continue
            key = patient_dir.name
            for sub, suffix, field in (
                ("videos", "_validation_original.mp4", "original_video"),
                ("data", "_validation_overlay.json", "overlay_json"),
                ("videos", "_validation_unified.mp4", "unified_video"),
            ):
                folder = patient_dir / sub
                if not folder.is_dir():
                    continue
                for path in folder.iterdir():
                    if not path.is_file() or path.stat().st_size <= 0:
                        continue
                    if not path.name.endswith(suffix):
                        continue
                    phase = _phase_from_name(path.name)
                    found.setdefault((key, phase), {})[field] = path

    cache = Path(data_dir) / "validation_cache"
    if cache.is_dir():
        for patient_dir in sorted(cache.iterdir()):
            if not patient_dir.is_dir():
                continue
            for phase_dir in sorted(patient_dir.iterdir()):
                if not phase_dir.is_dir():
                    continue
                files: Dict[str, Path] = {}
                original = phase_dir / "original.mp4"
                overlay = phase_dir / "overlay.json"
                unified = phase_dir / "unified.mp4"
                if original.is_file() and original.stat().st_size > 0:
                    files["original_video"] = original
                if overlay.is_file() and overlay.stat().st_size > 0:
                    files["overlay_json"] = overlay
                if unified.is_file() and unified.stat().st_size > 0:
                    files["unified_video"] = unified
                if files:
                    rec = found.setdefault((patient_dir.name, phase_dir.name), {})
                    rec.update(files)
    return [(key, phase, files) for (key, phase), files in sorted(found.items())]


def backfill_data_dir(data_dir: Path) -> Dict[str, Any]:
    sessions = collect_local_sessions(data_dir)
    uploaded = []
    for key, phase, files in sessions:
        saved = persist_phase_artifacts(
            Path(data_dir),
            key,
            phase,
            original_video=files.get("original_video"),
            overlay_json=files.get("overlay_json"),
            unified_video=files.get("unified_video"),
            library_name=f"{phase}_{key}_backfill",
        )
        uploaded.append(
            {
                "patientKey": key,
                "phase": phase,
                "files": saved.get("files") or {},
                "drive": saved.get("drive") or {},
                "drive_error": saved.get("drive_error"),
            }
        )
    records: Dict[str, Any] = {}
    try:
        from patient_drive_archive import archive_from_data_dir

        records = archive_from_data_dir(Path(data_dir))
    except Exception as exc:
        records = {"ok": False, "error": str(exc)}
    return {"ok": True, "count": len(uploaded), "sessions": uploaded, "records": records}
