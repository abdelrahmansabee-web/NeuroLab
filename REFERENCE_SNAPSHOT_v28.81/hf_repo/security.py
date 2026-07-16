import os
import re
import sqlite3
import time
import base64
import json
from pathlib import Path
from typing import Optional, Any

from fastapi import Request
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


def _derive_key(secret: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"neurolab_static_salt_v1",
        iterations=200000,
        backend=default_backend(),
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def get_fernet(secret: str) -> Fernet:
    return Fernet(_derive_key(secret))


def password_policy(password: str) -> tuple[bool, str]:
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain a digit"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]/\\`~]", password):
        return False, "Password must contain a special character"
    return True, "OK"


class RateLimiter:
    def __init__(self, limit: int = 5, window: int = 60):
        self.limit = limit
        self.window = window
        self._store = {}

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        entries = self._store.get(key, [])
        entries = [t for t in entries if now - t < self.window]
        if len(entries) >= self.limit:
            self._store[key] = entries
            return False
        entries.append(now)
        self._store[key] = entries
        return True


def get_client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def init_audit_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER,
                email TEXT,
                ip TEXT,
                details TEXT,
                success INTEGER NOT NULL
            )
            """
        )
        conn.commit()


def log_audit(db_path: Path, action: str, user_id: Optional[int] = None, email: Optional[str] = None, ip: Optional[str] = None, details: str = "", success: bool = True):
    try:
        init_audit_db(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO audit_logs (timestamp, action, user_id, email, ip, details, success) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (time.time(), action, user_id, email, ip, details, int(success)),
            )
            conn.commit()
    except Exception as exc:
        print("Audit log failed:", exc, flush=True)


def encrypt_json(data: Any, secret: str) -> bytes:
    f = get_fernet(secret)
    return f.encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def decrypt_json(encrypted: bytes, secret: str) -> Any:
    f = get_fernet(secret)
    return json.loads(f.decrypt(encrypted).decode("utf-8"))


def encrypt_json_to_str(data: Any, secret: str) -> str:
    return "enc:" + encrypt_json(data, secret).decode("utf-8")


def decrypt_json_from_str(text: str, secret: str) -> Any:
    if isinstance(text, str) and text.startswith("enc:"):
        return decrypt_json(text[4:].encode("utf-8"), secret)
    return json.loads(text)
