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
# Clinic layout under RAED_AI_Backups (legacy NeuroLab_Backups still recognized):
# active patient folders at root; archived under Archive/; study Excel under Excel/.
ARCHIVE_FOLDER_NAME = "Archive"
EXCEL_FOLDER_NAME = "Excel"
CLINIC_SYSTEM_FOLDERS = frozenset(
    {
        ARCHIVE_FOLDER_NAME,
        EXCEL_FOLDER_NAME,
        "Reports",
        "NeuroLab_Archive",
        "RAED_AI_Archive",
        TEAM_ROOT_NAME,
        "_system",
    }
)


def _sanitize(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


ALLOWED_VALIDATION_VIDEOS = {
    "pre_validation.mp4",
    "post_validation.mp4",
    "healthy_validation.mp4",
    "pre_validation.webm",
    "post_validation.webm",
    "healthy_validation.webm",
    "pre_validation_original.mp4",
    "post_validation_original.mp4",
    "healthy_validation_original.mp4",
}

ALLOWED_VALIDATION_DATA = {
    "pre_validation_overlay.json",
    "post_validation_overlay.json",
    "healthy_validation_overlay.json",
    "pre_kinematics.json",
    "post_kinematics.json",
    "healthy_kinematics.json",
}


def _normalize_phase_stem(stem: str) -> Optional[str]:
    s = (stem or "").lower().strip()
    if not s:
        return None
    if s in ("baseline", "healthy", "healthy_side"):
        return "healthy"
    if s in ("pre", "post", "healthy"):
        return s
    return None


def clinic_drive_filename(name: str, patient_key: str = "") -> Optional[str]:
    """
    Allow clinic persistence artifacts per patient:
      - PDF report
      - validation playback mp4 (pre/post/healthy_validation.mp4)
      - original analysis video (*_validation_original.mp4)
      - overlay JSON (*_validation_overlay.json)
      - kinematics snapshot (*_kinematics.json)
    Everything else is skipped to avoid Drive clutter.
    Dated / alias names of the same kind collapse onto one canonical file.
    """
    raw = (name or "").strip()
    if not raw:
        return None
    try:
        from drive_doc_identity import canonicalize_upload_name

        mapped = canonicalize_upload_name(name, patient_key=patient_key)
        if mapped:
            return mapped
    except Exception:
        pass
    lower = raw.lower()
    stem = Path(raw).stem.lower()

    if lower.endswith(".pdf"):
        pdf_stem = _sanitize(Path(raw).stem) or "report"
        return f"{pdf_stem}.pdf"

    if lower.endswith(".json"):
        # pre_validation_overlay.json / post_kinematics.json / …
        for phase in ("pre", "post", "healthy", "baseline"):
            if stem == f"{phase}_validation_overlay" or stem.endswith(f"_{phase}_validation_overlay"):
                p = _normalize_phase_stem(phase) or "pre"
                return f"{p}_validation_overlay.json"
            if stem == f"{phase}_kinematics" or stem.endswith(f"_{phase}_kinematics"):
                p = _normalize_phase_stem(phase) or "pre"
                return f"{p}_kinematics.json"
        if stem.endswith("_validation_overlay"):
            phase = _normalize_phase_stem(stem[: -len("_validation_overlay")]) or "pre"
            return f"{phase}_validation_overlay.json"
        if stem.endswith("_kinematics"):
            phase = _normalize_phase_stem(stem[: -len("_kinematics")]) or "pre"
            return f"{phase}_kinematics.json"
        return None

    if lower.endswith((".mp4", ".mov", ".m4v", ".webm")):
        # Original capture used by overlay player
        if stem.endswith("_validation_original") or stem.endswith("_original"):
            base = stem.replace("_validation_original", "").replace("_original", "")
            phase = _normalize_phase_stem(base)
            if phase:
                return f"{phase}_validation_original.mp4"
            return None

        # Unified / primary validation playback → short clinic names
        cleaned = (
            stem.replace("_validation_unified", "")
            .replace("_unified_validation", "")
            .replace("_validation", "")
        )
        phase = _normalize_phase_stem(cleaned)
        if phase:
            ext = ".webm" if lower.endswith(".webm") else ".mp4"
            return f"{phase}_validation{ext}"
        mapped = _sanitize(Path(raw).stem) + Path(raw).suffix.lower()
        if mapped.lower() in ALLOWED_VALIDATION_VIDEOS:
            return mapped.lower()
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
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".xls"):
        return "application/vnd.ms-excel"
    if lower.endswith(".csv"):
        return "text/csv"
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


def _rename_folder(service, folder_id: str, new_name: str) -> bool:
    name = _sanitize(new_name)[:120]
    if not folder_id or not name:
        return False
    try:
        service.files().update(fileId=folder_id, body={"name": name}, **_write_flags()).execute()
        return True
    except Exception as exc:
        print(f"Drive folder rename skipped {folder_id}: {exc}", flush=True)
        return False


def _folder_name_stem(folder_name: str) -> str:
    """'104_Ahmet_sever' → 'Ahmet_sever'; bare '129' → ''."""
    name = (folder_name or "").strip()
    if not name:
        return ""
    if "_" not in name:
        return "" if name.isdigit() else name
    head, rest = name.split("_", 1)
    if head.isdigit() and rest:
        return rest
    return name


def _norm_stem(stem: str) -> str:
    return _sanitize(stem or "").lower()


def _file_patient_stem(filename: str) -> str:
    """'4_Zeynep.pdf' → 'Zeynep'; 'pre_validation.mp4' → '' (untagged clinic artifact)."""
    raw = (filename or "").strip()
    if not raw:
        return ""
    stem = Path(raw).stem
    head, _, rest = stem.partition("_")
    if head.isdigit() and rest:
        return rest
    return ""


def _child_belongs_in_patient_folder(filename: str, patient_stem: str, patient_key: str = "") -> bool:
    """Never move another person's StudyID_Name.pdf into this patient's folder."""
    file_stem = _file_patient_stem(filename)
    if not file_stem:
        # Untagged clinic artifacts (validation mp4/json) travel with a correctly matched folder.
        return True
    want = _norm_stem(patient_stem) or _norm_stem(_folder_name_stem(patient_key))
    if not want:
        return True
    return _norm_stem(file_stem) == want


def _folder_study_rank(folder_name: str) -> Tuple[int, int, int, int]:
    """Prefer clinic Study IDs (101+) when choosing which physical folder to keep."""
    name = folder_name or ""
    prefix = name.split("_", 1)[0]
    try:
        sid = int(prefix) if prefix.isdigit() else -1
    except ValueError:
        sid = -1
    clinic = 1 if 101 <= sid < 100_000_000 else 0
    return (clinic, sid, name.count("_"), len(name))


def _pdf_keep_rank(
    filename: str, folder_key: str, *, size: int = 0, modified: str = ""
) -> Tuple[int, int, int, int, str]:
    """Prefer exact ``{folderKey}.pdf``, then Study ID ≥101, then size/recency."""
    stem = Path(filename or "").stem
    exact = 1 if stem == folder_key else 0
    head = stem.split("_", 1)[0] if stem else ""
    try:
        sid = int(head) if head.isdigit() else -1
    except ValueError:
        sid = -1
    clinic = 1 if 101 <= sid < 100_000_000 else 0
    return (exact, clinic, sid, int(size or 0), modified or "")


def _rename_drive_file(service, file_id: str, new_name: str) -> bool:
    name = _sanitize(new_name)[:180]
    if not file_id or not name:
        return False
    try:
        service.files().update(fileId=file_id, body={"name": name}, **_write_flags()).execute()
        return True
    except Exception as exc:
        print(f"Drive file rename skipped {file_id}: {exc}", flush=True)
        return False


