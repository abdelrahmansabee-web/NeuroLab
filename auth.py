import os
import json
import base64
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

import encrypted_sqlite as sqlite3
import pyotp
import qrcode
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import service_account as google_service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from security import password_policy, RateLimiter, get_client_ip, log_audit, encrypt_json_to_str, decrypt_json_from_str

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required. Set it in Hugging Face Space Secrets.")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY") or JWT_SECRET
if not MFA_ENCRYPTION_KEY:
    raise RuntimeError("MFA_ENCRYPTION_KEY or JWT_SECRET is required for MFA encryption.")

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
legacy_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

login_rate_limiter = RateLimiter(limit=5, window=60 * 15)
register_rate_limiter = RateLimiter(limit=5, window=60 * 60)
password_reset_rate_limiter = RateLimiter(limit=3, window=60 * 15)
mfa_rate_limiter = RateLimiter(limit=10, window=60)

_drive_service_instance = None


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
AUDIT_DB = DATA_DIR / "audit.db"
PATIENTS_DIR = DATA_DIR / "patients"
PATIENTS_DIR.mkdir(parents=True, exist_ok=True)
print(f"STARTUP: DATA_DIR={DATA_DIR}", flush=True)
print(f"STARTUP: USERS_DB={USERS_DB}", flush=True)
print(f"STARTUP: PATIENTS_DIR={PATIENTS_DIR}", flush=True)


def _ensure_encrypted_dbs():
    """Encrypt plain SQLite databases in place on first startup."""
    try:
        sqlite3.ensure_encrypted(USERS_DB)
    except Exception as exc:
        print(f"STARTUP: users.db encryption check failed: {exc}", flush=True)
    try:
        sqlite3.ensure_encrypted(AUDIT_DB)
    except Exception as exc:
        print(f"STARTUP: audit.db encryption check failed: {exc}", flush=True)


# Call encryption check at import time so it runs before any DB access.
_ensure_encrypted_dbs()


def _init_db():
    with sqlite3.connect(USERS_DB) as conn:
        try:
            cur = conn.execute("PRAGMA table_info(users)")
            columns = {row[1] for row in cur.fetchall()}
            if columns and "password_hash" not in columns:
                conn.execute("DROP TABLE users")
                columns = set()
            if columns:
                if "is_admin" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
                if "is_approved" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0")
                if "mfa_secret" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN mfa_secret TEXT")
                if "mfa_enabled" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0")
                conn.commit()
        except Exception as exc:
            print("Migration warning:", exc, flush=True)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                is_approved INTEGER NOT NULL DEFAULT 0,
                mfa_secret TEXT,
                mfa_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(password: str, hash_value: str) -> bool:
    if not hash_value:
        return False
    try:
        if pwd_context.verify(password, hash_value):
            return True
    except Exception:
        pass
    # Fallback for any accounts created earlier with bcrypt.
    try:
        if legacy_context.verify(password, hash_value):
            return True
    except Exception:
        pass
    return False


def _encrypt_mfa_secret(secret: str) -> str:
    return encrypt_json_to_str(secret, MFA_ENCRYPTION_KEY)


