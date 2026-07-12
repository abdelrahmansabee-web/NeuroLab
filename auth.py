import os
import sqlite3
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from jose import JWTError, jwt
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
JWT_SECRET = os.environ.get("JWT_SECRET") or "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
]


def _data_dir():
    env = os.environ.get("NEUROLAB_DATA_DIR")
    candidates = [Path(env)] if env else []
    candidates += [Path("/data/neurolab"), Path(__file__).parent / "data"]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    fallback = Path(__file__).parent / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


DATA_DIR = _data_dir()
USERS_DB = DATA_DIR / "users.db"
PATIENTS_DIR = DATA_DIR / "patients"
PATIENTS_DIR.mkdir(parents=True, exist_ok=True)


def _init_db():
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                picture TEXT,
                google_refresh_token TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


_init_db()


def _flow(request: Request):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    redirect_uri = str(request.url_for("google_callback"))
    redirect_uri = redirect_uri.replace("http://", "https://")
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )


def _create_token(user_id: int) -> str:
    exp = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": exp}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _user_id_from_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None


def _get_user(user_id: int):
    with sqlite3.connect(USERS_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def _get_user_by_email(email: str):
    with sqlite3.connect(USERS_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def _upsert_user(email: str, name: str, picture: str, refresh_token: Optional[str]):
    now = datetime.utcnow().isoformat()
    existing = _get_user_by_email(email)
    with sqlite3.connect(USERS_DB) as conn:
        if existing:
            if refresh_token:
                conn.execute(
                    "UPDATE users SET name = ?, picture = ?, google_refresh_token = ?, updated_at = ? WHERE id = ?",
                    (name, picture, refresh_token, now, existing["id"]),
                )
            else:
                conn.execute(
                    "UPDATE users SET name = ?, picture = ?, updated_at = ? WHERE id = ?",
                    (name, picture, now, existing["id"]),
                )
            conn.commit()
            return existing["id"]
        conn.execute(
            "INSERT INTO users (email, name, picture, google_refresh_token, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, picture, refresh_token, now, now),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _drive_service(user: dict):
    refresh_token = user.get("google_refresh_token")
    if not refresh_token or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(GoogleRequest())
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_current_user(request: Request):
    token = request.cookies.get("neurolab_token")
    if not token:
        auth = request.headers.get("authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = _user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = _get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
async def google_login(request: Request):
    authorization_url, state = _flow(request).authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    response = RedirectResponse(authorization_url)
    response.set_cookie("neurolab_oauth_state", state, httponly=True, max_age=600)
    return response


@router.get("/google/callback", name="google_callback")
async def google_callback(request: Request, code: str, state: str = None):
    saved_state = request.cookies.get("neurolab_oauth_state")
    if state and saved_state and state != saved_state:
        raise HTTPException(status_code=400, detail="Invalid state")
    flow = _flow(request)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    try:
        idinfo = google_id_token.verify_oauth2_token(
            credentials.id_token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        email = idinfo.get("email")
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to verify Google token: {exc}")
    if not email:
        raise HTTPException(status_code=400, detail="Email not provided")
    refresh_token = credentials.refresh_token
    user_id = _upsert_user(email, name, picture, refresh_token)
    token = _create_token(user_id)
    response = RedirectResponse("/")
    response.set_cookie("neurolab_oauth_state", "", max_age=0)
    response.set_cookie("neurolab_token", token, httponly=True, max_age=60 * 60 * 24 * 7)
    return response


@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"],
    }


@router.post("/logout")
async def auth_logout():
    response = JSONResponse({"ok": True})
    response.set_cookie("neurolab_token", "", max_age=0)
    return response


@router.post("/backup")
async def backup_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patients = body.get("patients", [])
    service = _drive_service(user)
    if not service:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    folder_name = "NeuroLab_Backups"
    q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    res = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
    if res.get("files"):
        folder_id = res["files"][0]["id"]
    else:
        folder = service.files().create(
            body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        folder_id = folder["id"]

    file_name = f"neurolab_backup_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    media = MediaIoBaseUpload(
        BytesIO(json.dumps(patients, ensure_ascii=False).encode("utf-8")),
        mimetype="application/json",
        resumable=True,
    )
    service.files().create(
        body={"name": file_name, "parents": [folder_id]},
        media_body=media,
        fields="id",
    ).execute()
    return {"ok": True, "fileName": file_name}


@router.post("/restore")
async def restore_drive(user: dict = Depends(get_current_user)):
    service = _drive_service(user)
    if not service:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    folder_name = "NeuroLab_Backups"
    q = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    res = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
    folders = res.get("files", [])
    if not folders:
        return {"patients": []}
    folder_id = folders[0]["id"]
    q = f"'{folder_id}' in parents and mimeType='application/json' and trashed=false"
    res = service.files().list(
        q=q, spaces="drive", orderBy="createdTime desc", fields="files(id, name, createdTime)"
    ).execute()
    files = res.get("files", [])
    if not files:
        return {"patients": []}
    content = service.files().get_media(fileId=files[0]["id"]).execute()
    return {"patients": json.loads(content.decode("utf-8"))}