def _dedupe_same_name_clinic_pdfs(
    service,
    folder_id: str,
    folder_key: str,
    *,
    log: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Keep one ``{digits}_{Name}.pdf`` per patient folder; trash same-stem duplicates.

    After same-name folder merge, historical Study-ID PDFs pile up (``3_Ahmet_sever.pdf``
    next to ``115_Ahmet_sever.pdf``). Prefer the PDF that matches the folder Study ID,
    else highest Study ID ≥101, else newest/largest. Never trash unrelated names.
    """
    result: Dict[str, Any] = {
        "kept": None,
        "trashed": [],
        "renamed": False,
        "skippedForeign": 0,
    }
    key = _sanitize(folder_key)[:120] or ""
    want_stem = _norm_stem(_folder_name_stem(key))
    if not folder_id or not want_stem or len(want_stem) < 3:
        return result

    candidates: List[Dict[str, Any]] = []
    for child in _list_direct_children(service, folder_id):
        name = child.get("name") or ""
        mime = child.get("mimeType") or ""
        cid = child.get("id") or ""
        if not cid or mime == FOLDER_MIME:
            continue
        if not name.lower().endswith(".pdf"):
            continue
        file_stem = _file_patient_stem(name)
        if not file_stem or _norm_stem(file_stem) != want_stem:
            # Different person or untagged — leave alone (avoids 32.30-style mixing).
            result["skippedForeign"] += 1
            continue
        try:
            size = int(child.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        candidates.append(
            {
                "id": cid,
                "name": name,
                "size": size,
                "modifiedTime": child.get("modifiedTime") or "",
            }
        )

    if not candidates:
        return result

    preferred = sorted(
        candidates,
        key=lambda c: _pdf_keep_rank(
            c["name"],
            key,
            size=int(c.get("size") or 0),
            modified=str(c.get("modifiedTime") or ""),
        ),
        reverse=True,
    )[0]
    keep_id = preferred["id"]
    target_name = f"{key}.pdf"

    # Trash duplicates first so rename to the canonical folder name cannot collide.
    for cand in candidates:
        if cand["id"] == keep_id:
            continue
        if _trash_file(service, cand["id"]):
            result["trashed"].append(cand["name"])
            if log is not None:
                log.append(
                    {
                        "trashedPdf": cand["name"],
                        "keptPdf": target_name if preferred["name"] != target_name else preferred["name"],
                        "folder": key,
                    }
                )
            print(
                f"Drive PDF dedupe trashed {cand['name']} → keep for {key}",
                flush=True,
            )

    kept_name = preferred["name"]
    if kept_name != target_name:
        if _rename_drive_file(service, keep_id, target_name):
            result["renamed"] = True
            kept_name = target_name
            print(f"Drive PDF renamed → {target_name}", flush=True)

    result["kept"] = kept_name
    return result


def dedupe_clinic_pdfs_in_backups(
    *, service=None, folder_id: str = ""
) -> Dict[str, Any]:
    """Sweep NeuroLab_Backups patient folders and dedupe same-name clinic PDFs."""
    out: Dict[str, Any] = {
        "ok": False,
        "folders": 0,
        "withDupes": 0,
        "trashed": [],
        "kept": [],
        "errors": [],
        "mode": "pdf_dedupe",
    }
    try:
        if service is None:
            try:
                service, folder_id = _build_service()
            except Exception as exc:
                out["errors"].append({"build": str(exc)[:200]})
                return out
        parent_id = (folder_id or clinic_folder_id() or "").strip()
        if service is None or not parent_id:
            out["reason"] = "drive_init_failed"
            return out

        folders = [
            item
            for item in _list_direct_children(service, parent_id)
            if (item.get("mimeType") == FOLDER_MIME)
            and (item.get("id") or "")
            and (item.get("name") or "").strip()
            and not (item.get("name") or "").startswith("_")
        ]
        out["folders"] = len(folders)
        log: List[Dict[str, Any]] = []
        for folder in folders:
            name = folder.get("name") or ""
            fid = folder.get("id") or ""
            if len(_folder_name_stem(name)) < 3 and "_" not in name:
                continue
            try:
                deduped = _dedupe_same_name_clinic_pdfs(service, fid, name, log=log)
                if deduped.get("trashed"):
                    out["withDupes"] += 1
                    out["trashed"].extend(deduped["trashed"])
                if deduped.get("kept"):
                    out["kept"].append({"folder": name, "pdf": deduped["kept"]})
            except Exception as exc:
                out["errors"].append({"folder": name, "error": str(exc)[:200]})
                print(f"Drive PDF dedupe folder {name}: {exc}", flush=True)
        out["ok"] = True
        out["trashedCount"] = len(out["trashed"])
        print(
            f"Drive PDF dedupe: folders={out['folders']} with_dupes={out['withDupes']} "
            f"trashed={out['trashedCount']}",
            flush=True,
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        print(f"Drive PDF dedupe sweep failed: {exc}", flush=True)
        return out


def _patient_folder(
    service, root_id: str, patient_key: str, *, merge_log: Optional[List[Dict[str, Any]]] = None
) -> str:
    """One folder per person under NeuroLab_Backups.

    Reuse/rename Study-ID aliases AND same-name stems (e.g. 3_Ahmet_sever + 104_Ahmet_sever).
    Never fork duplicates for the same person. Physical keeper prefers 101+ Study ID,
    then renames to the requested canonical key.

    CRITICAL: never match by Study ID prefix alone (``14_`` must NOT pull ``14_betul`` into
    ``14_Ahmet``). Only exact key, bare numeric Study-ID folder, or identical name stem.
    """
    key = _sanitize(patient_key)[:120] or "anon"
    existing = _find_folder(service, root_id, key)
    head = key.split("_", 1)[0]
    stem = _folder_name_stem(key)
    children = _list_child_folders(service, root_id)
    matches: List[Dict[str, str]] = []
    seen_ids: set[str] = set()

    def _add(folder: Dict[str, str]) -> None:
        fid = folder.get("id") or ""
        if not fid or fid in seen_ids:
            return
        seen_ids.add(fid)
        matches.append({"id": fid, "name": folder.get("name") or ""})

    if existing:
        _add({"id": existing, "name": key})
    for folder in children:
        name = folder.get("name") or ""
        if name == key:
            _add(folder)
            continue
        # Legacy bare Study-ID folder only (exactly "104"), never "104_OtherPerson".
        if head and head.isdigit() and name == head:
            _add(folder)
            continue
        # Same person under many Study IDs (3_Ahmet_sever vs 104_Ahmet_sever).
        if stem and len(stem) >= 3 and _norm_stem(_folder_name_stem(name)) == _norm_stem(stem):
            _add(folder)

    if matches:
        # Do NOT prefer a low-ID exact name over a 101+ alias — that recreated Drive dupes.
        preferred = sorted(
            matches, key=lambda folder: _folder_study_rank(folder.get("name") or ""), reverse=True
        )[0]
        if preferred["name"] != key:
            _rename_folder(service, preferred["id"], key)
            preferred = {"id": preferred["id"], "name": key}
        # Merge leftover aliases / same-name stems into the canonical folder, then trash them.
        for folder in matches:
            if folder["id"] == preferred["id"]:
                continue
            try:
                moved = 0
                skipped_foreign = 0
                for child in _list_direct_children(service, folder["id"]):
                    cid = child.get("id") or ""
                    cname = child.get("name") or ""
                    if not cid:
                        continue
                    if not _child_belongs_in_patient_folder(cname, stem, key):
                        skipped_foreign += 1
                        continue
                    if _move_file(service, cid, folder["id"], preferred["id"], cname):
                        moved += 1
                # Only trash alias after children were moved (or folder was already empty).
                leftover = _list_direct_children(service, folder["id"])
                if leftover:
                    print(
                        f"Drive alias still has {len(leftover)} child(ren), skip trash: {folder.get('name')}"
                        f" (foreign_skipped={skipped_foreign})",
                        flush=True,
                    )
                    if merge_log is not None:
                        merge_log.append(
                            {
                                "from": folder.get("name") or "",
                                "to": key,
                                "moved": moved,
                                "trashed": False,
                                "reason": "nonempty",
                                "foreignSkipped": skipped_foreign,
                            }
                        )
                    continue
                trashed_ok = _trash_file(service, folder["id"])
                print(
                    f"Drive alias merged {folder.get('name')} → {key} "
                    f"(moved={moved} trashed={trashed_ok} foreign_skipped={skipped_foreign})",
                    flush=True,
                )
                if merge_log is not None:
                    merge_log.append(
                        {
                            "from": folder.get("name") or "",
                            "to": key,
                            "moved": moved,
                            "trashed": bool(trashed_ok),
                            "foreignSkipped": skipped_foreign,
                        }
                    )
            except Exception as exc:
                print(f"Drive alias merge skipped {folder.get('name')}: {exc}", flush=True)
                if merge_log is not None:
                    merge_log.append(
                        {
                            "from": folder.get("name") or "",
                            "to": key,
                            "trashed": False,
                            "error": str(exc)[:200],
                        }
                    )
        # After merge, collapse historical Study-ID PDF copies into one clinic PDF.
        try:
            _dedupe_same_name_clinic_pdfs(service, preferred["id"], key, log=merge_log)
        except Exception as dedupe_exc:
            print(f"Drive PDF dedupe skipped {key}: {dedupe_exc}", flush=True)
        return preferred["id"]
    return _create_folder(service, root_id, key)


def patient_key_aliases(patient_key: str) -> list[str]:
    key = _sanitize(patient_key)[:120] or "anon"
    aliases = [key]
    if "_" in key:
        head = key.split("_", 1)[0]
        if head and head not in aliases:
            aliases.append(head)
    return aliases


def collapse_drive_name_duplicates(
    *, service=None, folder_id: str = ""
) -> Dict[str, Any]:
    """Minimal fix: one Drive folder per person name stem. Keeper = highest Study ID (prefer 101+).

    Moves all children into the keeper, then trashes empty alias folders.
    Does not require a program patient list.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "beforeCount": 0,
        "afterCount": 0,
        "merged": [],
        "trashed": [],
        "keepers": [],
        "errors": [],
        "mode": "stem_collapse",
    }
    try:
        if service is None:
            if not drive_configured():
                # Still try list+write via OAuth/SA — drive_configured can be overly strict.
                pass
            try:
                service, folder_id = _build_service()
            except Exception as exc:
                out["errors"].append({"build": str(exc)[:200]})
                service, folder_id = None, ""
            if service is None:
                try:
                    from drive_oauth import oauth_drive_service, oauth_folder_id

                    service = oauth_drive_service()
                    folder_id = oauth_folder_id() or folder_id
                except Exception as exc:
                    out["errors"].append({"oauth": str(exc)[:200]})
            if service is None:
                try:
                    service, folder_id = _sa_list_service()
                except Exception as exc:
                    out["errors"].append({"sa": str(exc)[:200]})
                    service, folder_id = None, ""
        # Always use the configured clinic backup folder (same as folder-status).
        parent_id = (clinic_folder_id() or folder_id or "").strip()
        if service is None or not parent_id:
            out["reason"] = "drive_init_failed"
            out["folderId"] = parent_id
            out["serviceOk"] = service is not None
            return out
        out["folderId"] = parent_id
        out["serviceOk"] = True

        def _keep_name(name: str) -> bool:
            raw = (name or "").strip()
            if not raw or raw in ("_system", "u1", TEAM_ROOT_NAME) or raw.startswith("_"):
                return False
            if len(raw) >= 2 and raw[0] == "u" and raw[1:].isdigit():
                return False
            return True

        # Same listing path as list_clinic_folder (proven to see ~58 folders).
        children = _list_direct_children(service, parent_id)
        folders = [
            {"id": item.get("id") or "", "name": item.get("name") or ""}
            for item in children
            if (item.get("mimeType") == FOLDER_MIME)
            and _keep_name(item.get("name") or "")
            and (item.get("id") or "")
        ]
        out["beforeCount"] = len(folders)
        out["beforeFolders"] = sorted(f.get("name") or "" for f in folders)
        if not folders:
            out["ok"] = True
            out["note"] = "no_patient_folders_listed"
            out["rawChildCount"] = len(children)
            return out

        by_stem: Dict[str, List[Dict[str, str]]] = {}
        for folder in folders:
            name = folder.get("name") or ""
            stem = _folder_name_stem(name)
            key = stem if len(stem) >= 3 else name
            by_stem.setdefault(key, []).append(folder)

        merge_log: List[Dict[str, Any]] = []
        for group in by_stem.values():
            if len(group) < 2:
                continue
            best = sorted(group, key=lambda f: _folder_study_rank(f.get("name") or ""), reverse=True)[0]
            keeper = best.get("name") or ""
            if not keeper:
                continue
            out["keepers"].append(keeper)
            try:
                _patient_folder(service, parent_id, keeper, merge_log=merge_log)
            except Exception as exc:
                out["errors"].append({"keeper": keeper, "error": str(exc)[:200]})
                print(f"Drive stem collapse {keeper}: {exc}", flush=True)

        out["merged"] = [row for row in merge_log if row.get("from")]
        out["trashed"] = [row for row in merge_log if row.get("trashed")]

        # Second pass: force-remove empty same-stem aliases with OAuth (owner) credentials.
        oauth = None
        oauth_err = ""
        try:
            from drive_oauth import oauth_drive_service

            oauth = oauth_drive_service()
        except Exception as exc:
            oauth_err = str(exc)[:200]
        out["oauthWrite"] = oauth is not None
        if oauth_err:
            out["oauthError"] = oauth_err
        write_svc = oauth or service

        after_children = _list_direct_children(service, parent_id)
        after_folders = [
            {"id": item.get("id") or "", "name": item.get("name") or ""}
            for item in after_children
            if (item.get("mimeType") == FOLDER_MIME)
            and _keep_name(item.get("name") or "")
            and (item.get("id") or "")
        ]
        by_stem2: Dict[str, List[Dict[str, str]]] = {}
        for folder in after_folders:
            name = folder.get("name") or ""
            stem = _folder_name_stem(name)
            key = stem if len(stem) >= 3 else name
            by_stem2.setdefault(key, []).append(folder)

        force_trashed = []
        trash_errors = []
        for group in by_stem2.values():
            if len(group) < 2:
                continue
            best = sorted(group, key=lambda f: _folder_study_rank(f.get("name") or ""), reverse=True)[0]
            for folder in group:
                if folder["id"] == best["id"]:
                    continue
                kids = _list_direct_children(write_svc, folder["id"])
                keeper_stem = _folder_name_stem(best.get("name") or "")
                # Move leftover kids that belong to this person; leave foreign PDFs for repair.
                for child in kids:
                    cid = child.get("id") or ""
                    cname = child.get("name") or ""
                    if not cid:
                        continue
                    if not _child_belongs_in_patient_folder(cname, keeper_stem, best.get("name") or ""):
                        continue
                    _move_file(write_svc, cid, folder["id"], best["id"], cname)
                kids2 = _list_direct_children(write_svc, folder["id"])
                if kids2:
                    trash_errors.append(
                        {"name": folder.get("name"), "reason": f"still_has_{len(kids2)}_children"}
                    )
                    continue
                try:
                    write_svc.files().update(
                        fileId=folder["id"], body={"trashed": True}, **_write_flags()
                    ).execute()
                    force_trashed.append(folder.get("name") or "")
                except Exception as exc:
                    try:
                        write_svc.files().delete(fileId=folder["id"], **_write_flags()).execute()
                        force_trashed.append(folder.get("name") or "")
                    except Exception as del_exc:
                        trash_errors.append(
                            {
                                "name": folder.get("name"),
                                "error": f"{exc} | {del_exc}"[:300],
                            }
                        )

        out["forceTrashed"] = force_trashed
        out["trashErrors"] = trash_errors[:20]
        out["trashed"] = list(out["trashed"]) + [{"from": n, "trashed": True, "force": True} for n in force_trashed]

        final_children = _list_direct_children(service, parent_id)
        after = [
            item.get("name") or ""
            for item in final_children
            if (item.get("mimeType") == FOLDER_MIME) and _keep_name(item.get("name") or "")
        ]
        out["afterCount"] = len(after)
        out["afterFolders"] = sorted(after)
        try:
            repaired = repair_misplaced_drive_files(service=service, folder_id=parent_id)
            out["repair"] = {
                "ok": repaired.get("ok"),
                "movedCount": len(repaired.get("moved") or []),
                "created": repaired.get("created") or [],
            }
        except Exception as repair_exc:
            out["repair"] = {"ok": False, "error": str(repair_exc)[:200]}
        try:
            pdf_dedupe = dedupe_clinic_pdfs_in_backups(service=service, folder_id=parent_id)
            out["pdfDedupe"] = {
                "ok": pdf_dedupe.get("ok"),
                "withDupes": pdf_dedupe.get("withDupes"),
                "trashedCount": pdf_dedupe.get("trashedCount") or len(pdf_dedupe.get("trashed") or []),
            }
        except Exception as pdf_exc:
            out["pdfDedupe"] = {"ok": False, "error": str(pdf_exc)[:200]}
        out["ok"] = True
        print(
            f"Drive stem collapse: {out['beforeCount']} → {out['afterCount']} "
            f"(merged={len(out['merged'])} force_trashed={len(force_trashed)} trash_err={len(trash_errors)} "
            f"repaired={out.get('repair', {}).get('movedCount', 0)} "
            f"pdf_trashed={out.get('pdfDedupe', {}).get('trashedCount', 0)})",
            flush=True,
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        print(f"Drive stem collapse failed: {exc}", flush=True)
        return out


def repair_misplaced_drive_files(
    *, service=None, folder_id: str = ""
) -> Dict[str, Any]:
    """Move ``{StudyID}_{OtherName}.*`` files out of the wrong patient folder.

    Example: ``4_Zeynep.pdf`` sitting in ``119_Ahmet_sever`` → ``4_Zeynep`` (or existing
    canonical ``*_Zeynep`` folder). Creates the destination folder when missing.
    Untagged clinic artifacts (validation mp4/json) are left in place.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "moved": [],
        "created": [],
        "skipped": [],
        "errors": [],
        "mode": "repair_misplaced",
    }
    try:
        if service is None:
            try:
                service, folder_id = _build_service()
            except Exception:
                service, folder_id = None, folder_id or ""
            if service is None:
                try:
                    from drive_oauth import oauth_drive_service, oauth_folder_id

                    service = oauth_drive_service()
                    folder_id = oauth_folder_id() or folder_id
                except Exception as exc:
                    out["errors"].append({"oauth": str(exc)[:200]})
            if service is None:
                try:
                    service, folder_id = _sa_list_service()
                except Exception as exc:
                    out["errors"].append({"sa": str(exc)[:200]})
                    service, folder_id = None, ""
        parent_id = (clinic_folder_id() or folder_id or "").strip()
        if service is None or not parent_id:
            out["reason"] = "drive_init_failed"
            return out

        def _keep_name(name: str) -> bool:
            raw = (name or "").strip()
            if not raw or raw in ("_system", "u1", TEAM_ROOT_NAME) or raw.startswith("_"):
                return False
            if len(raw) >= 2 and raw[0] == "u" and raw[1:].isdigit():
                return False
            return True

        folders = [
            {"id": item.get("id") or "", "name": item.get("name") or ""}
            for item in _list_direct_children(service, parent_id)
            if (item.get("mimeType") == FOLDER_MIME)
            and _keep_name(item.get("name") or "")
            and (item.get("id") or "")
        ]
        # Prefer highest Study ID folder per name stem as destination.
        by_stem: Dict[str, Dict[str, str]] = {}
        for folder in folders:
            name = folder.get("name") or ""
            stem = _norm_stem(_folder_name_stem(name))
            if not stem or len(stem) < 2:
                continue
            prev = by_stem.get(stem)
            if prev is None or _folder_study_rank(name) > _folder_study_rank(prev.get("name") or ""):
                by_stem[stem] = folder

        for folder in folders:
            folder_name = folder.get("name") or ""
            folder_id_cur = folder.get("id") or ""
            folder_stem = _norm_stem(_folder_name_stem(folder_name))
            if not folder_id_cur:
                continue
            for child in _list_direct_children(service, folder_id_cur):
                if (child.get("mimeType") or "") == FOLDER_MIME:
                    continue
                cid = child.get("id") or ""
                cname = child.get("name") or ""
                if not cid or not cname:
                    continue
                file_stem_raw = _file_patient_stem(cname)
                if not file_stem_raw:
                    continue
                file_stem = _norm_stem(file_stem_raw)
                if not file_stem or file_stem == folder_stem:
                    continue
                # Wrong patient file in this folder — rehome.
                dest = by_stem.get(file_stem)
                if dest and dest.get("id") == folder_id_cur:
                    continue
                try:
                    if not dest:
                        # Prefer folder name matching the file's own StudyID_Name stem.
                        dest_key = _sanitize(Path(cname).stem)[:120] or f"x_{file_stem_raw}"
                        dest_id = _find_or_create_folder(service, parent_id, dest_key)
                        dest = {"id": dest_id, "name": dest_key}
                        by_stem[file_stem] = dest
                        out["created"].append(dest_key)
                    moved_id = _move_file(service, cid, folder_id_cur, dest["id"], cname)
                    if moved_id:
                        row = {
                            "file": cname,
                            "from": folder_name,
                            "to": dest.get("name") or "",
                        }
                        out["moved"].append(row)
                        print(
                            f"Drive repair moved {cname}: {folder_name} → {dest.get('name')}",
                            flush=True,
                        )
                    else:
                        out["errors"].append({"file": cname, "error": "move_failed"})
                except Exception as exc:
                    out["errors"].append({"file": cname, "error": str(exc)[:200]})

        out["ok"] = True
        out["movedCount"] = len(out["moved"])
        print(
            f"Drive misplaced repair: moved={len(out['moved'])} created={len(out['created'])} "
            f"errors={len(out['errors'])}",
            flush=True,
        )
        return out
    except Exception as exc:
        out["error"] = str(exc)[:400]
        print(f"Drive misplaced repair failed: {exc}", flush=True)
        return out


def reconcile_drive_to_program(
    program_patients: Optional[List[Dict[str, Any]]] = None,
    *,
    service=None,
    folder_id: str = "",
    upload_pdfs: bool = True,
) -> Dict[str, Any]:
    """Align NeuroLab_Backups 1:1 with the program patient list.

    - Canonical key = ``{StudyID}_{SanitizedName}`` (same-name merge prefers 101+).
    - Alias folders (same *name stem* only) → move matching children into keeper, then trash.
    - Never merge by Study ID prefix alone (``14_Ahmet`` ≠ ``14_betul``).
    - Repair pass moves wrongly-placed ``{id}_{OtherName}.*`` files to the correct folder.
    - PDF dedupe: one ``{StudyID}_{Name}.pdf`` per folder (prefer folder Study ID).
    - Does not delete unique files; only trashes empty aliases / duplicate same-name PDFs.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "beforeCount": 0,
        "afterCount": 0,
        "canonicalCount": 0,
        "canonicalKeys": [],
        "mergedAliases": [],
        "trashedAliases": [],
        "orphans": [],
        "errors": [],
        "patientsUploaded": 0,
    }
    if service is None:
        if not drive_configured():
            out["reason"] = "drive_unset"
            out["error"] = (
                "Google Drive is not connected. Open Connect Drive and sign in with the clinic Gmail, then retry Rebuild."
            )
            return out
        try:
            service, folder_id = _build_service()
        except Exception as build_exc:
            out["reason"] = "drive_init_failed"
            out["error"] = f"Drive OAuth failed: {str(build_exc)[:220]}"
            print(f"Drive reconcile build failed: {build_exc}", flush=True)
            return out
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        out["error"] = (
            "Drive OAuth token invalid or expired. Reconnect Drive (Connect Drive), then retry Rebuild."
        )
        return out

    from patient_drive_archive import (
        archive_patients,
        merge_patients,
        merge_same_name_patients,
        patient_drive_key,
    )

    raw = [p for p in (program_patients or []) if isinstance(p, dict)]
    patients = merge_same_name_patients(merge_patients(raw))
    active = [p for p in patients if not p.get("_archived")]
    archived_pts = [p for p in patients if p.get("_archived")]
    canon_keys: List[str] = []
    seen_keys: set[str] = set()
    for patient in active:
        key = patient_drive_key(patient)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        canon_keys.append(key)
    archived_keys: List[str] = []
    archived_seen: set[str] = set()
    for patient in archived_pts:
        key = patient_drive_key(patient)
        if not key or key in archived_seen or key in seen_keys:
            continue
        archived_seen.add(key)
        archived_keys.append(key)
    out["canonicalKeys"] = canon_keys
    out["canonicalCount"] = len(canon_keys)
    out["archivedKeys"] = archived_keys
    out["mode"] = "program"

    def _patientish(name: str) -> bool:
        raw_name = (name or "").strip()
        if not raw_name or _is_legacy_root(raw_name):
            return False
        if raw_name in ("_system",):
            return False
        return True

    before = [f for f in _list_child_folders(service, parent_id) if _patientish(f.get("name") or "")]
    out["beforeCount"] = len(before)
    out["beforeFolders"] = sorted(f.get("name") or "" for f in before)

    # HF disk may have no patients.json — still collapse same-name Drive forks (prefer 101+).
    if not canon_keys and before:
        by_stem: Dict[str, List[Dict[str, str]]] = {}
        for folder in before:
            name = folder.get("name") or ""
            stem = _folder_name_stem(name)
            group = stem if len(stem) >= 3 else name
            by_stem.setdefault(group, []).append(folder)
        for folders in by_stem.values():
            if len(folders) < 2:
                continue
            best = sorted(
                folders,
                key=lambda folder: _folder_study_rank(folder.get("name") or ""),
                reverse=True,
            )[0]
            key = best.get("name") or ""
            if key and key not in seen_keys:
                seen_keys.add(key)
                canon_keys.append(key)
        out["canonicalKeys"] = canon_keys
        out["canonicalCount"] = len(canon_keys)
        out["mode"] = "stem_collapse_no_program"
        print(
            f"Drive reconcile fallback: no program patients; collapsing {len(canon_keys)} stem group(s)",
            flush=True,
        )

    # Always stem-collapse first (works even with empty program list on HF disk).
    merge_log: List[Dict[str, Any]] = []
    keep_ids: set[str] = set()
    try:
        collapsed = collapse_drive_name_duplicates(service=service, folder_id=parent_id)
        out["stemCollapse"] = {
            "beforeCount": collapsed.get("beforeCount"),
            "afterCount": collapsed.get("afterCount"),
            "merged": len(collapsed.get("merged") or []),
            "trashed": len(collapsed.get("trashed") or []),
            "keepers": collapsed.get("keepers") or [],
        }
        out["beforeCount"] = collapsed.get("beforeCount") or out["beforeCount"]
        for row in collapsed.get("merged") or []:
            merge_log.append(row)
    except Exception as exc:
        out["errors"].append({"stemCollapse": str(exc)[:200]})
        print(f"Drive stem collapse skipped: {exc}", flush=True)

    for key in canon_keys:
        try:
            fid = _patient_folder(service, parent_id, key, merge_log=merge_log)
            if fid:
                keep_ids.add(fid)
        except Exception as exc:
            out["errors"].append({"patientKey": key, "error": str(exc)[:200]})
            print(f"Drive reconcile folder {key}: {exc}", flush=True)

    out["mergedAliases"] = [row for row in merge_log if row.get("from")]
    out["trashedAliases"] = [row for row in merge_log if row.get("trashed")]

    # Second sweep: leftover same-STEM folders only (never Study-ID head alone).
    canon_stems = {
        _norm_stem(_folder_name_stem(k)): k
        for k in canon_keys
        if len(_folder_name_stem(k)) >= 3
    }
    for folder in _list_child_folders(service, parent_id):
        name = folder.get("name") or ""
        fid = folder.get("id") or ""
        if not fid or not _patientish(name) or fid in keep_ids or name in seen_keys:
            continue
        if name in archived_keys or name in archived_seen:
            # Will be moved under Archive/ below — not an active orphan.
            continue
        stem = _norm_stem(_folder_name_stem(name))
        target = canon_stems.get(stem) if stem else None
        if not target:
            out["orphans"].append(name)
            continue
        try:
            dest = _patient_folder(service, parent_id, target, merge_log=merge_log)
            if dest:
                keep_ids.add(dest)
        except Exception as exc:
            out["errors"].append({"patientKey": name, "error": str(exc)[:200]})

    out["mergedAliases"] = [row for row in merge_log if row.get("from")]
    out["trashedAliases"] = [row for row in merge_log if row.get("trashed")]

    # Keep archived patient folders under Archive/ (not mixed with active root).
    try:
        relocated = relocate_archived_patient_folders(
            service,
            parent_id,
            active_keys=canon_keys,
            archived_keys=archived_keys,
        )
        out["archiveRelocate"] = {
            "ok": relocated.get("ok"),
            "movedToArchive": relocated.get("movedToArchive") or [],
            "restoredFromArchive": relocated.get("restoredFromArchive") or [],
            "errors": (relocated.get("errors") or [])[:10],
        }
    except Exception as exc:
        out["errors"].append({"archiveRelocate": str(exc)[:200]})
        print(f"Drive Archive relocate skipped: {exc}", flush=True)

    # Repair: pull foreign StudyID_OtherName files out of wrong patient folders.
    try:
        repaired = repair_misplaced_drive_files(service=service, folder_id=parent_id)
        out["repair"] = {
            "ok": repaired.get("ok"),
            "moved": repaired.get("moved") or [],
            "created": repaired.get("created") or [],
            "errors": (repaired.get("errors") or [])[:10],
        }
    except Exception as exc:
        out["errors"].append({"repair": str(exc)[:200]})
        print(f"Drive misplaced-file repair skipped: {exc}", flush=True)

    if upload_pdfs and active:
        try:
            archived = archive_patients(active)
            out["patientsUploaded"] = int(archived.get("uploaded") or 0)
            out["archive"] = {"ok": archived.get("ok"), "uploaded": archived.get("uploaded")}
        except Exception as exc:
            out["errors"].append({"archive": str(exc)[:200]})
            print(f"Drive reconcile archive: {exc}", flush=True)

    # After merges (+ optional PDF upload), keep one clinic PDF per patient folder.
    try:
        pdf_dedupe = dedupe_clinic_pdfs_in_backups(service=service, folder_id=parent_id)
        out["pdfDedupe"] = {
            "ok": pdf_dedupe.get("ok"),
            "withDupes": pdf_dedupe.get("withDupes"),
            "trashedCount": pdf_dedupe.get("trashedCount") or len(pdf_dedupe.get("trashed") or []),
            "trashed": (pdf_dedupe.get("trashed") or [])[:40],
        }
    except Exception as exc:
        out["errors"].append({"pdfDedupe": str(exc)[:200]})
        print(f"Drive PDF dedupe skipped: {exc}", flush=True)

    after = [f for f in _list_child_folders(service, parent_id) if _patientish(f.get("name") or "")]
    out["afterCount"] = len(after)
    out["afterFolders"] = sorted(f.get("name") or "" for f in after)
    out["ok"] = True
    print(
        f"Drive reconcile: before={out['beforeCount']} after={out['afterCount']} "
        f"canonical={out['canonicalCount']} trashed_aliases={len(out['trashedAliases'])}",
        flush=True,
    )
    return out


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
        keep_id = files[0]["id"]
        service.files().update(
            fileId=keep_id, media_body=media, **_write_flags()
        ).execute()
        _share_with_owner(service, keep_id)
        for extra in files[1:]:
            extra_id = extra.get("id") or ""
            if extra_id and extra_id != keep_id:
                _trash_file(service, extra_id)
        return keep_id
    created = service.files().create(
        body={"name": name, "parents": [parent_id]},
        media_body=media,
        fields="id",
        **_write_flags(),
    ).execute()
    _share_with_owner(service, created["id"])
    return created["id"]


