#!/usr/bin/env python3
"""Wire Google user OAuth into Hugging Face auth.py Drive client."""
from __future__ import annotations

import sys
from pathlib import Path

SERVICE_OLD = '''def _drive_service():
    global _drive_service_instance
    if _drive_service_instance is not None:
        return _drive_service_instance
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_DRIVE_FOLDER_ID:
        return None
'''

SERVICE_SA_FALLBACK = '''def _drive_service():
    global _drive_service_instance
    if _drive_service_instance is not None:
        return _drive_service_instance
    try:
        from drive_oauth import oauth_drive_service

        oauth_svc = oauth_drive_service()
        if oauth_svc:
            _drive_service_instance = oauth_svc
            return _drive_service_instance
    except Exception as exc:
        print("OAuth Drive init:", exc, flush=True)
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_DRIVE_FOLDER_ID:
        return None
'''

SERVICE_NEW = '''def _drive_service():
    global _drive_service_instance
    if _drive_service_instance is not None:
        return _drive_service_instance
    try:
        from drive_oauth import oauth_client_configured, oauth_drive_service, oauth_ready

        if oauth_ready():
            oauth_svc = oauth_drive_service()
            if oauth_svc:
                _drive_service_instance = oauth_svc
                return _drive_service_instance
        if oauth_client_configured():
            # Personal Gmail Drive has no quota for service accounts.
            return None
    except Exception as exc:
        print("OAuth Drive init:", exc, flush=True)
        try:
            from drive_oauth import oauth_client_configured as _oauth_client_configured

            if _oauth_client_configured():
                return None
        except Exception:
            pass
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_DRIVE_FOLDER_ID:
        return None
'''

HEALTH_OLD = '''def _drive_health_summary() -> dict:
    out = {
        "configured": bool(GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID),
        "serviceInitialized": False,
        "folderReachable": False,
        "serviceAccountEmail": None,
        "folderIdHint": None,
        "folderName": None,
        "folderUrl": None,
        "videoCount": 0,
        "rootChildren": [],
        "error": None,
    }
    if not out["configured"]:
        out["error"] = "Missing GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_DRIVE_FOLDER_ID"
        return out
    fid = GOOGLE_DRIVE_FOLDER_ID or ""
    out["folderIdHint"] = f"{fid[:6]}…{fid[-4:]}" if len(fid) > 12 else fid
    try:
        out["serviceAccountEmail"] = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON).get("client_email")
    except Exception:
        pass
    service = _drive_service()
    if not service:
        out["error"] = "Drive client init failed (invalid JSON or Drive API disabled)"
        return out
'''

HEALTH_OAUTH = '''def _drive_health_summary() -> dict:
    out = {
        "configured": bool(GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID),
        "serviceInitialized": False,
        "folderReachable": False,
        "serviceAccountEmail": None,
        "folderIdHint": None,
        "folderName": None,
        "folderUrl": None,
        "videoCount": 0,
        "rootChildren": [],
        "error": None,
        "oauthReady": False,
        "oauthEmail": None,
        "oauthClientConfigured": False,
    }
    try:
        from drive_oauth import oauth_status

        ost = oauth_status()
        out["oauthReady"] = bool(ost.get("ready"))
        out["oauthEmail"] = ost.get("email")
        out["oauthClientConfigured"] = bool(ost.get("clientConfigured"))
        out["configured"] = bool(out["configured"] or out["oauthReady"])
    except Exception:
        pass
    if not out["configured"] and not out["oauthClientConfigured"]:
        out["error"] = "Open /connect-drive to link your Google account"
        return out
    fid = GOOGLE_DRIVE_FOLDER_ID or ""
    out["folderIdHint"] = f"{fid[:6]}…{fid[-4:]}" if len(fid) > 12 else fid
    try:
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            out["serviceAccountEmail"] = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON).get("client_email")
    except Exception:
        pass
    service = _drive_service()
    if not service:
        if out["oauthClientConfigured"] and not out["oauthReady"]:
            out["error"] = "OAuth client is set. Open /connect-drive and sign in with Google"
        else:
            out["error"] = "Drive client init failed"
        return out
'''

