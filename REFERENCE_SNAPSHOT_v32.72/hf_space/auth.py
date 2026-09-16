import os
import json
import base64
import re
import threading
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional

import encrypted_sqlite as sqlite3
import pyotp
import qrcode
from fastapi import APIRouter, Request, Depends, HTTPException, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import service_account as google_service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from security import password_policy, RateLimiter, get_client_ip, log_audit, encrypt_json_to_str, decrypt_json_from_str

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("NEUROLAB_JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = "neurolab-local-dev-secret"
    print("STARTUP: using local dev JWT_SECRET (set JWT_SECRET env for production)", flush=True)
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
    """Encrypt plain SQLite databases and rotate key if DB_ENCRYPTION_KEY changed."""
    if not sqlite3.SQLCIPHER_AVAILABLE:
        print("STARTUP: SQLCipher not available; DB encryption skipped", flush=True)
        return

    key = sqlite3.get_db_key()
    jwt_key = os.environ.get("JWT_SECRET")
    fallback_keys = [k for k in {jwt_key} if k and k != key]

    for db_path in (USERS_DB, AUDIT_DB):
        if not db_path.exists():
            # Create a fresh encrypted database.
            try:
                sqlite3.connect(db_path, key).close()
                print(f"STARTUP: created encrypted {db_path}", flush=True)
            except Exception as exc:
                print(f"STARTUP: failed to create {db_path}: {exc}", flush=True)
            continue

        # Already encrypted with the current key?
        try:
            with sqlite3.connect(db_path, key) as conn:
                conn.execute("SELECT 1")
            print(f"STARTUP: {db_path} already encrypted with current key", flush=True)
            continue
        except Exception:
            pass

        # Try to rotate from an old key.
        rotated = False
        for old_key in fallback_keys:
            try:
                sqlite3.rotate_key(db_path, old_key, key)
                print(f"STARTUP: rotated encryption key for {db_path}", flush=True)
                rotated = True
                break
            except Exception as exc:
                print(f"STARTUP: key rotation failed for {db_path} with fallback key: {exc}", flush=True)
        if rotated:
            continue

        # Plain database? Encrypt it now.
        try:
            if sqlite3.is_plain_sqlite(db_path):
                sqlite3.encrypt_db_inplace(db_path, key)
                print(f"STARTUP: encrypted plain {db_path}", flush=True)
                continue
        except Exception as exc:
            print(f"STARTUP: failed to encrypt plain {db_path}: {exc}", flush=True)

        print(f"STARTUP: {db_path} could not be opened with current key; manual recovery may be needed", flush=True)


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
                if "last_login_email" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN last_login_email TEXT")
                if "last_login_at" not in columns:
                    conn.execute("ALTER TABLE users ADD COLUMN last_login_at TEXT")
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
                last_login_email TEXT,
                last_login_at TEXT,
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


def _auth_cookie_response(payload: dict, token: str) -> JSONResponse:
    """Set neurolab_token cookie (name kept after Space rename) + JSON body."""
    resp = JSONResponse(payload)
    resp.set_cookie(
        "neurolab_token",
        token,
        max_age=ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )
    return resp


def _record_last_login(user_id: int, email: str) -> None:
    now = datetime.utcnow().isoformat()
    try:
        with sqlite3.connect(USERS_DB) as conn:
            conn.execute(
                "UPDATE users SET last_login_email = ?, last_login_at = ?, updated_at = ? WHERE id = ?",
                (email, now, now, user_id),
            )
            conn.commit()
    except Exception as exc:
        print(f"last_login update failed: {exc}", flush=True)


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
    try:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = google_service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        _drive_service_instance = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _drive_service_instance
    except Exception as exc:
        print("Drive service init failed:", exc, flush=True)
        return None


def _drive_patients_filename(user_id: int) -> str:
    return f"neurolab_patients_{user_id}.json"


def _drive_sanitize_name(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", (name or "").strip())[:180]


def _drive_list_flags() -> dict:
    return {"supportsAllDrives": True, "includeItemsFromAllDrives": True}


def _drive_write_flags() -> dict:
    return {"supportsAllDrives": True}


def _drive_owner_share_email() -> Optional[str]:
    return (
        (os.environ.get("GOOGLE_DRIVE_SHARE_EMAIL") or os.environ.get("NEUROLAB_ADMIN_EMAIL") or "")
        .strip()
        .lower()
        or None
    )


def _drive_share_with_owner(service, file_id: str) -> Optional[str]:
    """Make SA-owned files show up in the clinic owner's Google Drive."""
    email = _drive_owner_share_email()
    if not email or not file_id:
        return None
    try:
        service.permissions().create(
            fileId=file_id,
            body={"type": "user", "role": "writer", "emailAddress": email},
            sendNotificationEmail=False,
            fields="id",
            **_drive_write_flags(),
        ).execute()
        return email
    except HttpError as exc:
        reason = (exc.reason or str(exc)).lower()
        if "already" in reason or "owner" in reason or "duplicate" in reason:
            return email
        print(f"Drive share skipped ({file_id}): {exc}", flush=True)
        return None
    except Exception as exc:
        print(f"Drive share skipped ({file_id}): {exc}", flush=True)
        return None


def _drive_find_folder(service, parent_id: str, folder_name: str) -> Optional[str]:
    safe = folder_name.replace("'", "\\'")
    q = (
        f"'{parent_id}' in parents and name='{safe}' "
        "and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res = service.files().list(
        q=q, spaces="drive", fields="files(id, name)", **_drive_list_flags()
    ).execute()
    files = res.get("files", [])
    return files[0]["id"] if files else None


def _drive_create_folder(service, parent_id: str, folder_name: str) -> str:
    created = service.files().create(
        body={
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        },
        fields="id",
        **_drive_write_flags(),
    ).execute()
    folder_id = created["id"]
    _drive_share_with_owner(service, folder_id)
    return folder_id


def _drive_find_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    name = _drive_sanitize_name(folder_name) or "folder"
    existing = _drive_find_folder(service, parent_id, name)
    if existing:
        return existing
    return _drive_create_folder(service, parent_id, name)


def _drive_user_root_folder(service, user_id: int) -> str:
    return _drive_find_or_create_folder(service, GOOGLE_DRIVE_FOLDER_ID, f"u{user_id}")


def _patient_drive_key_from_record(p: dict) -> str:
    try:
        from patient_drive_archive import patient_drive_key

        return patient_drive_key(p if isinstance(p, dict) else {})
    except Exception:
        if not isinstance(p, dict):
            return "unknown"
        d = p.get("demographics") or {}
        pid = str(d.get("participantId") or p.get("_id") or "unknown").strip()
        label = str(d.get("name") or d.get("fullName") or "").strip()
        if label:
            return _drive_sanitize_name(f"{pid}_{label}")[:120]
        return _drive_sanitize_name(pid)[:120] or "unknown"


def _drive_patient_folder(service, user_id: int, patient_key: str) -> str:
    from drive_persist import _patient_folder

    user_root = _drive_user_root_folder(service, user_id)
    safe = _drive_sanitize_name(patient_key)[:120] or "patient_unknown"
    return _patient_folder(service, user_root, safe)


def _drive_patient_subfolder(service, user_id: int, patient_key: str, subfolder: str) -> str:
    patient_root = _drive_patient_folder(service, user_id, patient_key)
    sub = _drive_sanitize_name(subfolder) or "files"
    return _drive_find_or_create_folder(service, patient_root, sub)


def _drive_team_patients_root(service) -> str:
    """Shared validation artifacts — visible to all approved app users."""
    return _drive_find_or_create_folder(service, GOOGLE_DRIVE_FOLDER_ID, "team_patients")


def _drive_team_patient_subfolder(service, patient_key: str, subfolder: str) -> str:
    from drive_persist import _patient_folder

    team_root = _drive_team_patients_root(service)
    safe = _drive_sanitize_name(patient_key)[:120] or "patient_unknown"
    patient_root = _patient_folder(service, team_root, safe)
    sub = _drive_sanitize_name(subfolder) or "files"
    return _drive_find_or_create_folder(service, patient_root, sub)


def _drive_parent_for_patient_artifact(
    service,
    user_id: int,
    patient_key: str,
    subfolder: str,
    scope: str,
) -> str:
    from drive_persist import _patient_folder, clinic_folder_id

    _ = (user_id, subfolder, scope)
    return _patient_folder(service, clinic_folder_id() or GOOGLE_DRIVE_FOLDER_ID, patient_key)


def _drive_upsert_bytes(
    service,
    name: str,
    content: bytes,
    mime: str,
    parent_id: Optional[str] = None,
) -> str:
    parent = parent_id or GOOGLE_DRIVE_FOLDER_ID
    safe_name = name.replace("'", "\\'")
    q = f"'{parent}' in parents and name='{safe_name}' and trashed=false"
    res = service.files().list(
        q=q, spaces="drive", fields="files(id, name)", **_drive_list_flags()
    ).execute()
    files = res.get("files", [])
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime, resumable=True)
    try:
        if files:
            keep_id = files[0]["id"]
            service.files().update(
                fileId=keep_id, media_body=media, **_drive_write_flags()
            ).execute()
            _drive_share_with_owner(service, keep_id)
            for extra in files[1:]:
                extra_id = extra.get("id") or ""
                if extra_id and extra_id != keep_id:
                    try:
                        from drive_persist import _trash_file

                        _trash_file(service, extra_id)
                    except Exception as trash_exc:
                        print(f"Drive extra-name trash skipped: {trash_exc}", flush=True)
            return keep_id
        created = service.files().create(
            body={"name": name, "parents": [parent]},
            media_body=media,
            fields="id",
            **_drive_write_flags(),
        ).execute()
        _drive_share_with_owner(service, created["id"])
        return created["id"]
    except HttpError as exc:
        print(f"Drive upsert failed ({name}): {exc}", flush=True)
        raise


def _drive_count_mp4(service, folder_id: str, limit: int = 200, depth: int = 0) -> int:
    if not folder_id or depth > 6:
        return 0
    total = 0
    page_token = None
    while True:
        res = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            spaces="drive",
            pageSize=100,
            pageToken=page_token,
            fields="nextPageToken, files(id, name, mimeType)",
            **_drive_list_flags(),
        ).execute()
        for item in res.get("files") or []:
            mime = item.get("mimeType") or ""
            name = (item.get("name") or "").lower()
            if mime == "application/vnd.google-apps.folder":
                total += _drive_count_mp4(service, item.get("id") or "", limit, depth + 1)
            elif name.endswith(".mp4") or mime == "video/mp4":
                total += 1
            if total >= limit:
                return total
        page_token = res.get("nextPageToken")
        if not page_token:
            break
    return total


