"""Sign-in for the separate staff console (apps/admin).

Staff sessions are deliberately different from member sessions: their own cookie (SameSite=Strict, `__Host-` prefixed in
production), a short lifetime, valid only on /v1/admin and /v1/auth/mfa, and only for people who actually hold a staff role.
A member who is also staff signs in here separately; one session never serves the other site.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.rbac import staff_roles
from app.core.ratelimit import ip_limit, login_failed, login_locked, login_ok
from app.core.security import create_access_token, verify_password
from app.db import get_session
from app.deps import Principal, admin_cookie_name, get_principal
from app.models import User
from app.schemas import LoginIn, UserOut
from datetime import datetime, timedelta, timezone

from pydantic import Field

router = APIRouter(prefix="/v1/admin/auth", tags=["staff-auth"])


class AdminLoginIn(LoginIn):
    """Password plus, for anyone with an authenticator enrolled, a 6-digit code or one single-use recovery code."""

    code: str = Field(default="", max_length=16)


async def _second_factor_ok(session: AsyncSession, user: User, code: str) -> bool:
    from app.core import totp
    from app.models import MfaRecoveryCode

    code = code.strip().replace(" ", "")
    secret = totp.unseal(user.totp_secret_enc or "")
    if secret is not None and totp.verify(secret, code):
        return True
    row = (await session.execute(select(MfaRecoveryCode).where(
        MfaRecoveryCode.user_id == user.id, MfaRecoveryCode.code_hash == totp.hash_recovery_code(code),
        MfaRecoveryCode.used_at.is_(None)))).scalar_one_or_none()
    if row is None:
        return False
    row.used_at = datetime.now(timezone.utc)  # a recovery code works exactly once
    return True


@router.post("/login", dependencies=[Depends(ip_limit("admin-login", 10))])
async def admin_login(body: AdminLoginIn, response: Response, session: AsyncSession = Depends(get_session)):
    email = body.email.lower().strip()
    key = f"admin:{email}"
    if await login_locked(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts - try again in 15 minutes")
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    # One message for every failure, so the form cannot be used to discover who is staff.
    if user is None or not verify_password(body.password, user.password_hash) or not (
        user.role == "admin" or await staff_roles(session, user.id)
    ):
        await login_failed(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if user.mfa_enrolled_at is not None:
        # The password alone is never enough once an authenticator exists. Asking for the code is not a failure and does not
        # count against the lockout; a wrong code does.
        if not body.code.strip():
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "mfa_code_required", "message": "Enter the code from your authenticator app"})
        if not await _second_factor_ok(session, user, body.code):
            await login_failed(key)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email, password or code")
        # Having just proved presence, sensitive actions are unlocked for the usual step-up window.
        user.stepup_until = datetime.now(timezone.utc) + timedelta(minutes=get_settings().stepup_minutes)
        await session.commit()
    await login_ok(key)
    s = get_settings()
    minutes = s.admin_session_minutes
    response.set_cookie(
        admin_cookie_name(), create_access_token(str(user.id), user.role, minutes), max_age=minutes * 60, httponly=True,
        secure=not s.is_local, samesite="strict", path="/",
    )
    return {"user": UserOut.model_validate(user), "mfa_enrolled": user.mfa_enrolled_at is not None, "mfa_required": s.staff_mfa_required, "session_minutes": minutes}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(principal: Principal = Depends(get_principal)):
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(admin_cookie_name(), path="/")
    return response
