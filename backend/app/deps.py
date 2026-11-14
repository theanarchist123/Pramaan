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
from app.core.security import TEST_KEY_SCOPES, decode_access_token, hash_api_key, parse_api_key_prefix
from app.db import get_session
from app.models import ApiKey, User

OAUTH_PATHS = ("/v1/profiles", "/v1/onboarding", "/v1/search", "/v1/verify", "/v1/auth/me", "/v1/badges")
ALL_SCOPES = {"profiles:read", "profiles:write", "verify:read", "search:read", "webhooks:manage"}


@dataclass
class Principal:
    user: User
    via: str  # "jwt" | "api_key"
    scopes: set[str] = field(default_factory=lambda: set(ALL_SCOPES))
    api_key_id: uuid.UUID | None = None

    @property
    def is_admin(self) -> bool:
        # An app a member authorised (OAuth) never acts as staff, whoever the member is.
        return self.user.role == "admin" and self.via != "oauth"


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


SESSION_COOKIE = "pramaan_session"
ADMIN_COOKIE_LOCAL = "pramaan_admin"
ADMIN_COOKIE_PROD = "__Host-pramaan_admin"  # __Host-: Secure, path=/, no Domain: cannot be set or read by sibling subdomains
ADMIN_PATHS = ("/v1/admin", "/v1/auth/mfa")


def admin_cookie_name() -> str:
    return ADMIN_COOKIE_LOCAL if get_settings().is_local else ADMIN_COOKIE_PROD


def is_admin_path(path: str) -> bool:
    return path.startswith(ADMIN_PATHS)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _origin_allowed(origin: str, admin: bool = False) -> bool:
    s = get_settings()
    base = urlparse(s.admin_base_url if admin and s.admin_base_url else s.public_base_url)
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
    if not origin or not _origin_allowed(origin, admin=is_admin_path(request.url.path)):
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
        # Two browser sessions that never cross: staff endpoints read ONLY the admin cookie (set by the separate admin
        # app's login), everything else reads ONLY the member cookie. A stolen member session is useless on /v1/admin.
        token = request.cookies.get(admin_cookie_name() if is_admin_path(request.url.path) else SESSION_COOKIE)
        from_cookie = bool(token)
    if not token:
        raise _unauthorized()

    # API key
    if token.startswith(("pk_live_", "pk_test_")):
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
        allowed, remaining = await check_rate_limit(f"key:{row.id}", row.rate_limit_per_min)
        request.state.rate_limit = (row.rate_limit_per_min, remaining)
        try:
            from app.services import usage

            await usage.record(session, row.id, throttled=not allowed)
            if not allowed:
                await session.commit()  # the 429 below must still be counted
        except Exception:  # noqa: BLE001 - counting must never turn a good request into an error
            await session.rollback()
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
        scopes = set(row.scopes)
        if token.startswith("pk_test_"):
            scopes &= TEST_KEY_SCOPES  # belt and braces: a test key never writes, whatever its row says
        return Principal(owner, "api_key", scopes, row.id)

    # OAuth access token (a third-party app acting for a member, within the scopes the member approved)
    if token.startswith("pat_"):
        from app.services import oauth

        found = await oauth.principal_for_token(session, token)
        if found is None:
            raise _unauthorized("Invalid, expired or revoked token")
        tok, owner = found
        # An app may only reach the member-data endpoints that check scopes. Sign-in, MFA, identity and account endpoints are never open to it.
        if not request.url.path.startswith(OAUTH_PATHS):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "This endpoint is not available to apps")
        allowed, remaining = await check_rate_limit(f"oauth:{tok.id}", 120)
        request.state.rate_limit = (120, remaining)
        if not allowed:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded", headers={"Retry-After": "60"})
        return Principal(owner, "oauth", set(tok.scopes))

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


async def require_verified_email(principal: Principal) -> None:
    """Public listing needs proof the applicant controls the email on the account (admins are exempt).
    The rule is a GOVERNED setting: switched only by a second person's approval, with history."""
    from app.services import governed
    from app.services.guests import is_guest_email

    if is_guest_email(principal.user.email):
        # A guest has no real address to verify, so it can never be listed, verified or certified (invariant I-5): create the account first.
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Create your account first to continue")
    if await governed.get("require_email_verification") and not principal.is_admin and principal.user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Verify your email address first")


async def require_admin(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)) -> Principal:
    """Any staff member: the legacy admin flag or at least one staff role. Specific actions use require_permission()."""
    from app.core.rbac import staff_roles

    if principal.via != "jwt":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    if principal.is_admin or await staff_roles(session, principal.user.id):
        _require_mfa(principal)
        return principal
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")


def _require_mfa(principal: Principal) -> None:
    """Staff without an enrolled authenticator app get nothing but the enrolment endpoints."""
    if get_settings().staff_mfa_required and principal.user.mfa_enrolled_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "mfa_required", "message": "Set up your authenticator app first"})


def require_stepup(principal: Principal) -> None:
    """Sensitive staff actions need an MFA code entered in the last few minutes (POST /v1/auth/mfa/stepup)."""
    if not get_settings().staff_mfa_required:
        return
    until = principal.user.stepup_until
    if until is None or until < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={"code": "stepup_required", "message": "Confirm with your authenticator code"})


def require_permission(permission: str):
    """The caller must be a signed-in staff member whose roles grant `permission` (the legacy admin has them all)."""

    async def _dep(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)) -> Principal:
        from app.core.rbac import permissions_for_user

        if principal.via != "jwt" or permission not in await permissions_for_user(session, principal.user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Your role does not allow this ({permission})")
        _require_mfa(principal)
        return principal

    return _dep
