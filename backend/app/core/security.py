"""Passwords, JWTs and API keys. Stdlib scrypt keeps the dependency list small."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt${}${}".format(
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **_SCRYPT)
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, role: str, minutes: int = 60 * 12) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "role": role, "iat": now, "iatf": time.time(), "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def create_scoped_token(subject: str, purpose: str, minutes: int) -> str:
    """Short-lived single-purpose token (e.g. delegate one-tap approval links)."""
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "purpose": purpose, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm="HS256")


def decode_scoped_token(token: str, purpose: str) -> str | None:
    claims = decode_access_token(token)
    if claims and claims.get("purpose") == purpose:
        return claims["sub"]
    return None


# --- API keys: shown once as  pk_live_<prefix>_<secret>; only a SHA-256 is stored ---
API_KEY_SCOPES = {"profiles:read", "profiles:write", "verify:read", "search:read", "webhooks:manage"}


# A test key can only read: it can never change anything, so it is safe to paste into a CI job or a demo (API-01).
TEST_KEY_SCOPES = {"profiles:read", "verify:read", "search:read"}


def generate_api_key(mode: str = "live") -> tuple[str, str, str]:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    full = f"pk_{'test' if mode == 'test' else 'live'}_{prefix}_{secret}"
    return full, prefix, hash_api_key(full)


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode()).hexdigest()


def parse_api_key_prefix(full_key: str) -> str | None:
    parts = full_key.split("_", 3)
    if len(parts) == 4 and parts[0] == "pk" and parts[1] in ("live", "test"):
        return parts[2]
    return None