def _drive_folder_inventory(service) -> dict:
    inv = {
        "folderName": None,
        "folderUrl": None,
        "ownedByServiceAccount": None,
        "rootChildren": [],
        "videoCount": 0,
        "sharedWith": _drive_owner_share_email(),
    }
    if not GOOGLE_DRIVE_FOLDER_ID:
        return inv
    meta = service.files().get(
        fileId=GOOGLE_DRIVE_FOLDER_ID,
        fields="id,name,webViewLink,owners",
        **_drive_write_flags(),
    ).execute()
    inv["folderName"] = meta.get("name")
    inv["folderUrl"] = meta.get("webViewLink")
    owners = [o.get("emailAddress") for o in (meta.get("owners") or []) if o.get("emailAddress")]
    sa = None
    try:
        sa = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON or "{}").get("client_email")
    except Exception:
        sa = None
    inv["ownedByServiceAccount"] = bool(sa and sa in owners)
    res = service.files().list(
        q=f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false",
        spaces="drive",
        pageSize=100,
        fields="files(id, name, mimeType)",
        **_drive_list_flags(),
    ).execute()
    inv["rootChildren"] = [f.get("name") for f in res.get("files") or [] if f.get("name")]
    team = _drive_find_folder(service, GOOGLE_DRIVE_FOLDER_ID, "team_patients")
    if team:
        inv["videoCount"] = _drive_count_mp4(service, team)
    return inv


