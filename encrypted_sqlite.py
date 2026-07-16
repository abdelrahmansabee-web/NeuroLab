"""Encrypted SQLite wrapper using SQLCipher (or plain sqlite3 as fallback).

The application uses this module as a drop-in replacement for sqlite3.
When SQLCipher is available, every connection is opened with PRAGMA key,
encrypting the database at rest.  If SQLCipher is unavailable we fall back
 to the standard library sqlite3 so local development still works.
"""
import os
import re
import sqlite3 as _stdlib_sqlite3
from pathlib import Path
from typing import Optional

try:
    from sqlcipher3 import dbapi2 as _sqlcipher3

    SQLCIPHER_AVAILABLE = True
except Exception:  # pragma: no cover
    _sqlcipher3 = _stdlib_sqlite3
    SQLCIPHER_AVAILABLE = False

Row = _stdlib_sqlite3.Row


def get_db_key() -> str:
    """Return the database encryption key.

    Prefer a dedicated DB_ENCRYPTION_KEY env variable; otherwise fall back to
    JWT_SECRET so the key is already required for the app to start.  Never use a
    hard-coded default key.
    """
    key = os.environ.get("DB_ENCRYPTION_KEY")
    if not key:
        key = os.environ.get("JWT_SECRET")
    if not key:
        raise RuntimeError(
            "DB_ENCRYPTION_KEY or JWT_SECRET environment variable is required."
        )
    # Remove leading/trailing whitespace and a common mistake of wrapping the key in quotes.
    return key.strip().strip('"').strip("'")


def _sanitize_key_for_pragma(key: str) -> str:
    """Escape single quotes in the key so PRAGMA key='...' is safe."""
    return key.replace("'", "''")


def connect(db_path: Optional[str | Path] = None, key: Optional[str] = None):
    """Open a SQLCipher-encrypted connection (or plain sqlite3 fallback).

    If *key* is None, the key is read from the environment.  Callers that need
    a plain (unencrypted) connection for migration should use connect_plain().
    """
    if key is None:
        key = get_db_key()
    if not SQLCIPHER_AVAILABLE:
        return _stdlib_sqlite3.connect(str(db_path))
    conn = _sqlcipher3.connect(str(db_path))
    conn.execute(f"PRAGMA key = '{_sanitize_key_for_pragma(key)}'")
    return conn


def connect_plain(db_path: Optional[str | Path] = None):
    """Open a connection without setting the encryption key.

    Useful for migration: SQLCipher can read plain SQLite files when no key is
    supplied.  Falls back to stdlib sqlite3 if SQLCipher is not installed.
    """
    if not SQLCIPHER_AVAILABLE:
        return _stdlib_sqlite3.connect(str(db_path))
    return _sqlcipher3.connect(str(db_path))


def is_plain_sqlite(db_path: Path) -> bool:
    """Return True if the file is a plain, unencrypted SQLite database."""
    if not db_path.exists():
        return False
    try:
        with connect_plain(db_path) as conn:
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        return True
    except Exception:
        return False


def encrypt_db_inplace(db_path: Path, key: Optional[str] = None) -> None:
    """Encrypt a plain SQLite database in place using SQLCipher.

    Uses the SQLCipher ``sqlcipher_export`` pragma.  A temporary backup is kept
    until the operation succeeds; on failure the original file is left untouched.
    """
    db_path = Path(db_path)
    if key is None:
        key = get_db_key()
    if not SQLCIPHER_AVAILABLE:
        raise RuntimeError(
            "SQLCipher is not installed; cannot encrypt database."
        )
    if not db_path.exists():
        # Create a new encrypted database.
        with connect(db_path, key) as conn:
            conn.execute("SELECT 1")
        return

    temp_path = db_path.with_suffix(db_path.suffix + ".tmp_enc")
    backup_path = db_path.with_suffix(db_path.suffix + ".plain_backup")
    try:
        # Open the existing plain database with SQLCipher (no key).
        with connect_plain(db_path) as conn:
            conn.execute(
                f"ATTACH DATABASE '{temp_path}' AS encrypted KEY '{_sanitize_key_for_pragma(key)}'"
            )
            conn.execute("SELECT sqlcipher_export('encrypted')")
            conn.execute("DETACH DATABASE encrypted")
        # Replace original with encrypted copy.
        db_path.rename(backup_path)
        temp_path.rename(db_path)
        backup_path.unlink(missing_ok=True)
    except Exception:
        # Clean up temporary files on failure.
        if temp_path.exists():
            temp_path.unlink()
        if backup_path.exists() and db_path.exists():
            backup_path.unlink()
        raise


def ensure_encrypted(db_path: Path) -> None:
    """If the database file is plain, encrypt it in place."""
    db_path = Path(db_path)
    if is_plain_sqlite(db_path):
        encrypt_db_inplace(db_path)


# Keep the same module-level exceptions as the stdlib sqlite3 module for
# compatibility.
Error = _stdlib_sqlite3.Error
IntegrityError = _stdlib_sqlite3.IntegrityError
OperationalError = _stdlib_sqlite3.OperationalError
DatabaseError = _stdlib_sqlite3.DatabaseError


def _migrate_module_imports():
    """Not used at runtime; documents which sqlite3 attributes are re-exported."""
    pass
