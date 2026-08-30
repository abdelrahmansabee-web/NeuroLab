"""Upload one PDF + validation videos per patient. No extra Drive clutter."""
from __future__ import annotations

import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

FOLDER_MIME = "application/vnd.google-apps.folder"
TEAM_ROOT_NAME = "team_patients"


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


def clinic_drive_filename(name: str) -> Optional[str]:
    """Keep only the patient PDF and validation overlay mp4s."""
    raw = (name or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if lower.endswith(".pdf"):
        stem = _sanitize(Path(raw).stem) or "report"
        return f"{stem}.pdf"
    if lower.endswith((".mp4", ".mov", ".m4v", ".webm")):
        if "validation_unified" in lower or "unified_validation" in lower:
            stem = Path(raw).stem
            stem = stem.replace("_validation_unified", "_validation").replace(
                "_unified_validation", "_validation"
            )
            if not stem.endswith("_validation"):
                stem = f"{stem}_validation"
            return f"{stem}.mp4"
        if lower.endswith("_validation.mp4"):
            return _sanitize(Path(raw).stem) + ".mp4"
        return None
    return None


def drive_configured() -> bool:
    try:
        from drive_oauth import oauth_client_configured, oauth_ready

        if oauth_ready():
            return True
        if oauth_client_configured():
            # OAuth secrets are set but the clinic Gmail is not linked yet.
            # Do not fall back to the service account: it has no storage quota.
            return False
    except Exception:
        pass
    return bool(
        (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
        and (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    )


def clinic_folder_id() -> str:
    try:
        from drive_oauth import clinic_backup_folder_id

        return clinic_backup_folder_id()
    except Exception:
        return (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip() or "1o30Gi0XlWtpHoI5rsUoc8217IWoJUInK"


def _mime_for(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".mp4"):
        return "video/mp4"
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _build_service():
    try:
        from drive_oauth import oauth_client_configured, oauth_drive_service, oauth_folder_id, oauth_ready

        if oauth_ready():
            svc = oauth_drive_service()
            if svc:
                return svc, oauth_folder_id()
            return None, ""
        if oauth_client_configured():
            return None, ""
    except Exception as exc:
        print("OAuth Drive persist:", exc, flush=True)
        try:
            from drive_oauth import oauth_client_configured as _oauth_client_configured

            if _oauth_client_configured():
                return None, ""
        except Exception:
            pass
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or ""
    folder_id = clinic_folder_id()
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
    try:
        from drive_oauth import oauth_ready

        if oauth_ready():
            return
    except Exception:
        pass
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


def _list_child_folders(service, parent_id: str) -> List[Dict[str, str]]:
    folders: List[Dict[str, str]] = []
    page = None
    scanned = 0
    while scanned < 400:
        res = service.files().list(
            q=f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false",
            spaces="drive",
            pageSize=100,
            pageToken=page,
            fields="nextPageToken, files(id, name)",
            **_list_flags(),
        ).execute()
        items = res.get("files") or []
        scanned += len(items)
        folders.extend({"id": item.get("id") or "", "name": item.get("name") or ""} for item in items)
        page = res.get("nextPageToken")
        if not page:
            break
    return folders


def _patient_folder(service, root_id: str, patient_key: str) -> str:
    """One folder per patient directly under NeuroLab_Backups. No nested data/videos."""
    key = _sanitize(patient_key)[:120] or "anon"
    existing = _find_folder(service, root_id, key)
    if existing:
        return existing
    head = key.split("_", 1)[0]
    if head:
        matches = [
            folder
            for folder in _list_child_folders(service, root_id)
            if folder["name"] == key or folder["name"].startswith(f"{head}_")
        ]
        if len(matches) == 1:
            return matches[0]["id"]
        named = next((folder for folder in matches if folder["name"] == key), None)
        if named:
            return named["id"]
    return _create_folder(service, root_id, key)


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
    """Upsert PDF + validation mp4s under NeuroLab_Backups/<patientKey>/."""
    _ = user_id
    key = _sanitize(patient_key)[:120] or "anon"
    result: Dict[str, Any] = {
        "ok": False,
        "patientKey": key,
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
    parent_id = folder_id or clinic_folder_id()
    if not parent_id:
        result["skipped"] = True
        result["reason"] = "drive_unset"
        return result

    uploaded = 0
    payload = []
    for name, path, _subfolder in files:
        src = Path(path)
        if not src.is_file() or src.stat().st_size <= 0:
            continue
        drive_name = clinic_drive_filename(_sanitize(name) or src.name)
        if not drive_name:
            continue
        payload.append((drive_name, src, src.read_bytes()))

    if not payload:
        result["skipped"] = True
        result["reason"] = "pdf_and_validation_videos_only"
        return result

    parent = _patient_folder(service, parent_id, key)
    for drive_name, src, content in payload:
        file_id = _upsert_bytes(service, parent, drive_name, content, _mime_for(drive_name))
        result["locations"].append({"patientKey": key, "name": drive_name, "id": file_id})
        result["files"][drive_name] = {"bytes": src.stat().st_size}
        uploaded += 1
    result["ok"] = uploaded > 0
    result["uploaded"] = uploaded
    return result


_VALIDATION_ORIGINAL_SUFFIX = "_validation_original.mp4"


def promote_original_videos_on_drive() -> Dict[str, Any]:
    """Rename existing *_validation_original.mp4 files to *_original.mp4 on Drive."""
    out: Dict[str, Any] = {"ok": False, "renamed": [], "skipped": []}
    if not drive_configured():
        out["reason"] = "drive_unset"
        return out
    service, folder_id = _build_service()
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out

    def _walk(fid: str, depth: int = 0) -> None:
        if not fid or depth > 6:
            return
        page = None
        scanned = 0
        while scanned < 400:
            res = service.files().list(
                q=f"'{fid}' in parents and trashed=false",
                spaces="drive",
                pageSize=100,
                pageToken=page,
                fields="nextPageToken, files(id, name, mimeType)",
                **_list_flags(),
            ).execute()
            items = res.get("files") or []
            scanned += len(items)
            for item in items:
                mime = item.get("mimeType") or ""
                name = item.get("name") or ""
                if mime == FOLDER_MIME:
                    _walk(item.get("id") or "", depth + 1)
                    continue
                if not name.lower().endswith(_VALIDATION_ORIGINAL_SUFFIX):
                    continue
                new_name = name[: -len(_VALIDATION_ORIGINAL_SUFFIX)] + "_original.mp4"
                existing = service.files().list(
                    q=f"'{fid}' in parents and name='{new_name.replace(chr(39), chr(92)+chr(39))}' and trashed=false",
                    spaces="drive",
                    fields="files(id, name)",
                    **_list_flags(),
                ).execute().get("files") or []
                if existing:
                    out["skipped"].append({"id": item.get("id"), "name": name, "reason": "already_has_original"})
                    continue
                service.files().update(
                    fileId=item["id"],
                    body={"name": new_name},
                    **_write_flags(),
                ).execute()
                out["renamed"].append({"id": item.get("id"), "from": name, "to": new_name})
            page = res.get("nextPageToken")
            if not page:
                break

    _walk(parent_id)
    out["ok"] = True
    return out


def upload_root_bytes(name: str, content: bytes) -> Dict[str, Any]:
    """Write a file at the clinic backup folder root. OAuth only; never SA."""
    result: Dict[str, Any] = {"ok": False, "name": name}
    if not content:
        result["reason"] = "empty"
        return result
    if not drive_configured():
        result["skipped"] = True
        result["reason"] = "drive_unset"
        return result
    service, folder_id = _build_service()
    if service is None:
        result["skipped"] = True
        result["reason"] = "drive_init_failed"
        return result
    parent_id = folder_id or clinic_folder_id()
    if not parent_id:
        result["skipped"] = True
        result["reason"] = "drive_unset"
        return result
    file_id = _upsert_bytes(service, parent_id, name, content, _mime_for(name))
    result["ok"] = True
    result["id"] = file_id
    return result


def write_drive_connected_marker(*, email: str = "", folder_name: str = "") -> Dict[str, Any]:
    """Do not put marker JSON in the clinic folder. Patient folders stay PDF + videos only."""
    return {
        "ok": True,
        "skipped": True,
        "reason": "patient_folders_only",
        "email": email,
        "folderName": folder_name,
        "folderId": clinic_folder_id(),
    }


def _list_direct_children(service, folder_id: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    page = None
    scanned = 0
    while scanned < 800:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            pageSize=100,
            pageToken=page,
            fields="nextPageToken, files(id, name, mimeType)",
            **_list_flags(),
        ).execute()
        batch = res.get("files") or []
        scanned += len(batch)
        items.extend(batch)
        page = res.get("nextPageToken")
        if not page:
            break
    return items


def trash_clinic_folder_contents() -> Dict[str, Any]:
    """Move every child of NeuroLab_Backups to Drive trash so the folder can be rebuilt."""
    out: Dict[str, Any] = {"ok": False, "trashed": [], "errors": []}
    if not drive_configured():
        out["reason"] = "drive_unset"
        return out
    service, folder_id = _build_service()
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out
    children = _list_direct_children(service, parent_id)
    for item in children:
        file_id = item.get("id") or ""
        name = item.get("name") or ""
        if not file_id:
            continue
        try:
            service.files().update(
                fileId=file_id,
                body={"trashed": True},
                **_write_flags(),
            ).execute()
            out["trashed"].append({"id": file_id, "name": name})
        except Exception as exc:
            out["errors"].append({"id": file_id, "name": name, "error": str(exc)[:200]})
    out["ok"] = not out["errors"]
    out["count"] = len(out["trashed"])
    return out


def _patient_key_from_parts(parts: Tuple[str, ...]) -> str:
    names = [part for part in parts if part]
    if names and (
        names[0] == TEAM_ROOT_NAME
        or (len(names[0]) >= 2 and names[0][0] == "u" and names[0][1:].isdigit())
    ):
        names = names[1:]
    if names and names[0] in ("data", "videos", "reports"):
        names = names[1:]
    if not names:
        return ""
    return _sanitize(names[0])[:120]


def _walk_files(
    service, folder_id: str, parts: Tuple[str, ...] = (), depth: int = 0
) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    if not folder_id or depth > 8:
        return found
    for item in _list_direct_children(service, folder_id):
        name = item.get("name") or ""
        mime = item.get("mimeType") or ""
        file_id = item.get("id") or ""
        if mime == FOLDER_MIME:
            found.extend(_walk_files(service, file_id, parts + (name,), depth + 1))
            continue
        found.append({"id": file_id, "name": name, "parent": folder_id, "parts": parts})
    return found


def _sa_service_or_none():
    try:
        sa, _folder = _sa_list_service()
        return sa
    except Exception:
        return None


def _download_bytes(service, file_id: str) -> bytes:
    try:
        return service.files().get_media(fileId=file_id).execute() or b""
    except Exception as exc:
        sa = _sa_service_or_none()
        if sa is None:
            raise
        try:
            return sa.files().get_media(fileId=file_id).execute() or b""
        except Exception:
            print(f"Drive download skipped {file_id}: {exc}", flush=True)
            return b""


def _trash_file(service, file_id: str) -> None:
    if not file_id:
        return
    try:
        service.files().update(fileId=file_id, body={"trashed": True}, **_write_flags()).execute()
        return
    except Exception as exc:
        sa = _sa_service_or_none()
        if sa is None:
            print(f"Drive trash skipped {file_id}: {exc}", flush=True)
            return
        try:
            sa.files().update(fileId=file_id, body={"trashed": True}, **_write_flags()).execute()
        except Exception as sa_exc:
            print(f"Drive trash skipped {file_id}: {sa_exc}", flush=True)


def _move_file(service, file_id: str, old_parent: str, new_parent: str, new_name: str) -> str:
    if not file_id or not new_parent:
        return ""

    def _run(svc) -> str:
        safe = new_name.replace("'", "\\'")
        existing = (
            svc.files()
            .list(
                q=f"'{new_parent}' in parents and name='{safe}' and trashed=false",
                spaces="drive",
                fields="files(id, name)",
                **_list_flags(),
            )
            .execute()
            .get("files")
            or []
        )
        if existing and existing[0]["id"] != file_id:
            _trash_file(svc, file_id)
            return existing[0]["id"]
        body = {"name": new_name} if new_name else {}
        kwargs = dict(_write_flags())
        if old_parent and old_parent != new_parent:
            kwargs["addParents"] = new_parent
            kwargs["removeParents"] = old_parent
        svc.files().update(fileId=file_id, body=body, **kwargs).execute()
        return file_id

    try:
        return _run(service)
    except Exception as exc:
        sa = _sa_service_or_none()
        if sa is None:
            print(f"Drive move skipped {file_id}: {exc}", flush=True)
            return ""
        try:
            return _run(sa)
        except Exception as sa_exc:
            print(f"Drive move skipped {file_id}: {sa_exc}", flush=True)
            return ""


def _section_json_names() -> set[str]:
    from patient_drive_archive import PROGRAM_SECTIONS

    names = {"patient.json"}
    for index, section in enumerate(PROGRAM_SECTIONS, 1):
        names.add(f"{index:02d}_{section}.json")
    return names


def _assemble_patient_record(json_files: Dict[str, bytes]) -> Optional[Dict[str, Any]]:
    from patient_drive_archive import PROGRAM_SECTIONS, parse_patients_payload

    raw = json_files.get("patient.json")
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict) and (
                parsed.get("demographics") or parsed.get("_id") or parsed.get("patientKey")
            ):
                return parsed
            patients = parse_patients_payload(parsed)
            if patients:
                return patients[0]
        except Exception:
            pass
    rec: Dict[str, Any] = {}
    for index, section in enumerate(PROGRAM_SECTIONS, 1):
        blob = json_files.get(f"{index:02d}_{section}.json")
        if not blob:
            continue
        try:
            rec[section] = json.loads(blob.decode("utf-8"))
        except Exception:
            rec[section] = {}
    return rec or None


def _canonical_patient_key(keys: List[str]) -> str:
    return sorted(keys, key=lambda key: (key.count("_"), len(key)), reverse=True)[0]


def reorganize_clinic_folder(*, service=None, folder_id: str = "") -> Dict[str, Any]:
    """Rebuild NeuroLab_Backups as one folder per patient: PDF + validation mp4s only."""
    out: Dict[str, Any] = {
        "ok": False,
        "patients": [],
        "trashed": [],
        "moved": [],
        "pdfs": 0,
        "videos": 0,
    }
    if service is None:
        if not drive_configured():
            out["reason"] = "drive_unset"
            return out
        service, folder_id = _build_service()
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out

    keep_json = _section_json_names()
    grouped: Dict[str, Dict[str, Any]] = {}
    json_candidates: Dict[str, List[Dict[str, Any]]] = {}
    for item in _walk_files(service, parent_id):
        key = _patient_key_from_parts(tuple(item.get("parts") or ()))
        if not key:
            continue
        bucket = grouped.setdefault(key, {"json": {}, "videos": [], "pdfs": []})
        name = item.get("name") or ""
        lower = name.lower()
        if lower in {n.lower() for n in keep_json} or name in keep_json:
            json_candidates.setdefault(key, []).append(item)
            continue
        mapped = clinic_drive_filename(name)
        if mapped and mapped.endswith(".mp4"):
            bucket["videos"].append({**item, "driveName": mapped})
        elif mapped and mapped.endswith(".pdf"):
            bucket["pdfs"].append({**item, "driveName": mapped})

    def _pick_json(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        named = {str(item.get("name") or "").lower(): item for item in items}
        if "patient.json" in named:
            return [named["patient.json"]]
        if "01_demographics.json" in named:
            return [item for item in items if str(item.get("name") or "").lower() != "_program_layout.json"]
        return items[:8]

    for key, items in json_candidates.items():
        for item in _pick_json(items):
            name = item.get("name") or ""
            if name in grouped[key]["json"]:
                continue
            try:
                blob = _download_bytes(service, item["id"])
                if blob:
                    grouped[key]["json"][name] = blob
            except Exception as exc:
                print(f"Drive JSON download skipped {name}: {exc}", flush=True)

    by_head: Dict[str, List[str]] = {}
    for key in grouped:
        by_head.setdefault(key.split("_", 1)[0], []).append(key)
    alias_to_canon = {
        key: _canonical_patient_key(keys) for keys in by_head.values() for key in keys
    }

    merged: Dict[str, Dict[str, Any]] = {}
    for key, bucket in grouped.items():
        canon = alias_to_canon.get(key) or key
        dest = merged.setdefault(canon, {"json": {}, "videos": [], "pdfs": []})
        dest["json"].update(bucket["json"])
        dest["videos"].extend(bucket["videos"])
        dest["pdfs"].extend(bucket["pdfs"])

    keep_folder_ids: set[str] = set()
    from patient_drive_archive import patient_drive_key
    from patient_pdf import build_patient_pdf, patient_pdf_filename

    for canon, bucket in merged.items():
        rec: Dict[str, Any] = {"patientKey": canon, "files": []}
        try:
            patient = _assemble_patient_record(bucket["json"])
            folder_name = patient_drive_key(patient) if patient else canon
            folder_name = _sanitize(folder_name)[:120] or canon
            dest_id = _find_or_create_folder(service, parent_id, folder_name)
            keep_folder_ids.add(dest_id)
            rec["patientKey"] = folder_name
            if patient:
                pdf_name = patient_pdf_filename(patient)
                pdf_bytes = build_patient_pdf(patient)
                file_id = _upsert_bytes(service, dest_id, pdf_name, pdf_bytes, "application/pdf")
                rec["files"].append({"name": pdf_name, "id": file_id})
                out["pdfs"] += 1
            seen_videos = set()
            for video in bucket["videos"]:
                drive_name = video.get("driveName") or ""
                if not drive_name or drive_name in seen_videos:
                    if drive_name in seen_videos and video.get("id"):
                        _trash_file(service, video["id"])
                        out["trashed"].append(video["id"])
                    continue
                seen_videos.add(drive_name)
                moved = _move_file(
                    service,
                    video.get("id") or "",
                    video.get("parent") or "",
                    dest_id,
                    drive_name,
                )
                rec["files"].append({"name": drive_name, "id": moved})
                out["moved"].append(drive_name)
                out["videos"] += 1
        except Exception as exc:
            rec["error"] = str(exc)[:200]
            print(f"Drive rebuild patient {canon}: {exc}", flush=True)
        out["patients"].append(rec)

    leftover = _trash_legacy_layout(service, parent_id, keep_folder_ids)
    out["trashed"].extend(leftover)
    out["ok"] = True
    out["patientCount"] = len(out["patients"])
    return out


def _is_legacy_root(name: str) -> bool:
    raw = (name or "").strip()
    if raw in (TEAM_ROOT_NAME, "u1") or raw.startswith("_"):
        return True
    if len(raw) >= 2 and raw[0] == "u" and raw[1:].isdigit():
        return True
    if raw in ("NEUROLAB_VIDEOS_HERE.txt", "_NEUROLAB_DRIVE_OK.json"):
        return True
    return False


def _trash_legacy_layout(service, parent_id: str, keep_folder_ids: set[str]) -> List[str]:
    trashed: List[str] = []
    for item in _list_direct_children(service, parent_id):
        file_id = item.get("id") or ""
        name = item.get("name") or ""
        mime = item.get("mimeType") or ""
        if not file_id:
            continue
        if mime == FOLDER_MIME and not _is_legacy_root(name):
            keep_folder_ids.add(file_id)
            for child in _list_direct_children(service, file_id):
                child_name = (child.get("name") or "").lower()
                child_mime = child.get("mimeType") or ""
                keep = child_mime != FOLDER_MIME and (
                    child_name.endswith(".pdf") or child_name.endswith("_validation.mp4")
                )
                if not keep and child.get("id"):
                    _trash_file(service, child["id"])
                    trashed.append(child["id"])
            continue
        _trash_file(service, file_id)
        trashed.append(file_id)
    return trashed


def trash_legacy_clinic_layout() -> Dict[str, Any]:
    """Trash team_patients / u1 / markers. Keep patient folders that already have PDFs."""
    out: Dict[str, Any] = {"ok": False, "trashed": []}
    if not drive_configured():
        out["reason"] = "drive_unset"
        return out
    service, folder_id = _build_service()
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out
    keep = {
        item.get("id") or ""
        for item in _list_direct_children(service, parent_id)
        if (item.get("mimeType") == FOLDER_MIME)
        and (item.get("name") or "") not in (TEAM_ROOT_NAME, "u1")
        and not str(item.get("name") or "").startswith("_")
    }
    out["trashed"] = _trash_legacy_layout(service, parent_id, keep)
    out["ok"] = True
    out["count"] = len(out["trashed"])
    return out


def _sa_list_service():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or ""
    folder_id = clinic_folder_id()
    if not raw.strip() or not folder_id:
        return None, ""
    from google.oauth2 import service_account as google_service_account
    from googleapiclient.discovery import build

    info = json.loads(raw)
    creds = google_service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False), folder_id


def _count_files(service, folder_id: str, *, depth: int = 0) -> Tuple[int, int, int, Dict[str, int]]:
    if not folder_id or depth > 6:
        return 0, 0, 0, {}
    videos = jsons = files = 0
    kinds: Dict[str, int] = {}
    page = None
    scanned = 0
    while scanned < 400:
        kwargs = dict(_list_flags())
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            pageSize=100,
            pageToken=page,
            fields="nextPageToken, files(id, name, mimeType)",
            **kwargs,
        ).execute()
        items = res.get("files") or []
        scanned += len(items)
        for item in items:
            mime = item.get("mimeType") or ""
            name = item.get("name") or ""
            lower = name.lower()
            if mime == FOLDER_MIME:
                v, j, f, k = _count_files(service, item.get("id") or "", depth=depth + 1)
                videos += v
                jsons += j
                files += f
                for key, count in k.items():
                    kinds[key] = kinds.get(key, 0) + count
                continue
            files += 1
            kinds[name] = kinds.get(name, 0) + 1
            if lower.endswith(".mp4") or mime.startswith("video/"):
                videos += 1
            if lower.endswith(".json") or mime == "application/json":
                jsons += 1
        page = res.get("nextPageToken")
        if not page:
            break
    return videos, jsons, files, kinds


def list_clinic_folder() -> Dict[str, Any]:
    """Read-only inventory. Uses OAuth when linked, otherwise SA list-only."""
    from drive_oauth import oauth_ready

    out: Dict[str, Any] = {
        "ok": False,
        "folderId": clinic_folder_id(),
        "folderName": None,
        "videoCount": 0,
        "pdfCount": 0,
        "jsonCount": 0,
        "fileCount": 0,
        "patientFolders": [],
        "rootChildren": [],
        "empty": True,
        "oauthReady": bool(oauth_ready()),
        "fileKinds": {},
        "error": None,
        "layout": "<patientId_name>/<patientId_name>.pdf + <phase>_validation.mp4",
    }
    service = None
    folder_id = clinic_folder_id()
    try:
        if oauth_ready():
            service, folder_id = _build_service()
        if service is None:
            service, folder_id = _sa_list_service()
        if service is None or not folder_id:
            out["error"] = "drive_list_unavailable"
            return out
        meta = service.files().get(
            fileId=folder_id,
            fields="id,name",
            supportsAllDrives=True,
        ).execute()
        out["folderName"] = meta.get("name")
        out["folderId"] = meta.get("id") or folder_id
        children = _list_direct_children(service, folder_id)
        names = []
        patients = []
        for item in children:
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            names.append(name)
            if mime == FOLDER_MIME:
                patients.append(name)
        out["rootChildren"] = names
        out["patientFolders"] = patients
        videos, jsons, files, kinds = _count_files(service, folder_id)
        out["videoCount"] = videos
        out["jsonCount"] = jsons
        out["fileCount"] = files
        out["pdfCount"] = sum(
            count for name, count in kinds.items() if str(name).lower().endswith(".pdf")
        )
        out["fileKinds"] = kinds
        out["empty"] = files <= 0
        out["ok"] = True
        return out
    except Exception as exc:
        out["error"] = str(exc)[:300]
        return out