def _ensure_drive_visible_to_owner() -> dict:
    """Share the backup folder with the clinic Gmail and drop a finder file."""
    out = {"ok": False}
    service = _drive_service()
    if not service or not GOOGLE_DRIVE_FOLDER_ID:
        return out
    try:
        shared = _drive_share_with_owner(service, GOOGLE_DRIVE_FOLDER_ID)
        marker_id = None
        team_id = None
        inv = _drive_folder_inventory(service)
        out.update(inv)
        out["ok"] = True
        out["sharedWith"] = shared or inv.get("sharedWith")
        out["markerId"] = marker_id
        out["teamPatientsId"] = team_id
        return out
    except Exception as exc:
        out["error"] = str(exc)[:300]
        print(f"Drive visibility setup failed: {exc}", flush=True)
        return out


def _drive_health_summary() -> dict:
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
    out["serviceInitialized"] = True
    try:
        inv = _drive_folder_inventory(service)
        out["folderReachable"] = True
        out["folderName"] = inv.get("folderName")
        out["folderUrl"] = inv.get("folderUrl")
        out["videoCount"] = inv.get("videoCount") or 0
        out["rootChildren"] = inv.get("rootChildren") or []
        out["ownedByServiceAccount"] = inv.get("ownedByServiceAccount")
    except HttpError as exc:
        out["error"] = (exc.reason or str(exc))[:300]
    except Exception as exc:
        out["error"] = str(exc)[:300]
    return out


def _backup_users_db():
    service = _drive_service()
    if not service:
        return
    try:
        user_root = _drive_find_or_create_folder(service, GOOGLE_DRIVE_FOLDER_ID, "_system")
        q = f"'{user_root}' in parents and name='users.db' and trashed=false"
        res = service.files().list(
            q=q, spaces="drive", fields="files(id, name)", **_drive_list_flags()
        ).execute()
        files = res.get("files", [])
        media = MediaIoBaseUpload(BytesIO(USERS_DB.read_bytes()), mimetype="application/x-sqlite3", resumable=True)
        if files:
            service.files().update(
                fileId=files[0]["id"], media_body=media, **_drive_write_flags()
            ).execute()
        else:
            service.files().create(
                body={"name": "users.db", "parents": [user_root]},
                media_body=media,
                fields="id",
                **_drive_write_flags(),
            ).execute()
        print("Users DB backed up to Drive", flush=True)
    except Exception as exc:
        print("Users DB backup failed:", exc, flush=True)