def _decrypt_mfa_secret(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return decrypt_json_from_str(ciphertext, MFA_ENCRYPTION_KEY)
    except Exception:
        return None


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


def _is_first_user() -> bool:
    try:
        with sqlite3.connect(USERS_DB) as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return count == 0
    except Exception:
        return True


def _create_user(email: str, password: str, name: str) -> int:
    now = datetime.utcnow().isoformat()
    first = _is_first_user()
    is_admin = 1 if first else 0
    is_approved = 1 if first else 0
    with sqlite3.connect(USERS_DB) as conn:
        try:
            conn.execute(
                "INSERT INTO users (email, name, password_hash, is_admin, is_approved, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (email, name, _hash_password(password), is_admin, is_approved, now, now),
            )
            conn.commit()
            user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Email already registered")
    try:
        _backup_users_db()
    except Exception:
        pass
    return user_id


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
    try:
        _backup_users_db()
    except Exception:
        pass
    return True


def _drive_service():
    global _drive_service_instance
    if _drive_service_instance is not None:
        return _drive_service_instance
    if not GOOGLE_SERVICE_ACCOUNT_JSON or not GOOGLE_DRIVE_FOLDER_ID:
        return None
    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = google_service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        _drive_service_instance = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _drive_service_instance
    except Exception as exc:
        print("Drive service init failed:", exc, flush=True)
        return None


def _backup_users_db():
    service = _drive_service()
    if not service:
        return
    try:
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and name='users.db' and trashed=false"
        res = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
        files = res.get("files", [])
        media = MediaIoBaseUpload(BytesIO(USERS_DB.read_bytes()), mimetype="application/x-sqlite3", resumable=True)
        if files:
            service.files().update(fileId=files[0]["id"], media_body=media).execute()
        else:
            service.files().create(
                body={"name": "users.db", "parents": [GOOGLE_DRIVE_FOLDER_ID]},
                media_body=media,
                fields="id",
            ).execute()
        print("Users DB backed up to Drive", flush=True)
    except Exception as exc:
        print("Users DB backup failed:", exc, flush=True)


def _restore_users_db():
    service = _drive_service()
    if not service:
        return
    try:
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and name='users.db' and trashed=false"
        res = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
        files = res.get("files", [])
        if not files:
            return
        # Keep local DB if it already has users to avoid overwriting newer data.
        if USERS_DB.exists():
            try:
                with sqlite3.connect(USERS_DB) as conn:
                    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    if count > 0:
                        print("Local users DB has records; skip Drive restore", flush=True)
                        return
            except Exception:
                pass
        content = service.files().get_media(fileId=files[0]["id"]).execute()
        USERS_DB.parent.mkdir(parents=True, exist_ok=True)
        USERS_DB.write_bytes(content)
        print("Users DB restored from Drive", flush=True)
    except Exception as exc:
        print("Users DB restore failed:", exc, flush=True)


def _ensure_admin():
    try:
        with sqlite3.connect(USERS_DB) as conn:
            admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
            if admin_count == 0:
                first = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
                if first:
                    conn.execute("UPDATE users SET is_admin = 1, is_approved = 1 WHERE id = ?", (first[0],))
                    conn.commit()
                    print("Promoted first user to admin", flush=True)
    except Exception as exc:
        print("Ensure admin failed:", exc, flush=True)


def _seed_admin():
    admin_email = os.environ.get("NEUROLAB_ADMIN_EMAIL")
    admin_password = os.environ.get("NEUROLAB_ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        print("STARTUP: no NEUROLAB_ADMIN_EMAIL/PASSWORD set; skipping seed admin", flush=True)
        return
    try:
        with sqlite3.connect(USERS_DB) as conn:
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if count > 0:
                print(f"STARTUP: users exist; seed admin skipped", flush=True)
                return
            now = datetime.utcnow().isoformat()
            conn.execute(
                "INSERT INTO users (email, name, password_hash, is_admin, is_approved, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (admin_email.strip().lower(), "Admin", _hash_password(admin_password), 1, 1, now, now),
            )
            conn.commit()
            print(f"STARTUP: seeded admin user {admin_email}", flush=True)
    except Exception as exc:
        print("Seed admin failed:", exc, flush=True)


# Initialize database after all helpers are defined.
def init_auth():
    _restore_users_db()
    _init_db()
    _ensure_admin()
    _seed_admin()
    try:
        with sqlite3.connect(USERS_DB) as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            print(f"STARTUP: user_count={user_count}", flush=True)
    except Exception as exc:
        print(f"STARTUP: user_count unknown: {exc}", flush=True)


# Lazy initialization: main.py calls init_auth() in startup with a timeout.


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
async def register(request: Request, body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "").strip()
    ip = get_client_ip(request)
    if not email or not password:
        log_audit(AUDIT_DB, "register", email=email, ip=ip, details="Missing email or password", success=False)
        raise HTTPException(status_code=400, detail="Email and password required")
    if not register_rate_limiter.is_allowed(f"{ip}:{email}"):
        log_audit(AUDIT_DB, "register", email=email, ip=ip, details="Rate limited", success=False)
        raise HTTPException(status_code=429, detail="Too many registration attempts. Try again later.")
    ok, msg = password_policy(password)
    if not ok:
        log_audit(AUDIT_DB, "register", email=email, ip=ip, details=f"Weak password: {msg}", success=False)
        raise HTTPException(status_code=400, detail=msg)
    is_first = _is_first_user()
    user_id = _create_user(email, password, name)
    token = _create_token(user_id)
    log_audit(AUDIT_DB, "register", user_id=user_id, email=email, ip=ip, details="Registration successful", success=True)
    if is_first:
        return {"ok": True, "token": token, "user": {"id": user_id, "email": email, "name": name, "is_admin": True, "is_approved": True, "mfa_enabled": False}}
    return {"ok": True, "pending_approval": True, "message": "Account created. Waiting for admin approval.", "user": {"id": user_id, "email": email, "name": name, "is_admin": False, "is_approved": False, "mfa_enabled": False}}


@router.post("/login")
async def login(request: Request, body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    ip = get_client_ip(request)
    print(f"[login] email={email} password_len={len(password)}", flush=True)
    if not email or not password:
        log_audit(AUDIT_DB, "login", email=email, ip=ip, details="Missing email or password", success=False)
        raise HTTPException(status_code=400, detail="Email and password required")
    if not login_rate_limiter.is_allowed(f"{ip}:{email}"):
        log_audit(AUDIT_DB, "login", email=email, ip=ip, details="Rate limited", success=False)
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    user = _get_user_by_email(email)
    if not user:
        print(f"[login] user not found for {email}", flush=True)
        log_audit(AUDIT_DB, "login", email=email, ip=ip, details="User not found", success=False)
        raise HTTPException(status_code=401, detail="Invalid email")
    if not user.get("is_approved"):
        print(f"[login] user={user['id']} not approved", flush=True)
        log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="Account not approved", success=False)
        raise HTTPException(status_code=403, detail="Account pending approval")
    verified = _verify_password(password, user["password_hash"])
    print(f"[login] user={user['id']} verified={verified} hash_prefix={user['password_hash'][:20]}", flush=True)
    if not verified:
        log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="Invalid password", success=False)
        raise HTTPException(status_code=401, detail="Invalid password")
    if user.get("is_admin") and user.get("mfa_enabled"):
        totp_code = body.get("totp_code", "").strip()
        if not totp_code:
            log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="MFA code required", success=False)
            return {"ok": True, "mfa_required": True, "message": "Enter the 6-digit code from your authenticator app."}
        if not mfa_rate_limiter.is_allowed(f"{ip}:{email}:mfa"):
            log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="MFA rate limited", success=False)
            raise HTTPException(status_code=429, detail="Too many MFA attempts. Try again later.")
        secret = _decrypt_mfa_secret(user.get("mfa_secret"))
        if not secret or not pyotp.TOTP(secret).verify(totp_code, valid_window=1):
            log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="Invalid MFA code", success=False)
            raise HTTPException(status_code=401, detail="Invalid MFA code")
        log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="MFA verified", success=True)
    token = _create_token(user["id"])
    log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="Login successful", success=True)
    return {"ok": True, "token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"], "is_admin": bool(user.get("is_admin")), "is_approved": bool(user.get("is_approved")), "mfa_enabled": bool(user.get("mfa_enabled"))}}