_DOC_SUBFOLDERS = {"videos", "reports", "data"}


def trash_same_kind_aliases(
    service,
    folder_id: str,
    keep_name: str,
    *,
    keep_id: str = "",
    folder_key: str = "",
) -> List[str]:
    """Trash leftover files of the same document kind; keep ``keep_id`` / ``keep_name``."""
    from drive_doc_identity import should_trash_as_alias

    trashed: List[str] = []
    if not folder_id or not keep_name:
        return trashed
    folders = [folder_id]
    try:
        for child in _list_direct_children(service, folder_id):
            mime = child.get("mimeType") or ""
            name = (child.get("name") or "").strip().lower()
            cid = child.get("id") or ""
            if mime == FOLDER_MIME and name in _DOC_SUBFOLDERS and cid:
                folders.append(cid)
    except Exception as exc:
        print(f"Drive alias folder scan skipped: {exc}", flush=True)
        folders = [folder_id]
    seen: set[str] = set()
    for fid in folders:
        try:
            children = _list_direct_children(service, fid)
        except Exception as exc:
            print(f"Drive alias list skipped: {exc}", flush=True)
            continue
        for child in children:
            cid = child.get("id") or ""
            cname = child.get("name") or ""
            if not cid or cid in seen:
                continue
            if not should_trash_as_alias(
                cname,
                keep_name,
                folder_key=folder_key,
                keep_id=keep_id,
                child_id=cid,
            ):
                continue
            if _trash_file(service, cid):
                seen.add(cid)
                trashed.append(cname)
    if trashed:
        print(f"Drive replaced {keep_name}; trashed aliases {trashed}", flush=True)
    return trashed


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
        drive_name = clinic_drive_filename(_sanitize(name) or src.name, patient_key=key)
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
        trash_same_kind_aliases(
            service, parent, drive_name, keep_id=file_id, folder_key=key
        )
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
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
            **_list_flags(),
        ).execute()
        batch = res.get("files") or []
        scanned += len(batch)
        items.extend(batch)
        page = res.get("nextPageToken")
        if not page:
            break
    return items


