"""Upload clinic validation files to Google Drive. Never deletes Drive files."""
from __future__ import annotations

import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

FOLDER_MIME = "application/vnd.google-apps.folder"
TEAM_ROOT_NAME = "team_patients"


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


def drive_configured() -> bool:
    return bool(
        (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
        and (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    )


def _mime_for(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".mp4"):
        return "video/mp4"
    if lower.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _build_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or ""
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or ""
    if not raw.strip() or not folder_id.strip():
        return None, ""
    from google.oauth2 import service_account as google_service_account
    from googleapiclient.discovery import build

    info = json.loads(raw)
    creds = google_service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False), folder_id.strip()


def _list_flags() -> dict:
    return {"supportsAllDrives": True, "includeItemsFromAllDrives": True}


def _write_flags() -> dict:
    return {"supportsAllDrives": True}


def _share_with_owner(service, file_id: str) -> None:
    email = (
        (os.environ.get("GOOGLE_DRIVE_SHARE_EMAIL") or os.environ.get("NEUROLAB_ADMIN_EMAIL") or "")
        .strip()
        .lower()
    )
    if not email or not file_id:
        return
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": email},
            sendNotificationEmail=False,
            fields="id",
            **_write_flags(),
        ).execute()
    except Exception as exc:
        print(f"Drive share skipped ({file_id}): {exc}", flush=True)


def _find_folder(service, parent_id: str, folder_name: str) -> Optional[str]:
    safe = folder_name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and name='{safe}' "
        f"and mimeType='{FOLDER_MIME}' and trashed=false"
    )
    res = service.files().list(
        q=q, spaces="drive", fields="files(id, name)", **_list_flags()
    ).execute()
    files = res.get("files") or []
    return files[0]["id"] if files else None


def _create_folder(service, parent_id: str, folder_name: str) -> str:
    created = service.files().create(
        body={"name": folder_name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
        fields="id",
        **_write_flags(),
    ).execute()
    folder_id = created["id"]
    _share_with_owner(service, folder_id)
    return folder_id


def _find_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    name = _sanitize(folder_name) or "folder"
    existing = _find_folder(service, parent_id, name)
    if existing:
        return existing
    return _create_folder(service, parent_id, name)


def _team_subfolder(service, root_id: str, patient_key: str, subfolder: str) -> str:
    team = _find_or_create_folder(service, root_id, TEAM_ROOT_NAME)
    patient = _find_or_create_folder(service, team, _sanitize(patient_key)[:120] or "anon")
    sub = _sanitize(subfolder) or "files"
    if sub not in ("videos", "reports", "data"):
        sub = "data"
    return _find_or_create_folder(service, patient, sub)


def _user_subfolder(service, root_id: str, user_id: int, patient_key: str, subfolder: str) -> str:
    user_root = _find_or_create_folder(service, root_id, f"u{int(user_id)}")
    patient = _find_or_create_folder(service, user_root, _sanitize(patient_key)[:120] or "anon")
    sub = _sanitize(subfolder) or "files"
    if sub not in ("videos", "reports", "data"):
        sub = "data"
    return _find_or_create_folder(service, patient, sub)


def patient_key_aliases(patient_key: str) -> list[str]:
    key = _sanitize(patient_key)[:120] or "anon"
    aliases = [key]
    if "_" in key:
        head = key.split("_", 1)[0]
        if head and head not in aliases:
            aliases.append(head)
    return aliases


def _upsert_bytes(service, parent_id: str, name: str, content: bytes, mime: str) -> str:
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError:  # pragma: no cover - tests without Drive client
        class MediaIoBaseUpload:  # type: ignore[no-redef]
            def __init__(self, fd, mimetype=None, resumable=False):
                self.fd = fd
                self.mimetype = mimetype

    safe_name = name.replace("'", "\\'")
    q = f"'{parent_id}' in parents and name='{safe_name}' and trashed=false"
    res = service.files().list(
        q=q, spaces="drive", fields="files(id, name)", **_list_flags()
    ).execute()
    files = res.get("files") or []
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime, resumable=True)
    if files:
        service.files().update(
            fileId=files[0]["id"], media_body=media, **_write_flags()
        ).execute()
        _share_with_owner(service, files[0]["id"])
        return files[0]["id"]
    created = service.files().create(
        body={"name": name, "parents": [parent_id]},
        media_body=media,
        fields="id",
        **_write_flags(),
    ).execute()
    _share_with_owner(service, created["id"])
    return created["id"]


def upload_named_files(
    patient_key: str,
    files: Iterable[Tuple[str, Path, str]],
    *,
    service=None,
    folder_id: str = "",
    user_id: int = 1,
) -> Dict[str, Any]:
    """Upsert validation files under team_patients and u{user}/{patientKey}.

    Existing Drive files are updated in place. Nothing is trashed or deleted.
    """
    key = _sanitize(patient_key)[:120] or "anon"
    result: Dict[str, Any] = {
        "ok": False,
        "patientKey": key,
        "never_delete": True,
        "files": {},
        "locations": [],
    }
    if service is None:
        if not drive_configured():
            result["skipped"] = True
            result["reason"] = "drive_unset"
            return result
        service, folder_id = _build_service()
        if service is None:
            result["skipped"] = True
            result["reason"] = "drive_init_failed"
            return result
    parent_id = folder_id or (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    if not parent_id:
        result["skipped"] = True
        result["reason"] = "drive_unset"
        return result

    uploaded = 0
    payload = []
    for name, path, subfolder in files:
        src = Path(path)
        if not src.is_file() or src.stat().st_size <= 0:
            continue
        payload.append((_sanitize(name) or src.name, src, subfolder, src.read_bytes()))

    for alias in patient_key_aliases(key):
        for drive_name, src, subfolder, content in payload:
            parents = [
                _team_subfolder(service, parent_id, alias, subfolder),
                _user_subfolder(service, parent_id, user_id, alias, subfolder),
            ]
            for parent in parents:
                file_id = _upsert_bytes(service, parent, drive_name, content, _mime_for(drive_name))
                result["locations"].append(
                    {"patientKey": alias, "name": drive_name, "id": file_id, "subfolder": subfolder}
                )
            result["files"][drive_name] = {"bytes": src.stat().st_size, "subfolder": subfolder}
            uploaded += 1
    result["ok"] = uploaded > 0
    result["uploaded"] = uploaded
    return result