@router.post("/reset-password")
async def reset_password(request: Request, body: dict):
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    ip = get_client_ip(request)
    if not email or not password or len(password) < 6:
        log_audit(AUDIT_DB, "reset_password", email=email, ip=ip, details="Invalid input", success=False)
        raise HTTPException(status_code=400, detail="Email and password (min 6 chars) required")
    if not password_reset_rate_limiter.is_allowed(f"{ip}:{email}"):
        log_audit(AUDIT_DB, "reset_password", email=email, ip=ip, details="Rate limited", success=False)
        raise HTTPException(status_code=429, detail="Too many reset attempts. Try again later.")
    ok, msg = password_policy(password)
    if not ok:
        log_audit(AUDIT_DB, "reset_password", email=email, ip=ip, details=f"Weak password: {msg}", success=False)
        raise HTTPException(status_code=400, detail=msg)
    if not _update_password(email, password):
        log_audit(AUDIT_DB, "reset_password", email=email, ip=ip, details="Email not found", success=False)
        raise HTTPException(status_code=404, detail="Email not found")
    log_audit(AUDIT_DB, "reset_password", email=email, ip=ip, details="Password updated", success=True)
    return {"ok": True, "message": "Password updated. Sign in with your new password."}


def _require_admin(user: dict):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/pending")
async def pending_users(user: dict = Depends(get_current_user)):
    _require_admin(user)
    with sqlite3.connect(USERS_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, email, name, is_admin, is_approved, created_at FROM users WHERE is_approved = 0 ORDER BY created_at DESC"
        ).fetchall()
        return {"users": [dict(r) for r in rows]}


