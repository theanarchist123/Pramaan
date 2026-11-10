"""Auth dependencies: a request is authenticated by a JWT *or* an API key."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from urllib.parse import urlparse

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.core.security import decode_access_token, hash_api_key, parse_api_key_prefix
from app.db import get_session
from app.models import ApiKey, User

ALL_SCOPES = {"profiles:read", "profiles:write", "verify:read", "search:read", "webhooks:manage"}


@dataclass
class Principal:
    user: User
    via: str  # "jwt" | "api_key"
    scopes: set[str] = field(default_factory=lambda: set(ALL_SCOPES))
    api_key_id: uuid.UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


SESSION_COOKIE = "pramaan_session"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_allowed(origin: str) -> bool:
    s = get_settings()
    base = urlparse(s.public_base_url)
    allowed = f"{base.scheme}://{base.netloc}"
    if origin == allowed:
        return True
    if s.is_local:
        o = urlparse(origin)
        return o.scheme in ("http", "https") and o.hostname in ("localhost", "127.0.0.1")
    return False


def _csrf_check(request: Request) -> None:
    """A cookie is sent by the browser on ANY request to us, including ones a hostile page triggers. For
    state-changing requests the Origin (or Referer) must be our own site."""
    if request.method in _SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if not origin:
        ref = request.headers.get("referer", "")
        origin = f"{urlparse(ref).scheme}://{urlparse(ref).netloc}" if ref else ""
    if not origin or not _origin_allowed(origin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-site request blocked")


async def get_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    token = x_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    from_cookie = False
    if not token:
        token = request.cookies.get(SESSION_COOKIE)  # the browser session (httpOnly: JavaScript can't read it)
        from_cookie = bool(token)
    if not token:
        raise _unauthorized()

    # API key
    if token.startswith("pk_live_"):
        prefix = parse_api_key_prefix(token)
        row = None
        if prefix:
            row = (
                await session.execute(
                    select(ApiKey).where(
                        ApiKey.prefix == prefix, ApiKey.key_hash == hash_api_key(token)
                    )
                )
            ).scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            raise _unauthorized("Invalid or revoked API key")
        allowed, _ = check_rate_limit(f"key:{row.id}", row.rate_limit_per_min)
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Rate limit exceeded for this API key",
                headers={"Retry-After": "60"},
            )
        owner = await session.get(User, row.owner_id)
        if owner is None:
            raise _unauthorized("API key owner no longer exists")
        row.last_used_at = datetime.now(timezone.utc)
        await session.commit()
        return Principal(owner, "api_key", set(row.scopes), row.id)

    # JWT
    claims = decode_access_token(token)
    if not claims or "purpose" in claims:
        raise _unauthorized("Invalid or expired token")
    if from_cookie:
        _csrf_check(request)
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise _unauthorized("User no longer exists")
    if user.tokens_valid_after is not None and float(claims.get("iatf", 0)) < user.tokens_valid_after.timestamp():
        raise _unauthorized("Session was signed out")
    return Principal(user, "jwt")


async def get_optional_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal | None:
    if not x_api_key and not authorization and SESSION_COOKIE not in request.cookies:
        return None
    try:
        return await get_principal(request, session, authorization, x_api_key)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return None
        raise


def require_scope(scope: str):
    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if scope not in principal.scopes:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"API key lacks scope '{scope}'")
        return principal

    return _dep


def require_verified_email(principal: Principal) -> None:
    """Public listing needs proof the applicant controls the email on the account (admins are exempt)."""
    if get_settings().require_email_verification and not principal.is_admin and principal.user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your email address first")


async def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_admin or principal.via != "jwt":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return principal
