"""Return the session JWT from GET /auth/me so the Home Screen icon can send Bearer."""
from __future__ import annotations

from pathlib import Path

OLD = '''@router.get("/me")
async def auth_me(user: dict = Depends(get_current_user)):
    email = user.get("email")
    return {
        "id": user["id"],
        "email": email,'''

NEW = '''@router.get("/me")
async def auth_me(request: Request, user: dict = Depends(get_current_user)):
    email = user.get("email")
    token = request.cookies.get("neurolab_token") or ""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip() or token
    return {
        "id": user["id"],
        "email": email,
        "token": token,'''


def patch_auth_me_token(root: Path) -> int:
    path = root / "auth.py"
    text = path.read_text(encoding="utf-8")
    if '"token": token,' in text and "async def auth_me(request: Request" in text:
        print("already patched: auth_me token")
        return 0
    if OLD not in text:
        print("error: auth_me pattern missing", file=__import__("sys").stderr)
        return 1
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("patched auth_me token")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(patch_auth_me_token(Path(sys.argv[1] if len(sys.argv) > 1 else ".")))
