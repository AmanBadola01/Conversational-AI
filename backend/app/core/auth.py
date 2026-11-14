"""Account authentication: salted password hashing and signed bearer tokens.

Uses only the Python standard library so no extra install is required.
Passwords use PBKDF2-HMAC-SHA256. Tokens are compact HMAC-SHA256 signed
JWT-shaped values (header.payload.signature) with a 7-day expiry.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.core.database import get_db

TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PBKDF2_ITERATIONS = 260_000

_bearer = HTTPBearer(auto_error=False)


_PROCESS_SECRET = secrets.token_urlsafe(48)

def _secret() -> bytes:
    raw = os.getenv("AUTH_SECRET", "").strip()
    if not raw or raw.lower().startswith("your_") or raw.endswith("_here"):
        raw = _PROCESS_SECRET
    return raw.encode("utf-8")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    pad = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + pad).encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_b64, digest_b64 = stored.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        expected = _b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt_b64), int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_access_token(user_id: str) -> str:
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(
        json.dumps({"sub": user_id, "iat": now, "exp": now + TOKEN_TTL_SECONDS}, separators=(",", ":")).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64encode(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> str | None:
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64encode(hmac.new(_secret(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        data = json.loads(_b64decode(payload))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        subject = data.get("sub")
        return str(subject) if subject else None
    except Exception:
        return None


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    """FastAPI dependency: resolve the signed-in user or reject with 401."""
    from backend.app.models.db_models import User

    token = credentials.credentials if credentials else request.cookies.get("continuum_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(token.strip())
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_owned_conversation(db: Session, conversation_id: str, user):
    """Return the conversation only when it belongs to `user`; otherwise 404.

    A 404 (not 403) is returned for other accounts so conversation ids
    cannot be probed across accounts.
    """
    from backend.app.models.db_models import Conversation

    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user.id)
        .first()
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return conv
