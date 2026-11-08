"""Auth dependencies: a request is authenticated by a JWT *or* an API key."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def get_principal(
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    token = x_api_key
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
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
    user = await session.get(User, uuid.UUID(claims["sub"]))
    if user is None:
        raise _unauthorized("User no longer exists")
    return Principal(user, "jwt")


async def get_optional_principal(
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal | None:
    if not x_api_key and not authorization:
        return None
    try:
        return await get_principal(session, authorization, x_api_key)
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


async def require_admin(principal: Principal = Depends(get_principal)) -> Principal:
    if not principal.is_admin or principal.via != "jwt":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return principal
