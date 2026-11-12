"""OAuth 2.0 authorization code + PKCE (API-02), for third-party apps acting on a member's behalf.

Rules, all enforced in code:
* Public clients only; PKCE with S256 is mandatory (RFC 7636). "plain" is refused.
* A redirect URI is registered up front and matched EXACTLY. https only, except loopback (127.0.0.1, localhost, [::1]) for native apps (RFC 8252).
  No user-info, no fragment. An unknown client or redirect is shown as an error to the person, never redirected to.
* Codes are single use and last 5 minutes. Replaying a code revokes every token it produced.
* Access tokens last 1 hour, refresh tokens 30 days, and a refresh token works once (rotation). Reusing a spent one revokes the whole family.
* Only hashes of codes and tokens are stored. A token carries only scopes the member approved, and never webhooks:manage or staff power.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OAuthClient, OAuthCode, OAuthToken, User

OAUTH_SCOPES = {"verify:read", "search:read", "profiles:read", "profiles:write"}
CODE_TTL = timedelta(minutes=5)
ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
LOOPBACK = {"127.0.0.1", "localhost", "[::1]", "::1"}
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


class OAuthError(Exception):
    def __init__(self, error: str, description: str = "", status: int = 400):
        self.error, self.description, self.status = error, description, status


def now() -> datetime:
    return datetime.now(timezone.utc)


def h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def valid_redirect(uri: str) -> bool:
    if not isinstance(uri, str) or len(uri) > 500:
        return False
    u = urlparse(uri)
    if u.fragment or u.username or u.password or not u.hostname:
        return False
    if u.scheme == "https":
        return True
    return u.scheme == "http" and u.hostname.lower() in LOOPBACK


def parse_scopes(scope: str) -> list[str]:
    wanted = list(dict.fromkeys(scope.split()))
    if not wanted:
        raise OAuthError("invalid_scope", "Ask for at least one scope")
    bad = [s for s in wanted if s not in OAUTH_SCOPES]
    if bad:
        raise OAuthError("invalid_scope", f"Unknown or not available to apps: {', '.join(sorted(bad))}")
    return wanted


async def get_client(session: AsyncSession, client_id: str) -> OAuthClient:
    c = (await session.execute(select(OAuthClient).where(OAuthClient.client_id == client_id))).scalar_one_or_none()
    if c is None or c.revoked_at is not None:
        raise OAuthError("invalid_client", "Unknown app")
    return c


def check_request(client: OAuthClient, redirect_uri: str, challenge: str, method: str) -> None:
    if redirect_uri not in client.redirect_uris:  # exact match only
        raise OAuthError("invalid_request", "redirect_uri is not registered for this app")
    if method != "S256" or not CHALLENGE_RE.match(challenge or ""):
        raise OAuthError("invalid_request", "PKCE with code_challenge_method=S256 is required")


def redirect_with(redirect_uri: str, params: dict) -> str:
    sep = "&" if "?" in redirect_uri else "?"
    return redirect_uri + sep + urlencode({k: v for k, v in params.items() if v is not None})


async def issue_code(session: AsyncSession, client: OAuthClient, user: User, scopes: list[str], redirect_uri: str, challenge: str) -> str:
    code = secrets.token_urlsafe(32)
    session.add(OAuthCode(code_hash=h(code), client_id=client.client_id, user_id=user.id, scopes=scopes, redirect_uri=redirect_uri,
                          code_challenge=challenge, expires_at=now() + CODE_TTL))
    await session.commit()
    return code


def _pair(session: AsyncSession, family: str, client_id: str, user_id: uuid.UUID, scopes: list[str]) -> tuple[dict, OAuthToken]:
    access, refresh = "pat_" + secrets.token_urlsafe(32), "prt_" + secrets.token_urlsafe(32)
    row = OAuthToken(family=family, access_hash=h(access), refresh_hash=h(refresh), client_id=client_id, user_id=user_id, scopes=scopes,
                     access_expires_at=now() + ACCESS_TTL, refresh_expires_at=now() + REFRESH_TTL)
    session.add(row)
    body = {"access_token": access, "token_type": "Bearer", "expires_in": int(ACCESS_TTL.total_seconds()),
            "refresh_token": refresh, "scope": " ".join(scopes)}
    return body, row


async def revoke_family(session: AsyncSession, family: str) -> None:
    await session.execute(update(OAuthToken).where(OAuthToken.family == family, OAuthToken.revoked_at.is_(None)).values(revoked_at=now()))


async def exchange_code(session: AsyncSession, client_id: str, code: str, redirect_uri: str, verifier: str) -> dict:
    await get_client(session, client_id)
    ch = h(code)
    row = (await session.execute(select(OAuthCode).where(OAuthCode.code_hash == ch).with_for_update())).scalar_one_or_none()
    if row is None or row.client_id != client_id:
        raise OAuthError("invalid_grant", "That code is not valid")
    if row.used_at is not None:
        await revoke_family(session, ch)  # a replayed code means it leaked: undo everything it made
        await session.commit()
        raise OAuthError("invalid_grant", "That code was already used")
    if row.expires_at < now() or row.redirect_uri != redirect_uri:
        raise OAuthError("invalid_grant", "That code is not valid")
    expected = base64.urlsafe_b64encode(hashlib.sha256((verifier or "").encode()).digest()).rstrip(b"=").decode()
    if not secrets.compare_digest(expected, row.code_challenge):
        raise OAuthError("invalid_grant", "The code verifier does not match")
    row.used_at = now()
    body, _ = _pair(session, ch, client_id, row.user_id, list(row.scopes))
    await session.commit()
    return body


async def refresh(session: AsyncSession, client_id: str, refresh_token: str) -> dict:
    await get_client(session, client_id)
    row = (await session.execute(select(OAuthToken).where(OAuthToken.refresh_hash == h(refresh_token or "")).with_for_update())).scalar_one_or_none()
    if row is None or row.client_id != client_id:
        raise OAuthError("invalid_grant", "That refresh token is not valid")
    if row.rotated_at is not None or row.revoked_at is not None:
        await revoke_family(session, row.family)  # a spent refresh token was presented again: assume theft
        await session.commit()
        raise OAuthError("invalid_grant", "That refresh token was already used")
    if row.refresh_expires_at < now():
        raise OAuthError("invalid_grant", "That refresh token has expired")
    row.rotated_at = row.revoked_at = now()
    body, _ = _pair(session, row.family, client_id, row.user_id, list(row.scopes))
    await session.commit()
    return body


async def revoke_token(session: AsyncSession, token: str) -> None:
    """RFC 7009: anything we do not recognise is silently fine."""
    th = h(token or "")
    row = (await session.execute(select(OAuthToken).where((OAuthToken.access_hash == th) | (OAuthToken.refresh_hash == th)))).scalar_one_or_none()
    if row is not None:
        await revoke_family(session, row.family)
        await session.commit()


async def principal_for_token(session: AsyncSession, token: str):
    row = (await session.execute(select(OAuthToken).where(OAuthToken.access_hash == h(token)))).scalar_one_or_none()
    if row is None or row.revoked_at is not None or row.access_expires_at < now():
        return None
    client = (await session.execute(select(OAuthClient).where(OAuthClient.client_id == row.client_id))).scalar_one_or_none()
    if client is None or client.revoked_at is not None:
        return None
    user = await session.get(User, row.user_id)
    return (row, user) if user is not None else None
