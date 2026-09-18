"""Insert GET /auth/list-patient-files on a Hugging Face Space auth.py."""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "from drive_oauth_routes import register_drive_oauth_routes"

ROUTE = '''
def _drive_list_children(service, parent_id: str):
    items = []
    if not parent_id:
        return items
    page = None
    scanned = 0
    while scanned < 800:
        res = service.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            spaces="drive",
            pageSize=100,
            pageToken=page,
            fields="nextPageToken, files(id, name, mimeType, size)",
            **_drive_list_flags(),
        ).execute()
        batch = res.get("files") or []
        scanned += len(batch)
        items.extend(batch)
        page = res.get("nextPageToken")
        if not page:
            break
    return items


@router.get("/list-patient-files")
async def list_patient_files_drive(
    patientKey: str,
    scope: str = "auto",
    user: dict = Depends(get_current_user),
):
    """Names of files in the patient Drive folder (videos, PDF, overlay JSON)."""
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    safe_key = _drive_sanitize_name(patientKey)[:120]
    if not safe_key:
        raise HTTPException(status_code=400, detail="patientKey required")
    scope_norm = (scope or "auto").strip().lower()
    scopes = ("team", "user") if scope_norm == "auto" else (scope_norm,)
    folder_mime = "application/vnd.google-apps.folder"
    subfolders = {"videos", "reports", "data"}
    seen = set()
    files = []
    for sc in scopes:
        if sc not in ("team", "user"):
            continue
        try:
            parent = _drive_parent_for_patient_artifact(service, user["id"], safe_key, "videos", sc)
        except Exception as exc:
            print(f"Drive list parent skipped ({safe_key}): {exc}", flush=True)
            continue
        folders = [parent]
        try:
            children = _drive_list_children(service, parent)
        except Exception as exc:
            print(f"Drive list children skipped ({safe_key}): {exc}", flush=True)
            continue
        for child in children:
            mime = child.get("mimeType") or ""
            name = (child.get("name") or "").strip()
            cid = child.get("id") or ""
            if mime == folder_mime and name.lower() in subfolders and cid:
                folders.append(cid)
                continue
            if not name or cid in seen:
                continue
            seen.add(cid)
            files.append(
                {
                    "name": name,
                    "size": int(child.get("size") or 0),
                    "mimeType": mime,
                }
            )
        for fid in folders[1:]:
            try:
                extra = _drive_list_children(service, fid)
            except Exception:
                continue
            for child in extra:
                mime = child.get("mimeType") or ""
                name = (child.get("name") or "").strip()
                cid = child.get("id") or ""
                if not name or mime == folder_mime or cid in seen:
                    continue
                seen.add(cid)
                files.append(
                    {
                        "name": name,
                        "size": int(child.get("size") or 0),
                        "mimeType": mime,
                    }
                )
        if files:
            break
    return {"ok": True, "patientKey": safe_key, "files": files}


'''


def patch_list_patient_files(root: Path) -> int:
    auth = root / "auth.py"
    if not auth.is_file():
        print(f"error: {auth} missing", file=sys.stderr)
        return 1
    text = auth.read_text(encoding="utf-8")
    if "@router.get(\"/list-patient-files\")" in text:
        print("already patched: list-patient-files")
        return 0
    if MARKER not in text:
        print("error: auth.py oauth marker missing", file=sys.stderr)
        return 1
    auth.write_text(text.replace(MARKER, ROUTE + MARKER, 1), encoding="utf-8")
    print("patched auth list-patient-files")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch_list_patient_files.py /path/to/hf-space", file=sys.stderr)
        return 2
    return patch_list_patient_files(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
