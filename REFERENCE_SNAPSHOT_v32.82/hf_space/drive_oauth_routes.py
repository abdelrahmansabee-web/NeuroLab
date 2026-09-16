"""OAuth connect routes for Google Drive."""
from __future__ import annotations

import secrets
import threading
import time
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

_reconcile_lock = threading.Lock()
_reconcile_job = {
    "jobId": None,
    "running": False,
    "started": False,
    "result": None,
    "error": None,
    "startedAt": None,
}


def _human_reconcile_error(result: dict | None, exc_text: str = "") -> str:
    if exc_text:
        return exc_text[:400]
    if not isinstance(result, dict):
        return "Drive rebuild failed"
    if result.get("error"):
        return str(result.get("error"))[:400]
    reason = str(result.get("reason") or "")
    mapping = {
        "drive_unset": (
            "Google Drive is not connected. Open Connect Drive and sign in with the clinic Gmail, then retry Rebuild."
        ),
        "drive_init_failed": (
            "Drive OAuth token invalid or expired. Reconnect Drive (Connect Drive), then retry Rebuild."
        ),
    }
    if reason in mapping:
        return mapping[reason]
    errors = result.get("errors") or []
    if errors:
        first = errors[0]
        if isinstance(first, dict):
            return str(first.get("error") or first)[:400]
        return str(first)[:400]
    return "Drive rebuild failed"