@router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    _require_admin(user)
    with sqlite3.connect(USERS_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, email, name, is_admin, is_approved, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        return {"users": [dict(r) for r in rows]}


@router.get("/audit-logs")
async def audit_logs(user: dict = Depends(get_current_user), limit: int = 100):
    _require_admin(user)
    with sqlite3.connect(AUDIT_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"logs": [dict(r) for r in rows]}


@router.post("/approve/{user_id}")
async def approve_user(user_id: int, request: Request, admin: dict = Depends(get_current_user)):
    _require_admin(admin)
    ip = get_client_ip(request)
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        cur = conn.execute("UPDATE users SET is_approved = 1, updated_at = ? WHERE id = ?", (now, user_id))
        conn.commit()
        if cur.rowcount == 0:
            log_audit(AUDIT_DB, "approve_user", user_id=admin["id"], email=admin.get("email"), ip=ip, details=f"User {user_id} not found", success=False)
            raise HTTPException(status_code=404, detail="User not found")
    try:
        _backup_users_db()
    except Exception:
        pass
    log_audit(AUDIT_DB, "approve_user", user_id=admin["id"], email=admin.get("email"), ip=ip, details=f"Approved user {user_id}", success=True)
    return {"ok": True}


@router.post("/delete/{user_id}")
async def delete_user(user_id: int, request: Request, admin: dict = Depends(get_current_user)):
    _require_admin(admin)
    ip = get_client_ip(request)
    if admin["id"] == user_id:
        log_audit(AUDIT_DB, "delete_user", user_id=admin["id"], email=admin.get("email"), ip=ip, details="Attempted self-delete", success=False)
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    with sqlite3.connect(USERS_DB) as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        if cur.rowcount == 0:
            log_audit(AUDIT_DB, "delete_user", user_id=admin["id"], email=admin.get("email"), ip=ip, details=f"User {user_id} not found", success=False)
            raise HTTPException(status_code=404, detail="User not found")
    try:
        _backup_users_db()
    except Exception:
        pass
    log_audit(AUDIT_DB, "delete_user", user_id=admin["id"], email=admin.get("email"), ip=ip, details=f"Deleted user {user_id}", success=True)
    return {"ok": True}


@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "is_admin": bool(user.get("is_admin")), "is_approved": bool(user.get("is_approved")), "mfa_enabled": bool(user.get("mfa_enabled"))}


@router.get("/mfa/status")
async def mfa_status(user: dict = Depends(get_current_user)):
    _require_admin(user)
    return {"ok": True, "mfa_enabled": bool(user.get("mfa_enabled"))}


@router.post("/mfa/setup")
async def mfa_setup(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    secret = pyotp.random_base32()
    encrypted = _encrypt_mfa_secret(secret)
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            "UPDATE users SET mfa_secret = ?, mfa_enabled = 0, updated_at = ? WHERE id = ?",
            (encrypted, now, user["id"]),
        )
        conn.commit()
    try:
        _backup_users_db()
    except Exception:
        pass
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="NeuroLab")
    qr = qrcode.make(uri)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_data_url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
    ip = get_client_ip(request)
    log_audit(AUDIT_DB, "mfa_setup", user_id=user["id"], email=user.get("email"), ip=ip, details="MFA setup initiated", success=True)
    return {"ok": True, "secret": secret, "uri": uri, "qr_data_url": qr_data_url, "mfa_enabled": False}


@router.post("/mfa/verify")
async def mfa_verify(request: Request, body: dict, user: dict = Depends(get_current_user)):
    _require_admin(user)
    code = body.get("code", "").strip()
    ip = get_client_ip(request)
    if not code:
        log_audit(AUDIT_DB, "mfa_verify", user_id=user["id"], email=user.get("email"), ip=ip, details="Missing code", success=False)
        raise HTTPException(status_code=400, detail="Code required")
    secret = _decrypt_mfa_secret(user.get("mfa_secret"))
    if not secret:
        log_audit(AUDIT_DB, "mfa_verify", user_id=user["id"], email=user.get("email"), ip=ip, details="MFA not set up", success=False)
        raise HTTPException(status_code=400, detail="MFA not set up")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        log_audit(AUDIT_DB, "mfa_verify", user_id=user["id"], email=user.get("email"), ip=ip, details="Invalid MFA code", success=False)
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            "UPDATE users SET mfa_enabled = 1, updated_at = ? WHERE id = ?",
            (now, user["id"]),
        )
        conn.commit()
    try:
        _backup_users_db()
    except Exception:
        pass
    log_audit(AUDIT_DB, "mfa_verify", user_id=user["id"], email=user.get("email"), ip=ip, details="MFA enabled", success=True)
    return {"ok": True, "mfa_enabled": True}


@router.post("/mfa/disable")
async def mfa_disable(request: Request, user: dict = Depends(get_current_user)):
    _require_admin(user)
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(USERS_DB) as conn:
        conn.execute(
            "UPDATE users SET mfa_secret = NULL, mfa_enabled = 0, updated_at = ? WHERE id = ?",
            (now, user["id"]),
        )
        conn.commit()
    try:
        _backup_users_db()
    except Exception:
        pass
    ip = get_client_ip(request)
    log_audit(AUDIT_DB, "mfa_disable", user_id=user["id"], email=user.get("email"), ip=ip, details="MFA disabled", success=True)
    return {"ok": True, "mfa_enabled": False}


@router.get("/health")
async def auth_health():
    user_count = 0
    try:
        with sqlite3.connect(USERS_DB) as conn:
            user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception:
        pass
    return {"ok": True, "data_dir": str(DATA_DIR), "users_db": str(USERS_DB), "user_count": user_count}


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
