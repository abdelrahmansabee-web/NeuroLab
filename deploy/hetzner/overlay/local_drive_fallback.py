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


def save_patients_backup(data_dir: Path, user_id: Any, filename: str, patients: List[Any]) -> Path:
    path = patients_backup_path(data_dir, user_id, filename)
    payload = {
        "patients": patients if isinstance(patients, list) else [],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "local": True,
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
    path.write_bytes(content or b"")
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