def register_drive_oauth_routes(router: APIRouter, get_current_user, require_admin=None):
    @router.get("/drive/oauth-status")
    async def drive_oauth_status():
        from drive_oauth import oauth_status

        return oauth_status()

    @router.get("/drive/folder-status")
    async def drive_folder_status():
        from drive_persist import list_clinic_folder

        return list_clinic_folder()

    @router.get("/drive/reconcile-status")
    async def drive_reconcile_status(user: dict = Depends(get_current_user)):
        _ = user
        with _reconcile_lock:
            return {
                "jobId": _reconcile_job.get("jobId"),
                "running": bool(_reconcile_job.get("running")),
                "started": bool(_reconcile_job.get("started")),
                "error": _reconcile_job.get("error"),
                "result": _reconcile_job.get("result"),
                "startedAt": _reconcile_job.get("startedAt"),
            }

    @router.post("/drive/reconcile")
    async def drive_reconcile(request: Request, user: dict = Depends(get_current_user)):
        """Rebuild Drive folders 1:1 from the program patient list (merge aliases safely)."""
        body = {}
        try:
            body = await request.json()
        except Exception:
            body = {}
        patients = body.get("patients") if isinstance(body, dict) else None
        if not isinstance(patients, list):
            patients = []
        if not patients:
            try:
                from drive_oauth import _data_dir
                from patient_drive_archive import load_program_patients

                patients = load_program_patients(_data_dir())
            except Exception as exc:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "No patients in the request and none on the server. "
                        f"Open Database on the iPad so the list is loaded, then retry. ({exc})"
                    ),
                )

        # Same OAuth token Connect Drive just saved — verify it can call Drive before starting.
        try:
            from drive_oauth import oauth_client_configured, oauth_probe, oauth_ready

            if oauth_client_configured():
                if not oauth_ready():
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Drive is not connected. Tap Connect Drive, sign in with the clinic Gmail, then retry Rebuild."
                        ),
                    )
                probe = oauth_probe()
                if not probe.get("ok"):
                    raise HTTPException(
                        status_code=400,
                        detail=probe.get("error")
                        or "Drive OAuth failed. Reconnect Drive, then retry Rebuild.",
                    )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Drive OAuth check failed: {str(exc)[:220]}",
            )

        snapshot = list(patients)
        job_id = uuid.uuid4().hex[:12]

        with _reconcile_lock:
            if _reconcile_job.get("running"):
                return {
                    "ok": True,
                    "started": False,
                    "running": True,
                    "jobId": _reconcile_job.get("jobId"),
                    "message": "Drive rebuild already running",
                }
            _reconcile_job["jobId"] = job_id
            _reconcile_job["running"] = True
            _reconcile_job["started"] = True
            _reconcile_job["error"] = None
            _reconcile_job["result"] = None
            _reconcile_job["startedAt"] = int(time.time())

        def _run() -> None:
            try:
                from drive_persist import reconcile_drive_to_program

                result = reconcile_drive_to_program(snapshot)
                if not isinstance(result, dict):
                    result = {"ok": False, "error": "invalid reconcile result"}
                if result.get("ok") is False:
                    result["error"] = _human_reconcile_error(result)
                with _reconcile_lock:
                    if _reconcile_job.get("jobId") == job_id:
                        _reconcile_job["result"] = result
                        if result.get("ok") is False:
                            _reconcile_job["error"] = result.get("error")
            except Exception as exc:
                err = str(exc)[:400]
                with _reconcile_lock:
                    if _reconcile_job.get("jobId") == job_id:
                        _reconcile_job["error"] = err
                        _reconcile_job["result"] = {"ok": False, "error": err}
            finally:
                with _reconcile_lock:
                    if _reconcile_job.get("jobId") == job_id:
                        _reconcile_job["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        return {
            "ok": True,
            "started": True,
            "running": True,
            "jobId": job_id,
            "patientCount": len([p for p in snapshot if isinstance(p, dict)]),
            "message": "Drive rebuild started — poll /auth/drive/reconcile-status",
        }

    @router.post("/drive/connect-cookie")
    async def drive_connect_cookie(request: Request, user: dict = Depends(get_current_user)):
        token = request.cookies.get("neurolab_token")
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        resp = JSONResponse({"ok": True, "email": user.get("email")})
        resp.set_cookie(
            "neurolab_token",
            token,
            max_age=60 * 60 * 12,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
        return resp

    @router.get("/drive/connect")
    async def drive_connect(request: Request, user: dict = Depends(get_current_user)):
        from drive_oauth import authorization_url, oauth_client_configured

        if not oauth_client_configured():
            raise HTTPException(status_code=400, detail="OAuth client is not configured")
        state = secrets.token_urlsafe(24)
        url = authorization_url(state)
        resp = RedirectResponse(url, status_code=302)
        resp.set_cookie(
            "neurolab_oauth_state",
            state,
            max_age=600,
            httponly=True,
            samesite="lax",
            secure=True,
            path="/",
        )
        token = request.cookies.get("neurolab_token")
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        if token:
            resp.set_cookie(
                "neurolab_token",
                token,
                max_age=60 * 60 * 12,
                httponly=True,
                samesite="lax",
                secure=True,
                path="/",
            )
        return resp

    @router.get("/drive/callback")
    async def drive_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if error:
            return RedirectResponse("/connect-drive?error=" + quote(error), status_code=302)
        expected = request.cookies.get("neurolab_oauth_state") or ""
        if not code or not state or not expected or state != expected:
            return RedirectResponse("/connect-drive?error=" + quote("invalid_state"), status_code=302)
        try:
            from drive_oauth import exchange_code

            info = exchange_code(code)
            try:
                from drive_persist import write_drive_connected_marker

                write_drive_connected_marker(
                    email=str(info.get("email") or ""),
                    folder_name=str(info.get("folderName") or ""),
                )
            except Exception as marker_exc:
                print("Drive connected marker:", marker_exc, flush=True)
            try:
                import auth as auth_mod

                auth_mod._drive_service_instance = None
            except Exception:
                pass
        except Exception as exc:
            return RedirectResponse("/connect-drive?error=" + quote(str(exc)[:180]), status_code=302)
        try:
            from backfill_drive import backfill_data_dir
            from drive_oauth import _data_dir

            threading.Thread(target=backfill_data_dir, args=(_data_dir(),), daemon=True).start()
        except Exception as exc:
            print("Drive backfill after OAuth:", exc, flush=True)
        _ = info
        resp = RedirectResponse("/connect-drive?ok=1", status_code=302)
        resp.delete_cookie("neurolab_oauth_state", path="/")
        return resp
