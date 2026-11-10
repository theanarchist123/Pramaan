import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ratelimit import ip_limit, login_failed, login_locked, login_ok
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_session
from app.deps import SESSION_COOKIE, Principal, get_principal
from app.models import EmailOtp, User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut

log = logging.getLogger("pramaan.auth")
router = APIRouter(prefix="/v1/auth", tags=["auth"])

SESSION_MINUTES = 60 * 12
OTP_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_MAX_PER_HOUR = 5


def _set_session_cookie(response: Response, token: str) -> None:
    """The browser session lives in an httpOnly cookie: JavaScript (and so any XSS) can never read it."""
    s = get_settings()
    samesite = s.cookie_samesite if s.cookie_samesite != "auto" else ("lax" if s.is_local else "none")
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MINUTES * 60, httponly=True,
        secure=not s.is_local or samesite == "none", samesite=samesite, path="/",
    )


def _token_out(user: User, response: Response) -> TokenOut:
    token = create_access_token(str(user.id), user.role, SESSION_MINUTES)
    _set_session_cookie(response, token)
    # The token is also returned for API clients and SDKs; the web app ignores it and uses the cookie.
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(ip_limit("register", 10))])
async def register(body: RegisterIn, response: Response, session: AsyncSession = Depends(get_session)):
    email = body.email.lower().strip()
    exists = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(
        email=email, name=body.name, role=body.role, password_hash=hash_password(body.password)
    )
    session.add(user)
    await session.commit()
    return _token_out(user, response)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(ip_limit("login", 20))])
async def login(body: LoginIn, response: Response, session: AsyncSession = Depends(get_session)):
    email = body.email.lower().strip()
    if await login_locked(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts - try again in 15 minutes")
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        await login_failed(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    await login_ok(email)
    return _token_out(user, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Ends the session and revokes every token issued so far (signs out on all devices)."""
    if principal.via == "jwt":
        user = await session.get(User, principal.user.id)
        user.tokens_valid_after = datetime.now(timezone.utc)
        await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me", response_model=UserOut)
async def me(principal: Principal = Depends(get_principal)):
    return principal.user


# --------------------------------------------------------------------------- email one-time code
class OtpVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


def _otp_hash(user_id, code: str) -> str:
    return hashlib.sha256(f"{get_settings().jwt_secret}|{user_id}|{code}".encode()).hexdigest()


@router.post("/otp/request", dependencies=[Depends(ip_limit("otp", 10))])
async def otp_request(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    """Email a 6-digit code to the account's address; proves the applicant controls it."""
    user = principal.user
    if user.email_verified_at is not None:
        return {"sent": False, "already_verified": True}
    recent = (await session.execute(
        select(func.count()).select_from(EmailOtp)
        .where(EmailOtp.user_id == user.id, EmailOtp.created_at > datetime.now(timezone.utc) - timedelta(hours=1))
    )).scalar_one()
    if recent >= OTP_MAX_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested - try again later")

    s = get_settings()
    if not s.smtp_host and not s.is_local:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email delivery is not configured on this server")

    code = f"{secrets.randbelow(10**6):06d}"
    session.add(EmailOtp(user_id=user.id, code_hash=_otp_hash(user.id, code),
                         expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_MINUTES)))
    await session.commit()

    out: dict = {"sent": True, "expires_in_minutes": OTP_MINUTES}
    if s.smtp_host:
        import asyncio

        from app.services.outreach import _smtp_send

        try:
            await asyncio.to_thread(
                _smtp_send, user.email, "Your Pramaan verification code",
                f"Your code is {code}. It expires in {OTP_MINUTES} minutes.\n\nIf you did not ask for it, ignore this email.",
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("OTP email failed: %s", type(exc).__name__)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not send the email right now") from exc
    else:  # local development without SMTP: show it where the developer can find it
        log.warning("DEV ONLY - email code for %s: %s", user.email, code)
        out["dev_code"] = code
    return out


@router.post("/otp/verify", dependencies=[Depends(ip_limit("otp-verify", 20))])
async def otp_verify(
    body: OtpVerifyIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)
):
    user = await session.get(User, principal.user.id)
    if user.email_verified_at is not None:
        return {"verified": True}
    otp = (await session.execute(
        select(EmailOtp).where(EmailOtp.user_id == user.id, EmailOtp.used_at.is_(None))
        .order_by(EmailOtp.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if otp is None or otp.expires_at < datetime.now(timezone.utc) or otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code has expired - request a new one")
    otp.attempts += 1
    if not hmac.compare_digest(otp.code_hash, _otp_hash(user.id, body.code)):
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code")
    otp.used_at = user.email_verified_at = datetime.now(timezone.utc)
    await session.commit()
    return {"verified": True}
