import os
import sqlite3
import json
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import service_account as google_service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

JWT_SECRET = os.environ.get("JWT_SECRET") or "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


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
        try:
            cur = conn.execute("PRAGMA table_info(users)")
            columns = {row[1] for row in cur.fetchall()}
            if columns and "password_hash" not in columns:
                conn.execute("DROP TABLE users")
        except Exception:
            pass
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                password_hash TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


_init_db()


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(password: str, hash_value: str) -> bool:
    return pwd_context.verify(password, hash_value)


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


def _create_user(email: str, password: str, name: str) -> int:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (email, name, _hash_password(password), now, now),
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Email already registered")


def _update_password(email: str, password: str) -> bool:
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (_hash_password(password), now, row["id"]),
        )
        conn.commit()
        return True


def _drive_service():
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_DRIVE_FOLDER_ID:
        return None
    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = google_service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        print("Drive service init failed:", exc, flush=True)
        return None


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


@router.post("/register")
async def register(body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    user_id = _create_user(email, password, name)
    token = _create_token(user_id)
    return {"ok": True, "token": token, "user": {"id": user_id, "email": email, "name": name}}


@router.post("/login")
async def login(body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    user = _get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = _create_token(user["id"])
    return {"ok": True, "token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@router.post("/reset-password")
async def reset_password(body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    if not email or not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Email and password (min 6 chars) required")
    if not _update_password(email, password):
        raise HTTPException(status_code=404, detail="Email not found")
    return {"ok": True, "message": "Password updated. Sign in with your new password."}


@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


@router.post("/logout")
async def auth_logout():
    return {"ok": True}


@router.post("/backup")
async def backup_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patients = body.get("patients", [])
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    file_name = f"neurolab_backup_{datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    media = MediaIoBaseUpload(
        BytesIO(json.dumps(patients, ensure_ascii=False).encode("utf-8")),
        mimetype="application/json",
        resumable=True,
    )
    service.files().create(
        body={"name": file_name, "parents": [GOOGLE_DRIVE_FOLDER_ID]},
        media_body=media,
        fields="id",
    ).execute()
    return {"ok": True, "fileName": file_name}


@router.get("/restore")
async def restore_drive(user: dict = Depends(get_current_user)):
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and mimeType='application/json' and trashed=false"
    res = service.files().list(
        q=q, spaces="drive", orderBy="createdTime desc", fields="files(id, name, createdTime)"
    ).execute()
    files = res.get("files", [])
    if not files:
        return {"patients": []}
    content = service.files().get_media(fileId=files[0]["id"]).execute()
    return {"patients": json.loads(content.decode("utf-8"))}
