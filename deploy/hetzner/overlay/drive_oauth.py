"""Google Drive access using the clinic owner's Google login (OAuth).

Service accounts have zero storage quota on personal Gmail. User OAuth uses the
owner's Drive space (the free terabytes) and files show up in My Drive.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_FILE = "google_oauth_token.json"
DEFAULT_FOLDER_NAME = "NeuroLab_Backups"
DEFAULT_REDIRECT = "https://abdelrahmansabee-neurolab.hf.space/auth/drive/callback"


def _data_dir() -> Path:
    env = os.environ.get("NEUROLAB_DATA_DIR")
    candidates = [Path(env)] if env else []
    candidates += [Path("/data/neurolab"), Path(__file__).resolve().parent / "data"]
    for path in candidates:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue
    fallback = Path(__file__).resolve().parent / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def client_id() -> str:
    return (os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or "").strip()


def client_secret() -> str:
    return (os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or "").strip()


def redirect_uri() -> str:
    return (os.environ.get("GOOGLE_OAUTH_REDIRECT_URI") or DEFAULT_REDIRECT).strip()


def oauth_client_configured() -> bool:
    return bool(client_id() and client_secret())


def token_path() -> Path:
    return _data_dir() / TOKEN_FILE


def _fernet():
    from cryptography.fernet import Fernet

    raw = (os.environ.get("JWT_SECRET") or os.environ.get("NEUROLAB_JWT_SECRET") or "neurolab-local-dev-secret").encode()
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def load_token() -> Dict[str, Any]:
    env_refresh = (os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN") or "").strip()
    path = token_path()
    data: Dict[str, Any] = {}
    if path.is_file():
        raw = path.read_bytes()
        try:
            data = json.loads(_fernet().decrypt(raw).decode("utf-8"))
        except Exception:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                data = {}
    if env_refresh and not (data.get("refresh_token") or "").strip():
        data["refresh_token"] = env_refresh
    return data if isinstance(data, dict) else {}


def save_token(data: Dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    dest = token_path()
    dest.write_bytes(_fernet().encrypt(payload))
    try:
        dest.chmod(0o600)
    except OSError:
        pass


def clear_token() -> None:
    path = token_path()
    if path.is_file():
        path.unlink()


def oauth_ready() -> bool:
    if not oauth_client_configured():
        return False
    token = load_token()
    return bool((token.get("refresh_token") or "").strip())


def oauth_status() -> Dict[str, Any]:
    token = load_token()
    return {
        "clientConfigured": oauth_client_configured(),
        "ready": oauth_ready(),
        "email": token.get("email"),
        "redirectUri": redirect_uri(),
        "folderName": token.get("folderName"),
        "folderId": token.get("folderId"),
    }


def _credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token = load_token()
    refresh = (token.get("refresh_token") or "").strip()
    if not refresh or not oauth_client_configured():
        return None
    creds = Credentials(
        token=token.get("access_token"),
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id(),
        client_secret=client_secret(),
        scopes=SCOPES,
    )
    if not creds.valid or creds.expired:
        creds.refresh(Request())
        token["access_token"] = creds.token
        token["refresh_token"] = creds.refresh_token or refresh
        token["saved_at"] = int(time.time())
        save_token(token)
    return creds


def oauth_drive_service():
    creds = _credentials()
    if creds is None:
        return None
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def authorization_url(state: str) -> str:
    from google_auth_oauthlib.flow import Flow

    if not oauth_client_configured():
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are not set")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id(),
                "client_secret": client_secret(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri()],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri(),
    )
    url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return url


def exchange_code(code: str) -> Dict[str, Any]:
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": client_id(),
                "client_secret": client_secret(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri()],
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri(),
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    from googleapiclient.discovery import build

    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = service.about().get(fields="user(emailAddress,displayName)").execute()
    user = about.get("user") or {}
    folder_id, folder_name = ensure_backup_folder(service)
    data = {
        "refresh_token": creds.refresh_token,
        "access_token": creds.token,
        "email": user.get("emailAddress"),
        "name": user.get("displayName"),
        "folderId": folder_id,
        "folderName": folder_name,
        "saved_at": int(time.time()),
    }
    if not data["refresh_token"]:
        prev = load_token()
        data["refresh_token"] = prev.get("refresh_token")
    if not data.get("refresh_token"):
        raise RuntimeError("Google did not return a refresh token. Reconnect and allow offline access.")
    save_token(data)
    return data


def ensure_backup_folder(service) -> Tuple[str, str]:
    configured = (os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    if configured:
        try:
            meta = service.files().get(
                fileId=configured,
                fields="id,name,trashed",
                supportsAllDrives=True,
            ).execute()
            if meta and not meta.get("trashed"):
                return meta["id"], meta.get("name") or DEFAULT_FOLDER_NAME
        except Exception as exc:
            print(f"Configured Drive folder not usable with OAuth: {exc}", flush=True)
    q = (
        f"name='{DEFAULT_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false and 'me' in owners"
    )
    res = service.files().list(q=q, spaces="drive", fields="files(id, name)", pageSize=5).execute()
    files = res.get("files") or []
    if files:
        return files[0]["id"], files[0].get("name") or DEFAULT_FOLDER_NAME
    created = service.files().create(
        body={"name": DEFAULT_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"},
        fields="id,name",
    ).execute()
    return created["id"], created.get("name") or DEFAULT_FOLDER_NAME


def oauth_folder_id() -> str:
    token = load_token()
    return (token.get("folderId") or os.environ.get("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