def _restore_users_db():
    service = _drive_service()
    if not service:
        return
    try:
        system_root = _drive_find_folder(service, GOOGLE_DRIVE_FOLDER_ID, "_system")
        files = []
        if system_root:
            q = f"'{system_root}' in parents and name='users.db' and trashed=false"
            res = service.files().list(
                q=q, spaces="drive", fields="files(id, name)", **_drive_list_flags()
            ).execute()
            files = res.get("files", [])
        if not files:
            q_legacy = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and name='users.db' and trashed=false"
            res = service.files().list(
                q=q_legacy, spaces="drive", fields="files(id, name)", **_drive_list_flags()
            ).execute()
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
    """Create admin from HF secrets, or re-sync password so clinic login always matches Secrets."""
    admin_email = os.environ.get("NEUROLAB_ADMIN_EMAIL")
    admin_password = os.environ.get("NEUROLAB_ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        print("STARTUP: no NEUROLAB_ADMIN_EMAIL/PASSWORD set; skipping seed admin", flush=True)
        return
    email = admin_email.strip().lower()
    try:
        with sqlite3.connect(USERS_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id, email FROM users WHERE email = ?", (email,)).fetchone()
            now = datetime.utcnow().isoformat()
            pw_hash = _hash_password(admin_password)
            if row:
                conn.execute(
                    "UPDATE users SET password_hash = ?, is_admin = 1, is_approved = 1, updated_at = ? WHERE id = ?",
                    (pw_hash, now, row["id"]),
                )
                conn.commit()
                print(f"STARTUP: synced admin password from secrets for {email}", flush=True)
                return
            conn.execute(
                "INSERT INTO users (email, name, password_hash, is_admin, is_approved, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (email, "Admin", pw_hash, 1, 1, now, now),
            )
            conn.commit()
            print(f"STARTUP: seeded admin user {email}", flush=True)
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
    dh = _drive_health_summary()
    if not dh["configured"]:
        print("STARTUP: Drive backup OFF — set HF secrets for service account + folder ID", flush=True)
    elif dh["folderReachable"]:
        vis = _ensure_drive_visible_to_owner()
        print(
            "STARTUP: Drive OK "
            f"name={vis.get('folderName') or dh.get('folderName')} "
            f"url={vis.get('folderUrl') or dh.get('folderUrl')} "
            f"videos={vis.get('videoCount', dh.get('videoCount'))} "
            f"children={vis.get('rootChildren') or dh.get('rootChildren')} "
            f"sharedWith={vis.get('sharedWith')} "
            f"sa={dh.get('serviceAccountEmail')}",
            flush=True,
        )
        if vis.get("error"):
            print(f"STARTUP: Drive visibility error: {vis.get('error')}", flush=True)
    else:
        print(f"STARTUP: Drive NOT reachable: {dh.get('error')}", flush=True)


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
        _record_last_login(user_id, email)
        return _auth_cookie_response(
            {
                "ok": True,
                "token": token,
                "user": {
                    "id": user_id,
                    "email": email,
                    "name": name,
                    "is_admin": True,
                    "is_approved": True,
                    "mfa_enabled": False,
                    "last_login_email": email,
                },
            },
            token,
        )
    return {
        "ok": True,
        "pending_approval": True,
        "message": "Account created. Waiting for admin approval.",
        "user": {
            "id": user_id,
            "email": email,
            "name": name,
            "is_admin": False,
            "is_approved": False,
            "mfa_enabled": False,
        },
    }


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
    hash_prefix = (user.get("password_hash") or "")[:20]
    print(f"[login] user={user['id']} verified={verified} hash_prefix={hash_prefix}", flush=True)
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
    _record_last_login(user["id"], email)
    log_audit(AUDIT_DB, "login", user_id=user["id"], email=email, ip=ip, details="Login successful", success=True)
    return _auth_cookie_response(
        {
            "ok": True,
            "token": token,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "name": user["name"],
                "is_admin": bool(user.get("is_admin")),
                "is_approved": bool(user.get("is_approved")),
                "mfa_enabled": bool(user.get("mfa_enabled")),
                "last_login_email": email,
            },
        },
        token,
    )



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
    email = user.get("email")
    return {
        "id": user["id"],
        "email": email,
        "name": user["name"],
        "is_admin": bool(user.get("is_admin")),
        "is_approved": bool(user.get("is_approved")),
        "mfa_enabled": bool(user.get("mfa_enabled")),
        "last_login_email": user.get("last_login_email") or email,
        "last_login_at": user.get("last_login_at"),
    }


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
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user["email"], issuer_name="RA.ED AI")
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
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "users_db": str(USERS_DB),
        "user_count": user_count,
        "drive": _drive_health_summary(),
    }