def recovered_drive_video_name(name: str) -> Optional[str]:
    """Map any recovered clinic mp4 onto {phase}_validation.mp4 in the patient folder."""
    raw = (name or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if not lower.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return None
    stem = Path(raw).stem
    for suffix in (
        "_validation_unified",
        "_unified_validation",
        "_validation_original",
        "_original",
        "_validation",
    ):
        if stem.lower().endswith(suffix):
            phase = stem[: -len(suffix)]
            break
    else:
        phase = stem
    phase = _sanitize(phase) or "baseline"
    if not phase.endswith("_validation"):
        phase = f"{phase}_validation"
    return f"{phase}.mp4"


# Drive's files.list hides trashed items unless the query says trashed=true.
_TRASH_FOLDER_QUERY = (
    "trashed=true and mimeType='application/vnd.google-apps.folder' and ("
    "name='team_patients' or name='u1'"
    ")"
)
_TRASH_VIDEO_QUERY = (
    "trashed=true and ("
    "name contains '_original.mp4' or name contains '_validation.mp4' "
    "or name contains 'unified.mp4'"
    ")"
)


def _list_query_files(service, query: str, *, limit: int = 800) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    page = None
    scanned = 0
    while scanned < limit:
        res = service.files().list(
            q=query,
            spaces="drive",
            pageSize=100,
            pageToken=page,
            fields="nextPageToken, files(id, name, mimeType, parents)",
            **_list_flags(),
        ).execute()
        batch = res.get("files") or []
        scanned += len(batch)
        items.extend(batch)
        page = res.get("nextPageToken")
        if not page:
            break
    return items


def _list_trashed_files(service, *, limit: int = 800) -> List[Dict[str, Any]]:
    """Clinic trash only: nested layout folders plus session/validation mp4s."""
    _ = limit
    found: List[Dict[str, Any]] = []
    seen = set()
    for query in (_TRASH_FOLDER_QUERY, _TRASH_VIDEO_QUERY):
        for item in _list_query_files(service, query):
            file_id = item.get("id") or ""
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            found.append(item)
    return found


def _list_children_any(service, folder_id: str) -> List[Dict[str, Any]]:
    """List children even if the parent folder is in trash.

    Drive defaults to trashed=false, so a trashed team_patients tree is
    invisible unless we query trashed=true explicitly.
    """
    items: List[Dict[str, Any]] = []
    seen = set()
    for trashed in ("true", "false"):
        for item in _list_query_files(
            service, f"'{folder_id}' in parents and trashed={trashed}"
        ):
            file_id = item.get("id") or ""
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            items.append(item)
    return items


def _collect_videos_from_trashed_trees(service) -> List[Dict[str, Any]]:
    videos: List[Dict[str, Any]] = []
    seen = set()

    def _walk(svc, folder_id: str, parts: Tuple[str, ...], depth: int) -> None:
        if not folder_id or depth > 8:
            return
        for item in _list_children_any(svc, folder_id):
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            if mime == FOLDER_MIME:
                _walk(svc, file_id, parts + (name,), depth + 1)
                continue
            lower = name.lower()
            if lower.endswith((".mp4", ".mov", ".m4v", ".webm")) or mime.startswith("video/"):
                videos.append({**item, "parts": parts})

    walkers = [svc for svc in (service, _sa_service_or_none()) if svc is not None]
    for svc in walkers:
        for item in _list_trashed_files(svc):
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            if mime == FOLDER_MIME:
                extra: List[str] = []
                for walker in walkers:
                    extra = _parent_chain_names(walker, file_id)
                    if extra:
                        break
                start_parts = tuple(extra) if extra else (name,)
                for walker in walkers:
                    _walk(walker, file_id, start_parts, 0)
                continue
            lower = name.lower()
            if lower.endswith((".mp4", ".mov", ".m4v", ".webm")) or mime.startswith("video/"):
                if file_id not in seen:
                    seen.add(file_id)
                    videos.append(item)
    return videos


def _trashed_json_files(service) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    seen = set()
    walkers = [svc for svc in (service, _sa_service_or_none()) if svc is not None]

    def _walk(svc, folder_id: str, parts: Tuple[str, ...], depth: int) -> None:
        if not folder_id or depth > 8:
            return
        for item in _list_children_any(svc, folder_id):
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            if not file_id or file_id in seen:
                continue
            seen.add(file_id)
            if mime == FOLDER_MIME:
                _walk(svc, file_id, parts + (name,), depth + 1)
                continue
            if name.lower().endswith(".json"):
                found.append({**item, "parts": parts})

    for svc in walkers:
        for item in _list_trashed_files(svc):
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            name = item.get("name") or ""
            if mime == FOLDER_MIME and file_id:
                extra = _parent_chain_names(svc, file_id) or [name]
                _walk(svc, file_id, tuple(extra), 0)
    return found


def _parent_chain_names(service, file_id: str) -> List[str]:
    names: List[str] = []
    current = file_id
    seen = set()
    for _ in range(8):
        if not current or current in seen:
            break
        seen.add(current)
        try:
            meta = service.files().get(
                fileId=current,
                fields="id,name,parents",
                supportsAllDrives=True,
            ).execute()
        except Exception:
            break
        names.append(meta.get("name") or "")
        parents = meta.get("parents") or []
        current = parents[0] if parents else ""
    return names


def _looks_like_patient_key(name: str) -> bool:
    key = _sanitize(name or "")[:120]
    if not key or key.lower().endswith((".mp4", ".mov", ".m4v", ".webm", ".pdf", ".json", ".txt")):
        return False
    head = key.split("_", 1)[0]
    return head.isdigit() and len(key) >= 3


def _patient_key_from_chain(names: List[str]) -> str:
    skip = {
        TEAM_ROOT_NAME,
        "videos",
        "data",
        "reports",
        "u1",
        " NeuroLab_Backups",
        "NeuroLab_Backups",
        "RAED_AI_Backups",
        "RA_ED_AI_Backups",
        "_system",
        "My Drive",
        "My_Drive",
        "Drive",
    }
    numeric: List[str] = []
    other: List[str] = []
    for name in names:
        raw = (name or "").strip()
        if not raw or raw in skip or raw.startswith("_"):
            continue
        if len(raw) >= 2 and raw[0] == "u" and raw[1:].isdigit():
            continue
        key = _sanitize(raw)[:120]
        if not key or key in skip:
            continue
        if key.lower().endswith((".mp4", ".mov", ".m4v", ".webm", ".pdf", ".json", ".txt")):
            continue
        if _looks_like_patient_key(key):
            numeric.append(key)
        else:
            other.append(key)
    if numeric:
        return numeric[0]
    return other[0] if other else ""


def restore_trashed_videos_to_patients() -> Dict[str, Any]:
    """Pull clinic mp4s out of Drive trash into each patient folder next to the PDF."""
    out: Dict[str, Any] = {"ok": False, "restored": [], "skipped": []}
    if not drive_configured():
        out["reason"] = "drive_unset"
        return out
    service, folder_id = _build_service()
    parent_id = folder_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out
    collected = _collect_videos_from_trashed_trees(service)
    out["scanned"] = len(collected)
    for item in collected:
        name = item.get("name") or ""
        mime = item.get("mimeType") or ""
        file_id = item.get("id") or ""
        lower = name.lower()
        if not file_id:
            continue
        if not (lower.endswith((".mp4", ".mov", ".m4v", ".webm")) or mime.startswith("video/")):
            continue
        drive_name = recovered_drive_video_name(name)
        if not drive_name:
            out["skipped"].append({"id": file_id, "name": name, "reason": "not_clinic_video"})
            continue
        chain = list(item.get("parts") or ()) + _parent_chain_names(service, file_id)
        key = _patient_key_from_chain(chain)
        if not key:
            out["skipped"].append({"id": file_id, "name": name, "reason": "no_patient_folder"})
            continue
        if not _looks_like_patient_key(key):
            out["skipped"].append(
                {"id": file_id, "name": name, "reason": "not_patient_key", "key": key}
            )
            continue
        dest = _find_or_create_folder(service, parent_id, key)
        old_parent = (item.get("parents") or [""])[0]
        moved = _untrash_into_folder(service, file_id, dest, drive_name, old_parent)
        if moved:
            out["restored"].append(
                {
                    "id": file_id,
                    "patientKey": key,
                    "name": drive_name,
                    "from": name,
                    "parts": list(item.get("parts") or ())[:8],
                }
            )
        else:
            out["skipped"].append({"id": file_id, "name": name, "reason": "untrash_failed"})
    rehomed = rehome_misplaced_clinic_videos(service, parent_id)
    leftover = _trash_legacy_layout(service, parent_id, set())
    out["trashedLeftover"] = leftover
    out["rehomed"] = rehomed
    out["ok"] = True
    out["count"] = len(out["restored"]) + len(rehomed.get("moved") or [])
    return out


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


def _untrash_into_folder(
    service, file_id: str, dest: str, drive_name: str, old_parent: str = ""
) -> str:
    """Move a trashed mp4 into the live patient folder, next to the PDF."""

    def _run(svc) -> str:
        kwargs = dict(_write_flags())
        if dest:
            kwargs["addParents"] = dest
        if old_parent and old_parent != dest:
            kwargs["removeParents"] = old_parent
        svc.files().update(
            fileId=file_id,
            body={"trashed": False, "name": drive_name},
            **kwargs,
        ).execute()
        _share_with_owner(svc, file_id)
        return file_id

    try:
        return _run(service)
    except Exception as exc:
        sa = _sa_service_or_none()
        if sa is None:
            print(f"Drive untrash skipped {file_id}: {exc}", flush=True)
            return ""
        try:
            return _run(sa)
        except Exception as sa_exc:
            print(f"Drive untrash skipped {file_id}: {sa_exc}", flush=True)
            return ""


def _trash_file(service, file_id: str) -> bool:
    if not file_id:
        return False

    def _run(svc) -> bool:
        svc.files().update(fileId=file_id, body={"trashed": True}, **_write_flags()).execute()
        return True

    try:
        return _run(service)
    except Exception as exc:
        print(f"Drive trash primary failed {file_id}: {exc}", flush=True)
    for factory in (_sa_service_or_none,):
        alt = factory()
        if alt is None:
            continue
        try:
            return _run(alt)
        except Exception as sa_exc:
            print(f"Drive trash alt failed {file_id}: {sa_exc}", flush=True)
    try:
        from drive_oauth import oauth_drive_service

        oauth = oauth_drive_service()
        if oauth is not None:
            return _run(oauth)
    except Exception as oauth_exc:
        print(f"Drive trash oauth failed {file_id}: {oauth_exc}", flush=True)
    try:
        # Last resort: permanent delete (empty alias folders only callers should reach here).
        service.files().delete(fileId=file_id, **_write_flags()).execute()
        return True
    except Exception as del_exc:
        print(f"Drive delete skipped {file_id}: {del_exc}", flush=True)
        return False


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


def reorganize_clinic_folder(
    *, service=None, folder_id: str = "", program_patients: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Rebuild NeuroLab_Backups as one folder per program patient: PDF + matching overlay videos."""
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
        mapped = clinic_drive_filename(name, patient_key=key)
        if mapped and mapped.endswith(".mp4"):
            bucket["videos"].append({**item, "driveName": mapped})
        elif mapped and mapped.endswith(".pdf"):
            bucket["pdfs"].append({**item, "driveName": mapped})

    for item in _trashed_json_files(service):
        key = _patient_key_from_chain(list(item.get("parts") or ()) + [item.get("name") or ""])
        if not key:
            key = _patient_key_from_parts(tuple(item.get("parts") or ()))
        if not key:
            continue
        grouped.setdefault(key, {"json": {}, "videos": [], "pdfs": []})
        json_candidates.setdefault(key, []).append(item)

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
        dest = merged.setdefault(canon, {"json": {}, "videos": [], "pdfs": [], "patient": None})
        dest["json"].update(bucket["json"])
        dest["videos"].extend(bucket["videos"])
        dest["pdfs"].extend(bucket["pdfs"])

    from patient_drive_archive import patient_drive_key, program_patient_record

    for patient in program_patients or []:
        if not isinstance(patient, dict):
            continue
        rec = program_patient_record(patient)
        key = patient_drive_key(rec)
        dest = merged.setdefault(key, {"json": {}, "videos": [], "pdfs": [], "patient": None})
        dest["patient"] = rec

    keep_folder_ids: set[str] = set()
    from patient_drive_archive import patient_drive_key
    from patient_pdf import build_patient_pdf, patient_pdf_filename

    for canon, bucket in merged.items():
        rec: Dict[str, Any] = {"patientKey": canon, "files": []}
        try:
            patient = bucket.get("patient") or _assemble_patient_record(bucket["json"])
            folder_name = patient_drive_key(patient) if patient else canon
            folder_name = _sanitize(folder_name)[:120] or canon
            dest_id = _patient_folder(service, parent_id, folder_name)
            keep_folder_ids.add(dest_id)
            rec["patientKey"] = folder_name
            if patient:
                pdf_name = patient_pdf_filename(patient)
                pdf_bytes = build_patient_pdf(patient)
                file_id = _upsert_bytes(service, dest_id, pdf_name, pdf_bytes, "application/pdf")
                trash_same_kind_aliases(
                    service, dest_id, pdf_name, keep_id=file_id, folder_key=folder_name
                )
                rec["files"].append({"name": pdf_name, "id": file_id})
                out["pdfs"] += 1
            placed: Dict[str, str] = {}
            for video in bucket["videos"]:
                vid = video.get("id") or ""
                mapped = video.get("driveName") or clinic_drive_filename(
                    video.get("name") or "", patient_key=folder_name
                )
                if not vid:
                    continue
                if mapped and mapped.lower() in ALLOWED_VALIDATION_VIDEOS:
                    if mapped in placed and placed[mapped] != vid:
                        _trash_file(service, vid)
                        out["trashed"].append(vid)
                        continue
                    parent = video.get("parent") or ""
                    if parent != dest_id or (video.get("name") or "") != mapped:
                        vid = _move_file(service, vid, parent, dest_id, mapped) or vid
                    placed[mapped] = vid
                    rec["files"].append({"name": mapped, "id": vid})
                    out["videos"] += 1
                    out["moved"].append(vid)
                    continue
                _trash_file(service, vid)
                out["trashed"].append(vid)
            placed_ids = set(placed.values())
            for child in _list_direct_children(service, dest_id):
                child_id = child.get("id") or ""
                child_name = child.get("name") or ""
                lower = child_name.lower()
                if not child_id or child_id in placed_ids:
                    continue
                if not lower.endswith((".mp4", ".mov", ".m4v", ".webm")):
                    continue
                mapped = clinic_drive_filename(child_name, patient_key=folder_name)
                if mapped and mapped.lower() in ALLOWED_VALIDATION_VIDEOS:
                    if mapped in placed and placed[mapped] != child_id:
                        _trash_file(service, child_id)
                        out["trashed"].append(child_id)
                        continue
                    if child_name != mapped:
                        child_id = _move_file(service, child_id, dest_id, dest_id, mapped) or child_id
                    placed[mapped] = child_id
                    rec["files"].append({"name": mapped, "id": child_id})
                    out["videos"] += 1
                    continue
                _trash_file(service, child_id)
                out["trashed"].append(child_id)
            for mapped_name, vid in list(placed.items()):
                trash_same_kind_aliases(
                    service, dest_id, mapped_name, keep_id=vid, folder_key=folder_name
                )
        except Exception as exc:
            rec["error"] = str(exc)[:200]
            print(f"Drive rebuild patient {canon}: {exc}", flush=True)
        out["patients"].append(rec)

    leftover = _trash_legacy_layout(service, parent_id, keep_folder_ids)
    out["trashed"].extend(leftover)
    out["ok"] = True
    out["patientCount"] = len(out["patients"])
    return out


def _patient_keys_from_trashed_layout(service) -> List[str]:
    keys: List[str] = []
    seen = set()
    walkers = [svc for svc in (service, _sa_service_or_none()) if svc is not None]

    def _walk(svc, folder_id: str, parts: Tuple[str, ...], depth: int) -> None:
        if not folder_id or depth > 8:
            return
        for item in _list_children_any(svc, folder_id):
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            if not file_id:
                continue
            if mime == FOLDER_MIME:
                if name.lower() == "videos":
                    key = _patient_key_from_chain(list(parts) + [name])
                    if _looks_like_patient_key(key) and key not in seen:
                        seen.add(key)
                        keys.append(key)
                _walk(svc, file_id, parts + (name,), depth + 1)
                continue
            lower = name.lower()
            if lower.endswith((".mp4", ".mov", ".m4v", ".webm")) or str(mime).startswith("video/"):
                key = _patient_key_from_chain(list(parts) + [name])
                if _looks_like_patient_key(key) and key not in seen:
                    seen.add(key)
                    keys.append(key)

    for svc in walkers:
        for item in _list_trashed_files(svc):
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            file_id = item.get("id") or ""
            if mime != FOLDER_MIME or not file_id:
                continue
            extra = _parent_chain_names(svc, file_id) or [name]
            _walk(svc, file_id, tuple(extra), 0)
    return keys


def _live_patient_folders_with_videos(service, parent_id: str) -> set[str]:
    have: set[str] = set()
    for item in _list_direct_children(service, parent_id):
        name = item.get("name") or ""
        mime = item.get("mimeType") or ""
        file_id = item.get("id") or ""
        if mime != FOLDER_MIME or not _looks_like_patient_key(name) or not file_id:
            continue
        for child in _list_direct_children(service, file_id):
            child_name = (child.get("name") or "").lower()
            if child_name.endswith(".mp4") or child_name.endswith("_validation.mp4"):
                have.add(_sanitize(name)[:120])
                break
    return have


def rehome_misplaced_clinic_videos(service=None, parent_id: str = "") -> Dict[str, Any]:
    """Move videos that landed in My_Drive into real patient folders."""
    out: Dict[str, Any] = {"ok": False, "moved": [], "skipped": []}
    if service is None:
        if not drive_configured():
            out["reason"] = "drive_unset"
            return out
        service, parent_id = _build_service()
    parent_id = parent_id or clinic_folder_id()
    if service is None or not parent_id:
        out["reason"] = "drive_init_failed"
        return out
    misplaced_id = _find_folder(service, parent_id, "My_Drive")
    if not misplaced_id:
        out["ok"] = True
        out["reason"] = "no_my_drive_folder"
        return out
    videos = [
        item
        for item in _list_direct_children(service, misplaced_id)
        if ((item.get("name") or "").lower().endswith((".mp4", ".mov", ".m4v", ".webm"))
            or str(item.get("mimeType") or "").startswith("video/"))
    ]
    dest_key = "111_Douan_ertan"
    dest = _find_or_create_folder(service, parent_id, dest_key)
    out["targets"] = [dest_key]
    for index, video in enumerate(videos):
        file_id = video.get("id") or ""
        name = video.get("name") or "baseline_validation.mp4"
        if not file_id:
            continue
        drive_name = "baseline_validation.mp4" if index == 0 else f"baseline_{index + 1}_validation.mp4"
        moved = _move_file(service, file_id, misplaced_id, dest, drive_name)
        if moved:
            out["moved"].append({"id": file_id, "patientKey": dest_key, "name": drive_name})
        else:
            out["skipped"].append({"id": file_id, "name": name, "reason": "move_failed"})
    if not _list_direct_children(service, misplaced_id):
        _trash_file(service, misplaced_id)
        out["trashedMyDrive"] = True
    out["ok"] = True
    return out


def _is_legacy_root(name: str) -> bool:
    raw = (name or "").strip()
    if raw in CLINIC_SYSTEM_FOLDERS or raw in (TEAM_ROOT_NAME, "u1") or raw.startswith("_"):
        return True
    if len(raw) >= 2 and raw[0] == "u" and raw[1:].isdigit():
        return True
    if raw in ("NEUROLAB_VIDEOS_HERE.txt", "_NEUROLAB_DRIVE_OK.json"):
        return True
    return False


def _move_folder(service, folder_id: str, old_parent: str, new_parent: str) -> bool:
    """Reparent a Drive folder (e.g. active root ↔ Archive)."""
    if not folder_id or not new_parent:
        return False
    if old_parent and old_parent == new_parent:
        return True

    def _run(svc) -> bool:
        kwargs = dict(_write_flags())
        if old_parent and old_parent != new_parent:
            kwargs["addParents"] = new_parent
            kwargs["removeParents"] = old_parent
        elif not old_parent:
            kwargs["addParents"] = new_parent
        svc.files().update(fileId=folder_id, body={}, **kwargs).execute()
        return True

    try:
        return _run(service)
    except Exception as exc:
        print(f"Drive folder move skipped {folder_id}: {exc}", flush=True)
        try:
            sa = _sa_service_or_none()
            if sa is None:
                return False
            return _run(sa)
        except Exception as sa_exc:
            print(f"Drive folder move skipped {folder_id}: {sa_exc}", flush=True)
            return False


def relocate_archived_patient_folders(
    service,
    parent_id: str,
    *,
    active_keys: Iterable[str],
    archived_keys: Iterable[str],
) -> Dict[str, Any]:
    """Keep archived patient folders under NeuroLab_Backups/Archive only.

    Active patients stay at the backups root. Restored patients are moved back
    from Archive → root. Does not trash content.
    """
    out: Dict[str, Any] = {
        "ok": False,
        "archiveFolderId": "",
        "movedToArchive": [],
        "restoredFromArchive": [],
        "errors": [],
    }
    if service is None or not parent_id:
        out["reason"] = "drive_unset"
        return out

    active_set = {(_sanitize(k) or "").strip() for k in (active_keys or []) if (_sanitize(k) or "").strip()}
    archived_set = {
        (_sanitize(k) or "").strip() for k in (archived_keys or []) if (_sanitize(k) or "").strip()
    }
    # Prefer archive when a key is somehow listed in both.
    active_set -= archived_set

    try:
        archive_id = _find_or_create_folder(service, parent_id, ARCHIVE_FOLDER_NAME)
    except Exception as exc:
        out["errors"].append({"archiveFolder": str(exc)[:200]})
        return out
    out["archiveFolderId"] = archive_id

    root_folders = {
        (f.get("name") or ""): f
        for f in _list_child_folders(service, parent_id)
        if (f.get("name") or "") and not _is_legacy_root(f.get("name") or "")
    }
    archive_folders = {
        (f.get("name") or ""): f
        for f in _list_child_folders(service, archive_id)
        if (f.get("name") or "")
    }

    # Move archived (or unknown-but-matching archived keys) from root → Archive.
    for name, folder in list(root_folders.items()):
        fid = folder.get("id") or ""
        if not fid:
            continue
        if name in active_set:
            continue
        should_archive = name in archived_set
        if not should_archive:
            # Stem match against archived keys (alias StudyID_Name forks).
            stem = _norm_stem(_folder_name_stem(name))
            if stem and len(stem) >= 3:
                for akey in archived_set:
                    if _norm_stem(_folder_name_stem(akey)) == stem:
                        should_archive = True
                        break
        if not should_archive:
            continue
        try:
            if _move_folder(service, fid, parent_id, archive_id):
                out["movedToArchive"].append(name)
                archive_folders[name] = folder
                root_folders.pop(name, None)
            else:
                out["errors"].append({"moveToArchive": name})
        except Exception as exc:
            out["errors"].append({"moveToArchive": name, "error": str(exc)[:160]})

    # Restore active patients that still sit under Archive → root.
    for name, folder in list(archive_folders.items()):
        fid = folder.get("id") or ""
        if not fid or name not in active_set:
            continue
        try:
            if _move_folder(service, fid, archive_id, parent_id):
                out["restoredFromArchive"].append(name)
            else:
                out["errors"].append({"restoreFromArchive": name})
        except Exception as exc:
            out["errors"].append({"restoreFromArchive": name, "error": str(exc)[:160]})

    out["ok"] = True
    print(
        f"Drive Archive relocate: toArchive={len(out['movedToArchive'])} "
        f"restored={len(out['restoredFromArchive'])}",
        flush=True,
    )
    return out


def upload_excel_bytes(
    name: str,
    content: bytes,
    *,
    service=None,
    folder_id: str = "",
) -> Dict[str, Any]:
    """Upsert a study Excel/CSV under NeuroLab_Backups/Excel/ (not patient folders)."""
    result: Dict[str, Any] = {"ok": False, "name": name}
    safe = _sanitize(name) or ""
    lower = safe.lower()
    if not content or not safe:
        result["reason"] = "empty"
        return result
    if not (lower.endswith(".xlsx") or lower.endswith(".xls") or lower.endswith(".csv")):
        result["reason"] = "not_excel"
        return result
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
    try:
        excel_parent = _find_or_create_folder(service, parent_id, EXCEL_FOLDER_NAME)
        file_id = _upsert_bytes(service, excel_parent, safe, content, _mime_for(safe))
        result["ok"] = True
        result["id"] = file_id
        result["folder"] = EXCEL_FOLDER_NAME
        return result
    except Exception as exc:
        result["error"] = str(exc)[:220]
        print(f"Drive Excel upload failed {safe}: {exc}", flush=True)
        return result


def _trash_legacy_layout(service, parent_id: str, keep_folder_ids: set[str]) -> List[str]:
    trashed: List[str] = []
    keep = set(keep_folder_ids)
    children = _list_direct_children(service, parent_id)
    kept_heads: set[str] = set()
    for item in children:
        if (item.get("id") or "") in keep:
            name = item.get("name") or ""
            head = name.split("_", 1)[0]
            if head:
                kept_heads.add(head)
    for item in children:
        file_id = item.get("id") or ""
        name = item.get("name") or ""
        mime = item.get("mimeType") or ""
        if not file_id:
            continue
        if mime == FOLDER_MIME and not _is_legacy_root(name):
            if file_id in keep:
                for child in _list_direct_children(service, file_id):
                    child_name = (child.get("name") or "").lower()
                    child_mime = child.get("mimeType") or ""
                    keep_child = child_mime != FOLDER_MIME and (
                        child_name.endswith(".pdf")
                        or child_name in ALLOWED_VALIDATION_VIDEOS
                    )
                    if not keep_child and child.get("id"):
                        _trash_file(service, child["id"])
                        trashed.append(child["id"])
                continue
            head = name.split("_", 1)[0]
            # Same Study ID as a kept canonical folder → leftover alias; trash it.
            if head and head in kept_heads:
                _trash_file(service, file_id)
                trashed.append(file_id)
                continue
            # Unknown patient folder not in this rebuild — leave content, drop nested junk only.
            for child in _list_direct_children(service, file_id):
                child_name = (child.get("name") or "").lower()
                child_mime = child.get("mimeType") or ""
                keep_child = child_mime != FOLDER_MIME and (
                    child_name.endswith(".pdf")
                    or child_name in ALLOWED_VALIDATION_VIDEOS
                )
                if not keep_child and child.get("id"):
                    _trash_file(service, child["id"])
                    trashed.append(child["id"])
            if not _list_direct_children(service, file_id):
                _trash_file(service, file_id)
                trashed.append(file_id)
            continue
        if file_id not in keep:
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
        samples: Dict[str, List[str]] = {}
        for item in children:
            name = item.get("name") or ""
            mime = item.get("mimeType") or ""
            if mime == FOLDER_MIME and item.get("id"):
                samples[name] = [
                    child.get("name") or ""
                    for child in _list_direct_children(service, item["id"])
                ]
        out["patientContents"] = samples
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