HEALTH_NEW = '''def _drive_health_summary() -> dict:
    out = {
        "configured": bool(GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_DRIVE_FOLDER_ID),
        "serviceInitialized": False,
        "folderReachable": False,
        "serviceAccountEmail": None,
        "folderIdHint": None,
        "folderName": None,
        "folderUrl": None,
        "videoCount": 0,
        "rootChildren": [],
        "error": None,
        "oauthReady": False,
        "oauthEmail": None,
        "oauthClientConfigured": False,
    }
    try:
        from drive_oauth import oauth_status

        ost = oauth_status()
        out["oauthReady"] = bool(ost.get("ready"))
        out["oauthEmail"] = ost.get("email")
        out["oauthClientConfigured"] = bool(ost.get("clientConfigured"))
        out["configured"] = bool(out["configured"] or out["oauthReady"])
    except Exception:
        pass
    if not out["configured"] and not out["oauthClientConfigured"]:
        out["error"] = "Open /connect-drive to link your Google account"
        return out
    fid = GOOGLE_DRIVE_FOLDER_ID or ""
    out["folderIdHint"] = f"{fid[:6]}…{fid[-4:]}" if len(fid) > 12 else fid
    try:
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            out["serviceAccountEmail"] = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON).get("client_email")
    except Exception:
        pass
    service = _drive_service()
    if not service:
        try:
            from drive_persist import list_clinic_folder

            inv = list_clinic_folder()
            out["folderReachable"] = bool(inv.get("ok"))
            out["folderName"] = inv.get("folderName")
            out["videoCount"] = inv.get("videoCount") or 0
            out["rootChildren"] = inv.get("rootChildren") or []
            out["jsonCount"] = inv.get("jsonCount") or 0
            out["fileCount"] = inv.get("fileCount") or 0
            out["folderEmpty"] = bool(inv.get("empty"))
        except Exception:
            pass
        if out["oauthClientConfigured"] and not out["oauthReady"]:
            out["error"] = "OAuth client is set. Open /connect-drive and sign in with Google"
        else:
            out["error"] = "Drive client init failed"
        return out
'''

REGISTER_MARK = "register_drive_oauth_routes(router, get_current_user)"
REGISTER_SNIPPET = """

from drive_oauth_routes import register_drive_oauth_routes

register_drive_oauth_routes(router, get_current_user)
"""

SNAPSHOT_OLD = '''            snap = json.dumps(p, ensure_ascii=False, indent=2).encode("utf-8")
            _drive_upsert_bytes(service, "patient.json", snap, "application/json", parent_id=pf)
'''
SNAPSHOT_NEW = '''            try:
                from patient_drive_archive import archive_patients

                archive_patients([p], user_id=user_id)
            except Exception as arch_exc:
                print("Patient program archive:", arch_exc, flush=True)
                snap = json.dumps(p, ensure_ascii=False, indent=2).encode("utf-8")
                _drive_upsert_bytes(service, "patient.json", snap, "application/json", parent_id=pf)
'''

EMPTY_FOLDERS_OLD = '''            pf = _drive_patient_folder(service, user_id, key)
            for sub in ("videos", "reports", "data"):
                _drive_find_or_create_folder(service, pf, sub)
            try:
                from patient_drive_archive import archive_patients

                archive_patients([p], user_id=user_id)
            except Exception as arch_exc:
                print("Patient program archive:", arch_exc, flush=True)
                snap = json.dumps(p, ensure_ascii=False, indent=2).encode("utf-8")
                _drive_upsert_bytes(service, "patient.json", snap, "application/json", parent_id=pf)
'''

EMPTY_FOLDERS_NEW = '''            try:
                from patient_drive_archive import archive_patients

                archive_patients([p], user_id=user_id)
                continue
            except Exception as arch_exc:
                print("Patient program archive:", arch_exc, flush=True)
            pf = _drive_patient_folder(service, user_id, key)
            snap = json.dumps(p, ensure_ascii=False, indent=2).encode("utf-8")
            _drive_upsert_bytes(service, "patient.json", snap, "application/json", parent_id=pf)
'''

BACKUP_FILE_OLD = '''        drive_name = name
    else:
        user_root = _drive_user_root_folder(service, user["id"])
        parent = user_root
        drive_name = f"neurolab_{user['id']}_{name}"
    try:
        file_id = _drive_upsert_bytes(service, drive_name, content, mime, parent_id=parent)
'''

BACKUP_FILE_NEW = '''        try:
            from drive_persist import clinic_drive_filename

            mapped = clinic_drive_filename(name)
        except Exception:
            mapped = name
        if mapped is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "validation_videos_only",
                "fileName": name,
            }
        drive_name = mapped
    else:
        user_root = _drive_user_root_folder(service, user["id"])
        parent = user_root
        drive_name = f"neurolab_{user['id']}_{name}"
    try:
        file_id = _drive_upsert_bytes(service, drive_name, content, mime, parent_id=parent)
'''

BACKUP_UPLOAD_OLD = '''    drive_name = _drive_sanitize_name(name)
    if not drive_name:
        raise HTTPException(status_code=400, detail="name required")
    sub = (subfolder or "videos").strip().lower()
'''