@router.post("/logout")
async def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("neurolab_token", path="/")
    return resp


def _normalize_patients_payload(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        pts = body.get("patients")
        if isinstance(pts, list):
            return pts
    return []


def _patient_record_is_rich(patient: dict) -> bool:
    """True when a synced program record has real session/assessment content (not a Drive shell)."""
    if not isinstance(patient, dict):
        return False
    kin = patient.get("kinematics") if isinstance(patient.get("kinematics"), dict) else {}
    ar = kin.get("analysisResults") if isinstance(kin.get("analysisResults"), dict) else {}
    for _phase, vals in ar.items():
        if isinstance(vals, dict) and vals:
            return True
    for key in ("ipaq", "vas", "vams", "motorchange", "kgia", "wmft"):
        section = patient.get(key)
        if isinstance(section, dict) and section:
            return True
        if isinstance(section, list) and section:
            return True
    return False


def _patients_snapshot_is_rich(patients: list) -> bool:
    """Prefer neurolab_patients_*.json when it looks like a real Sync dump, not empty shells."""
    if not isinstance(patients, list) or not patients:
        return False
    rich_n = sum(1 for p in patients if isinstance(p, dict) and _patient_record_is_rich(p))
    if rich_n == 0:
        return False
    if rich_n >= max(3, len(patients) // 4):
        return True
    return rich_n >= 1 and len(patients) <= 8


@router.get("/drive/status")
async def drive_status(user: dict = Depends(get_current_user)):
    """Admin-only: verify Google Drive backup folder + service account access."""
    _require_admin(user)
    has_json = bool(GOOGLE_SERVICE_ACCOUNT_JSON)
    has_folder = bool(GOOGLE_DRIVE_FOLDER_ID)
    sa_email = None
    if has_json:
        try:
            sa_email = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON).get("client_email")
        except Exception:
            pass
    folder_hint = None
    if GOOGLE_DRIVE_FOLDER_ID:
        fid = GOOGLE_DRIVE_FOLDER_ID
        folder_hint = f"{fid[:6]}…{fid[-4:]}" if len(fid) > 12 else "set"

    service = _drive_service()
    drive_reachable = False
    users_db_on_drive = False
    patient_backups: list = []
    drive_error = None
    inv: dict = {}
    if service and GOOGLE_DRIVE_FOLDER_ID:
        try:
            q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed=false"
            res = service.files().list(
                q=q,
                spaces="drive",
                pageSize=200,
                fields="files(id, name, modifiedTime)",
                **_drive_list_flags(),
            ).execute()
            drive_reachable = True
            for f in res.get("files", []):
                name = f.get("name") or ""
                if name == "users.db":
                    users_db_on_drive = True
                if name.startswith("neurolab_patients_") and name.endswith(".json"):
                    patient_backups.append(
                        {"name": name, "modifiedTime": f.get("modifiedTime")}
                    )
            inv = _drive_folder_inventory(service)
        except Exception as exc:
            drive_error = str(exc)
            inv = {}

    return {
        "configured": has_json and has_folder,
        "serviceAccountEmail": sa_email,
        "folderIdHint": folder_hint,
        "folderName": inv.get("folderName") if drive_reachable else None,
        "folderUrl": inv.get("folderUrl") if drive_reachable else None,
        "videoCount": inv.get("videoCount") if drive_reachable else 0,
        "rootChildren": inv.get("rootChildren") if drive_reachable else [],
        "driveReachable": drive_reachable,
        "usersDbOnDrive": users_db_on_drive,
        "patientBackupCount": len(patient_backups),
        "patientBackups": sorted(patient_backups, key=lambda x: x.get("name") or ""),
        "driveError": drive_error,
        "adminLoginEmailEnv": os.environ.get("NEUROLAB_ADMIN_EMAIL"),
        "note": (
            "Open folderUrl in Google Drive. Videos are under team_patients/<patient>/videos/. "
            "Search Drive for NEUROLAB_VIDEOS_HERE.txt if the folder is not in My Drive."
        ),
    }


def _backup_patient_snapshots_worker(service, user_id: int, patients: list) -> None:
    try:
        from drive_persist import reconcile_drive_to_program

        result = reconcile_drive_to_program(list(patients or []), service=service)
        print(
            "Drive reconcile backup:",
            f"before={result.get('beforeCount')} after={result.get('afterCount')} "
            f"trashed={len(result.get('trashedAliases') or [])} ok={result.get('ok')}",
            flush=True,
        )
        if result.get("ok"):
            return
    except Exception as exc:
        print("Drive reconcile backup failed:", exc, flush=True)
    try:
        for p in patients:
            if not isinstance(p, dict):
                continue
            if p.get("_archived"):
                continue
            try:
                from patient_drive_archive import archive_patients

                archive_patients([p], user_id=user_id)
                continue
            except Exception as arch_exc:
                print("Patient program archive:", arch_exc, flush=True)
            continue
    except Exception as exc:
        print("Patient snapshot backup failed:", exc, flush=True)


def _persist_restored_patients(user: dict, patients: list) -> None:
    """Write restored Drive patients onto durable HF disk so Sync/login find them.

    Merge with any richer records already on disk — never overwrite kinematics/scales
    with empty shells from a prior broken restore.
    """
    if not isinstance(patients, list) or not patients:
        return
    try:
        from patient_drive_archive import load_patients_file, merge_patients, merge_same_name_patients

        existing: list = []
        path = PATIENTS_DIR / f"{int(user['id'])}.json"
        if path.is_file():
            existing = load_patients_file(path)
        clinic = DATA_DIR / "patients.json"
        if clinic.is_file():
            existing = merge_patients(existing, load_patients_file(clinic))
        merged = merge_same_name_patients(merge_patients(existing, patients))
        if JWT_SECRET and encrypt_json_to_str:
            path.write_text(encrypt_json_to_str(merged, JWT_SECRET), encoding="utf-8")
        else:
            path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        clinic.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Persist restored patients failed: {exc}", flush=True)


@router.post("/backup")
async def backup_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    patients = body.get("patients", [])
    if not isinstance(patients, list):
        patients = _normalize_patients_payload(body)
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    file_name = _drive_patients_filename(user["id"])
    payload = json.dumps(
        {"patients": patients, "updatedAt": datetime.utcnow().isoformat()},
        ensure_ascii=False,
    ).encode("utf-8")
    try:
        # Always upsert the JSON snapshot (was previously built but never uploaded).
        user_root = _drive_user_root_folder(service, user["id"])
        file_id = _drive_upsert_bytes(
            service,
            file_name,
            payload,
            "application/json",
            parent_id=user_root,
        )
        # Also keep a copy at clinic backup root for easy discovery after Space rename.
        try:
            _drive_upsert_bytes(
                service,
                file_name,
                payload,
                "application/json",
                parent_id=GOOGLE_DRIVE_FOLDER_ID,
            )
        except Exception as root_exc:
            print(f"Drive root patients snapshot: {root_exc}", flush=True)
        patient_folders = len([p for p in patients if isinstance(p, dict)])
        threading.Thread(
            target=_backup_patient_snapshots_worker,
            args=(service, user["id"], list(patients)),
            daemon=True,
        ).start()
    except HttpError as exc:
        sa = _drive_health_summary().get("serviceAccountEmail") or "the service account email"
        raise HTTPException(
            status_code=502,
            detail=(
                f"Drive upload failed: {exc.reason or str(exc)}. "
                f"Share your backup folder with {sa} as Editor and set GOOGLE_DRIVE_FOLDER_ID to that folder's ID."
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Drive upload failed: {exc}")
    return {
        "ok": True,
        "fileName": file_name,
        "fileId": file_id,
        "userFolder": f"u{user['id']}",
        "patientFolders": patient_folders,
        "reconcileStarted": True,
    }


@router.get("/restore")
async def restore_drive(user: dict = Depends(get_current_user)):
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    file_name = _drive_patients_filename(user["id"])
    json_patients: list = []
    folder_patients: list = []
    source = None
    used_name = None
    folder_meta: dict = {}

    # 1) Preferred: neurolab_patients_{id}.json (user folder, clinic root, or newest snapshot).
    try:
        files = []
        user_root = _drive_user_root_folder(service, user["id"])
        q = f"'{user_root}' in parents and name='{file_name}' and trashed=false"
        res = service.files().list(
            q=q, spaces="drive", fields="files(id, name, modifiedTime)", **_drive_list_flags()
        ).execute()
        files = res.get("files", [])
        if not files and GOOGLE_DRIVE_FOLDER_ID:
            q_legacy = (
                f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and name contains 'neurolab_patients_' "
                f"and mimeType!='application/vnd.google-apps.folder' and trashed=false"
            )
            res = service.files().list(
                q=q_legacy,
                spaces="drive",
                fields="files(id, name, modifiedTime)",
                orderBy="modifiedTime desc",
                pageSize=10,
                **_drive_list_flags(),
            ).execute()
            cand = [
                f
                for f in res.get("files", [])
                if str(f.get("name") or "").startswith("neurolab_patients_")
                and str(f.get("name") or "").endswith(".json")
            ]
            # Prefer exact user file, else newest snapshot.
            exact = [f for f in cand if f.get("name") == file_name]
            files = exact or cand
        if files:
            content = service.files().get_media(fileId=files[0]["id"]).execute()
            data = json.loads(content.decode("utf-8"))
            json_patients = _normalize_patients_payload(data)
            if json_patients:
                source = "json"
                used_name = files[0].get("name")
                mt = files[0].get("modifiedTime")
                for p in json_patients:
                    if isinstance(p, dict):
                        raw_ts = p.get("_savedAt")
                        if not raw_ts or raw_ts in ("None", "null"):
                            p["_savedAt"] = mt or datetime.utcnow().isoformat() + "Z"
    except Exception as exc:
        print(f"Drive JSON restore: {exc}", flush=True)

    # 2) If Sync JSON is rich → use it ONLY (never rebuild from PDF names).
    #    PDF/folder rebuild was corrupting good snapshots (shell names, Pre missing).
    if json_patients and _patients_snapshot_is_rich(json_patients):
        patients = json_patients
        _persist_restored_patients(user, patients)
        return {
            "patients": patients,
            "fileName": used_name,
            "source": "json",
            "folderCount": 0,
            "pdfParsed": 0,
            "jsonSnapshots": 1,
            "excelPatients": 0,
            "error": None,
            "message": "Restored from neurolab_patients JSON (PDF parse skipped).",
        }

    # 3) Fallback only when JSON missing/empty shells: folders + kinematics JSON (+ PDF last).
    try:
        from patient_drive_archive import restore_patients_from_clinic_drive

        folder_meta = restore_patients_from_clinic_drive(parse_pdfs=True)
        folder_patients = folder_meta.get("patients") or []
        if folder_patients and not source:
            source = folder_meta.get("source") or "folders"
            used_name = folder_meta.get("source") or "clinic_folders"
        elif folder_patients and source == "json":
            source = "json+folders"
    except Exception as exc:
        print(f"Drive folder restore: {exc}", flush=True)
        folder_meta = {"error": str(exc)[:300]}

    patients: list = []
    try:
        from patient_drive_archive import (
            load_program_patients,
            merge_patients,
            merge_same_name_patients,
        )

        disk_patients = []
        try:
            disk_patients = load_program_patients(DATA_DIR)
        except Exception:
            disk_patients = []
        # JSON first in merge order so it wins over PDF shells when both exist.
        patients = merge_same_name_patients(
            merge_patients(json_patients, disk_patients, folder_patients)
        )
    except Exception as exc:
        print(f"Drive restore merge: {exc}", flush=True)
        patients = json_patients or folder_patients

    if patients:
        _persist_restored_patients(user, patients)

    return {
        "patients": patients,
        "fileName": used_name,
        "source": source,
        "folderCount": folder_meta.get("folderCount"),
        "pdfParsed": folder_meta.get("pdfParsed"),
        "jsonSnapshots": folder_meta.get("jsonSnapshots"),
        "excelPatients": folder_meta.get("excelPatients"),
        "error": folder_meta.get("error"),
    }


@router.post("/backup-file")
async def backup_file_drive(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    name = _drive_sanitize_name(body.get("name", ""))
    b64 = body.get("contentBase64", "")
    if not name or not b64:
        raise HTTPException(status_code=400, detail="name and contentBase64 required")
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    try:
        content = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    patient_key = (body.get("patientKey") or "").strip()
    subfolder = (body.get("subfolder") or "").strip().lower()
    scope = (body.get("scope") or "team").strip().lower()
    mime = body.get("mimeType") or "application/octet-stream"

    # Clinic-wide study Excel under RAED_AI_Backups/Excel/ (not patient folders).
    if subfolder in ("excel", "excels") or scope in ("excel", "clinic_excel"):
        try:
            from drive_persist import upload_excel_bytes

            saved = upload_excel_bytes(name, content, service=service)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Drive Excel upload failed: {exc}") from exc
        if not saved.get("ok"):
            raise HTTPException(
                status_code=502,
                detail=saved.get("error") or saved.get("reason") or "Drive Excel upload failed",
            )
        return {
            "ok": True,
            "fileName": saved.get("name") or name,
            "fileId": saved.get("id"),
            "patientKey": None,
            "subfolder": "excel",
            "folder": saved.get("folder") or "Excel",
        }

    if patient_key:
        safe_key = _drive_sanitize_name(patient_key)[:120]
        if subfolder in ("videos", "reports", "data"):
            parent = _drive_parent_for_patient_artifact(service, user["id"], safe_key, subfolder, scope)
        else:
            parent = (
                _drive_team_patient_subfolder(service, safe_key, "data")
                if scope == "team"
                else _drive_patient_folder(service, user["id"], safe_key)
            )
        try:
            from drive_persist import clinic_drive_filename

            mapped = clinic_drive_filename(name, patient_key=safe_key)
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
    except HttpError as exc:
        raise HTTPException(status_code=502, detail=f"Drive upload failed: {exc.reason or str(exc)}")
    if patient_key:
        try:
            from drive_persist import trash_same_kind_aliases

            trash_same_kind_aliases(
                service,
                parent,
                drive_name,
                keep_id=file_id,
                folder_key=_drive_sanitize_name(patient_key)[:120],
            )
        except Exception as alias_exc:
            print(f"Drive alias trash skipped ({drive_name}): {alias_exc}", flush=True)
    return {
        "ok": True,
        "fileName": drive_name,
        "fileId": file_id,
        "patientKey": patient_key or None,
        "subfolder": subfolder or None,
    }


def _drive_find_file_bytes(service, parent_id: str, name: str) -> Optional[tuple]:
    safe_name = _drive_sanitize_name(name)
    if not safe_name:
        return None
    q = f"'{parent_id}' in parents and name='{safe_name.replace(chr(39), chr(92)+chr(39))}' and trashed=false"
    res = service.files().list(
        q=q, spaces="drive", fields="files(id, name, mimeType, size)", **_drive_list_flags()
    ).execute()
    files = res.get("files", [])
    if not files:
        return None
    meta = files[0]
    content = service.files().get_media(fileId=meta["id"]).execute()
    mime = meta.get("mimeType") or "application/octet-stream"
    return content, mime, meta.get("name") or safe_name


@router.get("/restore-file")
async def restore_file_drive(
    patientKey: str,
    name: str,
    subfolder: str = "videos",
    scope: str = "auto",
    user: dict = Depends(get_current_user),
):
    """Download a patient artifact from Google Drive (team shared or per-user backup)."""
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    safe_key = _drive_sanitize_name(patientKey)[:120]
    if not safe_key:
        raise HTTPException(status_code=400, detail="patientKey required")
    sub = (subfolder or "videos").strip().lower()
    if sub not in ("videos", "reports", "data"):
        sub = "videos"
    scope_norm = (scope or "auto").strip().lower()
    if scope_norm == "auto":
        scopes = ("team", "user")
    elif scope_norm in ("team", "user"):
        scopes = (scope_norm,)
    else:
        scopes = ("team", "user")
    names = [name]
    try:
        from drive_persist import clinic_drive_filename

        mapped = clinic_drive_filename(name, patient_key=safe_key)
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


@router.post("/backup-file-upload")
async def backup_file_upload_drive(
    file: UploadFile = File(...),
    patientKey: str = Form(...),
    name: str = Form(...),
    subfolder: str = Form("videos"),
    scope: str = Form("team"),
    user: dict = Depends(get_current_user),
):
    """Multipart Drive upload for large validation videos (>32MB base64 limit)."""
    service = _drive_service()
    if not service:
        raise HTTPException(status_code=500, detail="Google Drive not configured")
    safe_key = _drive_sanitize_name(patientKey)[:120]
    if not safe_key:
        raise HTTPException(status_code=400, detail="patientKey required")
    drive_name = _drive_sanitize_name(name)
    if not drive_name:
        raise HTTPException(status_code=400, detail="name required")
    try:
        from drive_persist import clinic_drive_filename

        mapped = clinic_drive_filename(drive_name, patient_key=safe_key)
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
    scope_norm = (scope or "team").strip().lower()
    if sub in ("videos", "reports", "data"):
        parent = _drive_parent_for_patient_artifact(service, user["id"], safe_key, sub, scope_norm)
    else:
        parent = (
            _drive_team_patient_subfolder(service, safe_key, "data")
            if scope_norm == "team"
            else _drive_patient_folder(service, user["id"], safe_key)
        )
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read upload: {exc}")
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    mime = file.content_type or "application/octet-stream"
    try:
        file_id = _drive_upsert_bytes(service, drive_name, content, mime, parent_id=parent)
    except HttpError as exc:
        raise HTTPException(status_code=502, detail=f"Drive upload failed: {exc.reason or str(exc)}")
    try:
        from drive_persist import trash_same_kind_aliases

        trash_same_kind_aliases(
            service, parent, drive_name, keep_id=file_id, folder_key=safe_key
        )
    except Exception as alias_exc:
        print(f"Drive alias trash skipped ({drive_name}): {alias_exc}", flush=True)
    return {
        "ok": True,
        "fileName": drive_name,
        "fileId": file_id,
        "patientKey": safe_key,
        "subfolder": sub,
        "bytes": len(content),
    }


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


from drive_oauth_routes import register_drive_oauth_routes

register_drive_oauth_routes(router, get_current_user)
