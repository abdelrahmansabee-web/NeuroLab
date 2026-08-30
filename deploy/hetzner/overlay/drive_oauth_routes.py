"""OAuth connect routes for Google Drive."""
from __future__ import annotations

import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse


def register_drive_oauth_routes(router: APIRouter, get_current_user, require_admin=None):
    @router.get("/drive/oauth-status")
    async def drive_oauth_status():
        from drive_oauth import oauth_status

        return oauth_status()

    @router.get("/drive/folder-status")
    async def drive_folder_status():
        from drive_persist import list_clinic_folder

        return list_clinic_folder()

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
            import threading

            threading.Thread(target=backfill_data_dir, args=(_data_dir(),), daemon=True).start()
        except Exception as exc:
            print("Drive backfill after OAuth:", exc, flush=True)
        _ = info
        resp = RedirectResponse("/connect-drive?ok=1", status_code=302)
        resp.delete_cookie("neurolab_oauth_state", path="/")
        return resp
