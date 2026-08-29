#!/usr/bin/env python3
"""Wire local disk fallbacks into Hugging Face auth.py Drive endpoints."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPLACEMENTS = [
    (
        '''@router.post("/backup")
async def backup_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patients = body.get("patients", [])
    if not isinstance(patients, list):
        patients = _normalize_patients_payload(body)
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
''',
        '''@router.post("/backup")
async def backup_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patients = body.get("patients", [])
    if not isinstance(patients, list):
        patients = _normalize_patients_payload(body)
    service = _drive_service()
    if not service:
        from local_drive_fallback import save_patients_backup
        file_name = _drive_patients_filename(user["id"])
        save_patients_backup(DATA_DIR, user["id"], file_name, patients)
        return {
            "ok": True,
            "fileName": file_name,
            "local": True,
            "disabledDrive": True,
        }
''',
    ),
    (
        '''@router.get("/restore")
async def restore_drive(user: dict = Depends(get_current_user)):
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
''',
        '''@router.get("/restore")
async def restore_drive(user: dict = Depends(get_current_user)):
    service = _drive_service()
    if not service:
        from local_drive_fallback import load_patients_backup
        file_name = _drive_patients_filename(user["id"])
        patients = load_patients_backup(DATA_DIR, user["id"], file_name)
        return {"patients": patients, "fileName": file_name if patients else None, "local": True}
''',
    ),
    (
        '''    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    try:
        content = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
''',
        '''    service = _drive_service()
    try:
        content = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    if not service:
        from local_drive_fallback import write_artifact
        patient_key = (body.get("patientKey") or "").strip() or "anon"
        subfolder = (body.get("subfolder") or "data").strip().lower()
        scope = (body.get("scope") or "team").strip().lower()
        path = write_artifact(
            DATA_DIR, user["id"], patient_key, name, content, subfolder, scope, _drive_sanitize_name
        )
        return {
            "ok": True,
            "fileName": path.name,
            "local": True,
            "patientKey": patient_key,
            "subfolder": subfolder,
        }
''',
    ),
    (
        '''    """Download a patient artifact from Google Drive (team shared or per-user backup)."""
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
''',
        '''    """Download a patient artifact from Google Drive (team shared or per-user backup)."""
    service = _drive_service()
    if not service:
        from fastapi.responses import FileResponse
        from local_drive_fallback import find_artifact, guess_mime
        safe_key = _drive_sanitize_name(patientKey)[:120]
        if not safe_key:
            raise HTTPException(status_code=400, detail="patientKey required")
        sub = (subfolder or "videos").strip().lower()
        scope_norm = (scope or "auto").strip().lower()
        scopes = ("team", "user") if scope_norm == "auto" else (scope_norm,)
        path = find_artifact(
            DATA_DIR, user["id"], safe_key, name, sub, scopes, _drive_sanitize_name
        )
        if path is None:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path, media_type=guess_mime(path), filename=path.name)
''',
    ),
    (
        '''    """Multipart Drive upload for large validation videos (>32MB base64 limit)."""
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
''',
        '''    """Multipart Drive upload for large validation videos (>32MB base64 limit)."""
    service = _drive_service()
    if not service:
        from local_drive_fallback import write_artifact
        safe_key = _drive_sanitize_name(patientKey)[:120]
        if not safe_key:
            raise HTTPException(status_code=400, detail="patientKey required")
        drive_name = _drive_sanitize_name(name)
        if not drive_name:
            raise HTTPException(status_code=400, detail="name required")
        sub = (subfolder or "videos").strip().lower()
        scope_norm = (scope or "team").strip().lower()
        try:
            content = await file.read()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read upload: {exc}")
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")
        path = write_artifact(
            DATA_DIR, user["id"], safe_key, drive_name, content, sub, scope_norm, _drive_sanitize_name
        )
        return {
            "ok": True,
            "fileName": path.name,
            "local": True,
            "patientKey": safe_key,
            "subfolder": sub,
            "bytes": len(content),
        }
''',
    ),
]


def patch_index_html(root: Path) -> None:
    idx = root / "frontend" / "build" / "index.html"
    if not idx.is_file():
        print("WARN: frontend/build/index.html missing")
        return
    text = idx.read_text(encoding="utf-8", errors="replace")
    old = (
        "Still blank? Wait 1–2 min for Space wake-up, or open the "
        '<a href="https://abdelrahmansabee-neurolab.hf.space/" style="color:#7dd3fc">direct app link</a>.'
    )
    new = "Still loading? Refresh the page — this clinic server stays on."
    if old in text:
        idx.write_text(text.replace(old, new), encoding="utf-8")
        print("patched Space wake-up copy in index.html")
    elif "this clinic server stays on" in text:
        print("index.html already has clinic boot copy")
    else:
        print("WARN: Space wake-up copy not found in index.html")

    media = root / "frontend" / "build" / "static" / "media"
    media.mkdir(parents=True, exist_ok=True)
    bg = root / "frontend" / "build" / "bg.jpg"
    dest = media / "bg.a2cb4668082122acfd8d.jpg"
    if bg.is_file() and not dest.is_file():
        shutil.copy2(bg, dest)
        print(f"copied background image to {dest.name}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_auth_drive.py /opt/neurolab", file=sys.stderr)
        return 2
    root = Path(sys.argv[1]).resolve()
    overlay = Path(__file__).resolve().parent
    auth = root / "auth.py"
    if not auth.is_file():
        print(f"error: {auth} missing", file=sys.stderr)
        return 1

    src = overlay / "local_drive_fallback.py"
    shutil.copy2(src, root / "local_drive_fallback.py")
    print("copied local_drive_fallback.py")

    text = auth.read_text(encoding="utf-8")
    if "from local_drive_fallback import" in text and "disabledDrive" in text:
        print("auth.py already has local Drive fallback")
        patch_index_html(root)
        return 0

    for old, new in REPLACEMENTS:
        if old not in text:
            print("error: Drive handler pattern not found", file=sys.stderr)
            print(old[:120], file=sys.stderr)
            return 1
        text = text.replace(old, new, 1)
    auth.write_text(text, encoding="utf-8")
    print("patched auth.py Drive endpoints to use local disk when Drive is unset")
    patch_index_html(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
