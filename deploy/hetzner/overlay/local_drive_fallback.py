"""Store Drive backup/restore artifacts on the VPS disk when Google Drive is unset.

The production frontend always calls /auth/backup, /auth/restore, /auth/backup-file,
and /auth/restore-file. Those endpoints used to return HTTP 500 without Drive, which
made the UI retry, feel broken, and drop validation overlays/videos after IndexedDB
eviction. This module is the local stand-in.
"""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

Sanitize = Callable[[str], str]


def artifacts_root(data_dir: Path) -> Path:
    path = Path(data_dir) / "local_artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _user_dir(data_dir: Path, user_id: Any) -> Path:
    dest = artifacts_root(data_dir) / "user" / str(user_id)
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def patients_backup_path(data_dir: Path, user_id: Any, filename: str) -> Path:
    return _user_dir(data_dir, user_id) / filename


def _patient_id(patient: Any) -> str:
    if not isinstance(patient, dict):
        return ""
    demo = patient.get("demographics") if isinstance(patient.get("demographics"), dict) else {}
    return str(patient.get("_id") or demo.get("participantId") or patient.get("patientKey") or "").strip()


def _is_probe_patient(patient: Any) -> bool:
    return _patient_id(patient).lower() in {"", "probe"}


def merge_patient_lists(*groups: List[Any]) -> List[Any]:
    by_id: dict[str, Any] = {}
    for group in groups:
        if not isinstance(group, list):
            continue
        for patient in group:
            key = _patient_id(patient)
            if not key or _is_probe_patient(patient):
                continue
            prev = by_id.get(key)
            if not isinstance(prev, dict):
                by_id[key] = patient
                continue
            prev_ts = str(prev.get("_savedAt") or prev.get("updated_at") or "")
            new_ts = str(patient.get("_savedAt") or patient.get("updated_at") or "")
            by_id[key] = patient if new_ts >= prev_ts else prev
    return list(by_id.values())


def list_validation_sessions(data_dir: Path) -> List[Any]:
    """Patients that have validation files on disk — never depends on IndexedDB."""
    team = artifacts_root(data_dir) / "team"
    if not team.is_dir():
        return []
    sessions: List[Any] = []
    for key_dir in sorted(team.iterdir()):
        if not key_dir.is_dir() or _is_probe_patient({"_id": key_dir.name}):
            continue
        has_file = False
        for folder in (key_dir / "videos", key_dir / "data"):
            if folder.is_dir() and any(
                path.is_file() and path.stat().st_size > 0 and "validation" in path.name
                for path in folder.iterdir()
            ):
                has_file = True
                break
        session_path = key_dir / "session.json"
        rec: dict[str, Any] = {
            "_id": key_dir.name,
            "patientKey": key_dir.name,
            "demographics": {"participantId": key_dir.name},
            "_serverValidation": True,
            "never_delete": True,
        }
        if session_path.is_file():
            try:
                loaded = json.loads(session_path.read_text(encoding="utf-8"))
            except Exception:
                loaded = None
            if isinstance(loaded, dict):
                rec.update({k: loaded[k] for k in loaded if k not in rec})
                rec["_id"] = key_dir.name
                rec["patientKey"] = key_dir.name
                rec["never_delete"] = True
                rec["_serverValidation"] = True
                rec["_savedAt"] = loaded.get("updated_at") or loaded.get("saved_at") or rec.get("_savedAt")
        if has_file or session_path.is_file():
            sessions.append(rec)
    return sessions


def merge_validation_sessions(data_dir: Path, patients: List[Any]) -> List[Any]:
    return merge_patient_lists(patients, list_validation_sessions(data_dir))


def save_patients_backup(data_dir: Path, user_id: Any, filename: str, patients: List[Any]) -> Path:
    path = patients_backup_path(data_dir, user_id, filename)
    incoming = patients if isinstance(patients, list) else []
    existing = load_patients_backup(data_dir, user_id, filename)
    # Do not let a health-check "probe" record wipe real clinic sessions.
    if incoming and all(_is_probe_patient(p) for p in incoming) and merge_patient_lists(existing):
        incoming = existing
    merged = merge_validation_sessions(data_dir, merge_patient_lists(existing, incoming))
    payload = {
        "patients": merged,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "local": True,
        "never_delete": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load_patients_backup(data_dir: Path, user_id: Any, filename: str) -> List[Any]:
    path = patients_backup_path(data_dir, user_id, filename)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    patients = data.get("patients") if isinstance(data, dict) else data
    return patients if isinstance(patients, list) else []


def _norm_subfolder(subfolder: str) -> str:
    sub = (subfolder or "data").strip().lower()
    return sub if sub in ("videos", "reports", "data") else "data"


def artifact_path(
    data_dir: Path,
    user_id: Any,
    patient_key: str,
    name: str,
    subfolder: str,
    scope: str,
    sanitize: Sanitize,
) -> Path:
    safe_key = sanitize(patient_key)[:120] or "anon"
    safe_name = sanitize(name) or "file.bin"
    sub = _norm_subfolder(subfolder)
    scope_norm = (scope or "team").strip().lower()
    if scope_norm not in ("team", "user"):
        scope_norm = "team"
    if scope_norm == "team":
        dest = artifacts_root(data_dir) / "team" / safe_key / sub
    else:
        dest = _user_dir(data_dir, user_id) / safe_key / sub
    dest.mkdir(parents=True, exist_ok=True)
    return dest / safe_name


def write_artifact(
    data_dir: Path,
    user_id: Any,
    patient_key: str,
    name: str,
    content: bytes,
    subfolder: str,
    scope: str,
    sanitize: Sanitize,
) -> Path:
    path = artifact_path(data_dir, user_id, patient_key, name, subfolder, scope, sanitize)
    payload = content or b""
    if path.is_file() and path.stat().st_size > 0 and not payload:
        return path
    path.write_bytes(payload)
    return path


def find_artifact(
    data_dir: Path,
    user_id: Any,
    patient_key: str,
    name: str,
    subfolder: str,
    scopes: Tuple[str, ...],
    sanitize: Sanitize,
) -> Optional[Path]:
    for scope in scopes:
        path = artifact_path(data_dir, user_id, patient_key, name, subfolder, scope, sanitize)
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"
