"""Prefer Bearer over a stale Home Screen cookie in get_current_user."""
from __future__ import annotations

from pathlib import Path

OLD = '''def get_current_user(request: Request):
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
'''

NEW = '''def get_current_user(request: Request):
    candidates = []
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        bearer = auth[7:].strip()
        if bearer:
            candidates.append(bearer)
    cookie = request.cookies.get("neurolab_token") or ""
    if cookie and cookie not in candidates:
        candidates.append(cookie)
    if not candidates:
        raise HTTPException(status_code=401, detail="Not authenticated")
    for token in candidates:
        user_id = _user_id_from_token(token)
        if not user_id:
            continue
        user = _get_user(user_id)
        if user:
            return user
    raise HTTPException(status_code=401, detail="Invalid token")
'''


def patch_auth_bearer_first(root: Path) -> int:
    path = root / "auth.py"
    text = path.read_text(encoding="utf-8")
    if "for token in candidates:" in text and "auth.lower().startswith(\"bearer \")" in text:
        print("already patched: auth bearer first")
        return 0
    if OLD not in text:
        print("error: get_current_user pattern missing", file=__import__("sys").stderr)
        return 1
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched auth bearer first")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(patch_auth_bearer_first(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
