"""Time-based one-time passwords (RFC 6238: HMAC-SHA1, 30 s steps, 6 digits), standard library only, plus encryption at
rest for the shared secret. Compatible with Google Authenticator, Authy, 1Password and the like."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

STEP = 30
DIGITS = 6


def new_secret() -> str:
    """20 random bytes, base32 (the format authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8))
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return f"{code:0{DIGITS}d}"


def code_at(secret_b32: str, at: float | None = None) -> str:
    return _hotp(secret_b32, int((time.time() if at is None else at) // STEP))


def verify(secret_b32: str, code: str, *, at: float | None = None, window: int = 1) -> bool:
    """Accept the current step and `window` steps either side (clock drift). Constant-time compare."""
    if not code or len(code) != DIGITS or not code.isdigit():
        return False
    now = int((time.time() if at is None else at) // STEP)
    return any(hmac.compare_digest(_hotp(secret_b32, now + d), code) for d in range(-window, window + 1))


def otpauth_uri(secret_b32: str, account: str, issuer: str = "Pramaan") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret_b32}&issuer={quote(issuer)}&digits={DIGITS}&period={STEP}"


def _fernet() -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("totp|" + get_settings().jwt_secret).encode()).digest()))


def seal(secret_b32: str) -> str:
    return _fernet().encrypt(secret_b32.encode()).decode()


def unseal(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