BACKUP_UPLOAD_NEW = '''    drive_name = _drive_sanitize_name(name)
    if not drive_name:
        raise HTTPException(status_code=400, detail="name required")
    try:
        from drive_persist import clinic_drive_filename

        mapped = clinic_drive_filename(drive_name)
    except Exception:
        mapped = drive_name
    if mapped is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "validation_videos_only",
            "fileName": drive_name,
        }
    drive_name = mapped
    sub = (subfolder or "videos").strip().lower()
'''

RESTORE_FILE_OLD = '''    for sc in scopes:
        parent = _drive_parent_for_patient_artifact(service, user["id"], safe_key, sub, sc)
        found = _drive_find_file_bytes(service, parent, name)
        if found:
            content, mime, out_name = found
            headers = {"Content-Disposition": f'inline; filename="{out_name}"'}
            return Response(content=content, media_type=mime, headers=headers)
    raise HTTPException(status_code=404, detail="File not found on Drive")
'''

RESTORE_FILE_NEW = '''    names = [name]
    try:
        from drive_persist import clinic_drive_filename

        mapped = clinic_drive_filename(name)
        if mapped and mapped not in names:
            names.append(mapped)
    except Exception:
        pass
    for sc in scopes:
        parent = _drive_parent_for_patient_artifact(service, user["id"], safe_key, sub, sc)
        for candidate in names:
            found = _drive_find_file_bytes(service, parent, candidate)
            if found:
                content, mime, out_name = found
                headers = {"Content-Disposition": f'inline; filename="{out_name}"'}
                return Response(content=content, media_type=mime, headers=headers)
    raise HTTPException(status_code=404, detail="File not found on Drive")
'''


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"already patched: {label}")
        return text
    if old not in text:
        raise SystemExit(f"pattern not found: {label}")
    return text.replace(old, new, 1)


def _replace_one_of(text: str, pairs: list[tuple[str, str]], label: str) -> str:
    newest = pairs[-1][1]
    if newest in text:
        print(f"already patched: {label}")
        return text
    for old, new in pairs:
        if old in text:
            print(f"patched {label}")
            return text.replace(old, new, 1)
    raise SystemExit(f"pattern not found: {label}")


def patch_drive_oauth(root: Path) -> int:
    auth = root / "auth.py"
    if not auth.is_file():
        print(f"error: {auth} missing", file=sys.stderr)
        return 1
    text = auth.read_text(encoding="utf-8")
    text = _replace_one_of(
        text,
        [(SERVICE_OLD, SERVICE_NEW), (SERVICE_SA_FALLBACK, SERVICE_NEW)],
        "auth _drive_service oauth",
    )
    text = _replace_one_of(
        text,
        [(HEALTH_OLD, HEALTH_NEW), (HEALTH_OAUTH, HEALTH_NEW)],
        "auth _drive_health_summary oauth",
    )
    if EMPTY_FOLDERS_NEW in text:
        print("already patched: auth skip empty Drive folders")
    elif EMPTY_FOLDERS_OLD in text:
        text = text.replace(EMPTY_FOLDERS_OLD, EMPTY_FOLDERS_NEW, 1)
        print("patched auth skip empty Drive folders")
    elif SNAPSHOT_NEW in text:
        print("already patched: auth patient program archive")
    elif SNAPSHOT_OLD in text:
        text = text.replace(SNAPSHOT_OLD, SNAPSHOT_NEW, 1)
        print("patched auth patient program archive")
    else:
        print("WARN: auth patient snapshot pattern missing")
    if BACKUP_FILE_NEW in text:
        print("already patched: auth original-only backup-file")
    elif BACKUP_FILE_OLD in text:
        text = text.replace(BACKUP_FILE_OLD, BACKUP_FILE_NEW, 1)
        print("patched auth original-only backup-file")
    else:
        print("WARN: auth backup-file pattern missing")
    if BACKUP_UPLOAD_NEW in text:
        print("already patched: auth original-only backup-file-upload")
    elif BACKUP_UPLOAD_OLD in text:
        text = text.replace(BACKUP_UPLOAD_OLD, BACKUP_UPLOAD_NEW, 1)
        print("patched auth original-only backup-file-upload")
    else:
        print("WARN: auth backup-file-upload pattern missing")
    if RESTORE_FILE_NEW in text:
        print("already patched: auth restore original fallback")
    elif RESTORE_FILE_OLD in text:
        text = text.replace(RESTORE_FILE_OLD, RESTORE_FILE_NEW, 1)
        print("patched auth restore original fallback")
    else:
        print("WARN: auth restore-file pattern missing")
    if "original_videos_only" in text:
        text = text.replace("original_videos_only", "validation_videos_only")
        print("patched auth skip reason to validation videos")
    if REGISTER_MARK not in text:
        text = text.rstrip() + REGISTER_SNIPPET
        print("patched auth oauth routes")
    else:
        print("already patched: auth oauth routes")
    auth.write_text(text, encoding="utf-8")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_drive_oauth.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_drive_oauth(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
