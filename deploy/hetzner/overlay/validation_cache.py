# Persist iPad IndexedDB validation artifacts to server disk (not Drive, not a file download).
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_part(value: str, fallback: str = "anon") -> str:
    cleaned = _SAFE.sub("_", (value or "").strip())[:120]
    return cleaned or fallback


def cache_root(data_dir: Path) -> Path:
    path = Path(data_dir) / "validation_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def register_validation_cache(app, data_dir: Path, html_path: Path) -> None:
    """Attach /sync-ipad and /api/validation-cache* to an existing FastAPI app."""

    @app.get("/sync-ipad", response_class=HTMLResponse, include_in_schema=False)
    async def sync_ipad_page():
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="sync page missing")
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    @app.get("/api/validation-cache")
    async def list_validation_cache():
        root = cache_root(data_dir)
        items: List[Dict[str, Any]] = []
        for meta in sorted(root.glob("*/*/meta.json")):
            try:
                items.append(json.loads(meta.read_text(encoding="utf-8")))
            except Exception:
                continue
        return {"count": len(items), "items": items}

    @app.post("/api/validation-cache")
    async def upload_validation_cache(
        patientKey: str = Form(...),
        phase: str = Form(...),
        csvFilename: Optional[str] = Form(None),
        videoFilename: Optional[str] = Form(None),
        unifiedVideoFilename: Optional[str] = Form(None),
        overlay: Optional[UploadFile] = File(None),
        originalVideo: Optional[UploadFile] = File(None),
        unifiedVideo: Optional[UploadFile] = File(None),
        kinematics: Optional[UploadFile] = File(None),
    ):
        patient = _safe_part(patientKey)
        ph = _safe_part(phase, "phase")
        dest = cache_root(data_dir) / patient / ph
        dest.mkdir(parents=True, exist_ok=True)

        saved: Dict[str, Any] = {
            "patientKey": patientKey,
            "phase": phase,
            "csvFilename": csvFilename,
            "videoFilename": videoFilename,
            "unifiedVideoFilename": unifiedVideoFilename,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }

        async def _store(upload: Optional[UploadFile], filename: str) -> Optional[int]:
            if upload is None:
                return None
            data = await upload.read()
            if not data:
                return None
            (dest / filename).write_bytes(data)
            saved["files"][filename] = len(data)
            return len(data)

        await _store(overlay, "overlay.json")
        await _store(originalVideo, "original.mp4")
        await _store(unifiedVideo, "unified.mp4")
        await _store(kinematics, "kinematics.json")
        (dest / "meta.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")

        if not saved["files"]:
            raise HTTPException(status_code=400, detail="No artifact bytes in this IndexedDB record")
        try:
            from persist_validation import persist_phase_artifacts

            orig = dest / "original.mp4"
            ov = dest / "overlay.json"
            uni = dest / "unified.mp4"
            persisted = persist_phase_artifacts(
                Path(data_dir),
                patient,
                ph,
                original_video=orig if orig.is_file() and orig.stat().st_size > 0 else None,
                overlay_json=ov if ov.is_file() and ov.stat().st_size > 0 else None,
                unified_video=uni if uni.is_file() and uni.stat().st_size > 0 else None,
            )
            saved["drive"] = persisted.get("drive")
        except Exception as exc:
            print(f"validation-cache Drive persist: {exc}", flush=True)
            saved["drive_error"] = str(exc)
        return JSONResponse({"ok": True, **saved})

    _ALLOWED_FILES = {
        "overlay.json",
        "original.mp4",
        "unified.mp4",
        "kinematics.json",
        "meta.json",
    }

    @app.get("/api/validation-cache/{patientKey}/{phase}/{filename}")
    async def download_validation_cache(patientKey: str, phase: str, filename: str):
        if filename not in _ALLOWED_FILES:
            raise HTTPException(status_code=404, detail="unknown file")
        path = cache_root(data_dir) / _safe_part(patientKey) / _safe_part(phase, "phase") / filename
        if not path.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        from fastapi.responses import FileResponse
        return FileResponse(path)

    @app.get("/connect-drive", response_class=HTMLResponse, include_in_schema=False)
    async def connect_drive_page():
        path = Path(__file__).resolve().parent / "connect_drive.html"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="connect-drive missing")
        return HTMLResponse(path.read_text(encoding="utf-8"))

    @app.post("/api/drive-backfill")
    async def drive_backfill():
        from backfill_drive import backfill_data_dir

        return backfill_data_dir(Path(data_dir))

    @app.post("/api/ipad-localstorage")
    async def upload_ipad_localstorage(payload: Optional[UploadFile] = File(None)):
        dest_dir = Path(data_dir) / "ipad_localstorage"
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = dest_dir / f"localstorage_{stamp}.json"
        raw = await payload.read() if payload is not None else b"{}"
        dest.write_bytes(raw or b"{}")
        latest = dest_dir / "latest.json"
        latest.write_bytes(raw or b"{}")
        return {"ok": True, "saved": dest.name, "bytes": len(raw or b"")}
