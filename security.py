import os
import re
import time
import base64
import json
from pathlib import Path
from typing import Optional, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

import encrypted_sqlite as sqlite3


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
    # Cloudflare passes the original visitor IP in CF-Connecting-IP.
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.split(",")[0].strip()
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


class WAFMiddleware(BaseHTTPMiddleware):
    """Lightweight application-level WAF / reverse-proxy guard.

    - Honors Cloudflare's CF-Connecting-IP header for real client IP.
    - Blocks IP addresses in an optional blocklist (env WAF_BLOCKLIST).
    - Rejects requests whose path/query match common SQLi / XSS probes.
    - Enforces a max request body size via Content-Length.
    - Logs blocked requests to the audit DB.

    This does not replace a real network WAF, but it adds a second layer of
    defence and records attempts.  For production traffic, put Cloudflare in
    front and enable Cloudflare's WAF / Managed Rules.
    """

    # Suspicious patterns tested against path + query string.
    _PATTERNS = [
        # SQL injection probes
        re.compile(r"(\b(union|select|insert|update|delete|drop|alter|create|exec|execute|grant|revoke)\b.*){2,}", re.IGNORECASE),
        re.compile(r"['\";]+\s*\b(or|and)\b\s*['\"]?\d+\s*=?\s*['\"]?\d", re.IGNORECASE),
        re.compile(r"--|#\s|/\*|\*/", re.IGNORECASE),
        # XSS / script injection probes
        re.compile(r"<\s*script|javascript\s*:|on\w+\s*=", re.IGNORECASE),
        re.compile(r"\b(eval|expression)\s*\(", re.IGNORECASE),
        # path traversal and file inclusion
        re.compile(r"\.\./|\.\.\\|%2e%2e", re.IGNORECASE),
    ]

    def __init__(self, app, max_content_length_bytes: int = 50 * 1024 * 1024, audit_db_path: Optional[Path] = None):
        super().__init__(app)
        self.max_content_length_bytes = max_content_length_bytes
        self.audit_db_path = audit_db_path
        self.blocklist: set[str] = set()
        self._load_blocklist()

    def _load_blocklist(self) -> None:
        blocklist_path = os.environ.get("WAF_BLOCKLIST")
        if not blocklist_path:
            return
        path = Path(blocklist_path)
        if not path.exists():
            return
        try:
            self.blocklist = {
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("#")
            }
        except Exception as exc:
            print(f"WAF blocklist load failed: {exc}", flush=True)

    def _log_block(self, ip: str, details: str) -> None:
        if not self.audit_db_path:
            return
        try:
            log_audit(self.audit_db_path, "waf_block", ip=ip, details=details, success=False)
        except Exception:
            pass

    async def dispatch(self, request: Request, call_next):
        ip = get_client_ip(request)

        if ip in self.blocklist:
            self._log_block(ip, "IP in blocklist")
            return Response("Forbidden", status_code=403)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.max_content_length_bytes:
                    self._log_block(ip, "Content-Length too large")
                    return Response("Payload Too Large", status_code=413)
            except ValueError:
                pass

        text = f"{request.url.path}?{request.url.query}"
        for pattern in self._PATTERNS:
            if pattern.search(text):
                self._log_block(ip, f"Pattern match: {pattern.pattern}")
                return Response("Forbidden", status_code=403)

        return await call_next(request)


