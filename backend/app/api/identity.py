"""Identity binding endpoints (TRU-04): the owner of a profile shows they control an institutional email or a page on an institution's site."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app.config import get_settings
from app.core.ratelimit import ip_limit
from app.db import get_session
from app.deps import Principal, get_principal
from app.models import IdentityBinding, Profile
from app.services import identity, mailer

log = logging.getLogger("pramaan.identity")
router = APIRouter(prefix="/v1/profiles", tags=["identity"])
CODE_MINUTES = 15
MAX_ATTEMPTS = 5
MAX_PER_HOUR = 5


async def _own(session: AsyncSession, profile_id: uuid.UUID, principal: Principal) -> Profile:
    profile = await session.get(Profile, profile_id)
    # Not found rather than forbidden for strangers: do not confirm that a profile exists.
    if profile is None or not (principal.is_admin or profile.owner_id == principal.user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


def _hash(binding_id, code: str) -> str:
    return hashlib.sha256(f"{get_settings().jwt_secret}|{binding_id}|{code}".encode()).hexdigest()


def _view(b: IdentityBinding) -> dict:
    return {"kind": b.kind, "subject": b.subject, "verified_at": b.verified_at}


async def _recent(session: AsyncSession, profile_id: uuid.UUID, kind: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    return (await session.execute(select(func.count()).select_from(IdentityBinding).where(
        IdentityBinding.profile_id == profile_id, IdentityBinding.kind == kind, IdentityBinding.created_at > since))).scalar_one()


class EmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PageIn(BaseModel):
    url: str = Field(min_length=10, max_length=500)


@router.get("/{profile_id}/identity")
async def list_bindings(profile_id: uuid.UUID, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    await _own(session, profile_id, principal)
    rows = (await session.execute(select(IdentityBinding).where(IdentityBinding.profile_id == profile_id).order_by(IdentityBinding.created_at))).scalars().all()
    return {
        "verified": [_view(b) for b in rows if b.status == "verified"],
        "pending": [{"kind": b.kind, "subject": b.subject} for b in rows if b.status == "pending"],
        "note": "A binding shows you control an email at, or a page on, an institution's site. A reviewer weighs it; it does not approve anything.",
    }


@router.post("/{profile_id}/identity/email", dependencies=[Depends(ip_limit("identity-email", 10))])
async def start_email(profile_id: uuid.UUID, body: EmailIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    await _own(session, profile_id, principal)
    domain = identity.institutional_domain(body.email)
    if domain is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Use an email address at your institution. Personal addresses (Gmail, Yahoo, Outlook...) cannot show a tie to one.")
    if await _recent(session, profile_id, "domain_email") >= MAX_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many codes requested - try again later")
    s = get_settings()
    if not mailer.configured() and not s.is_local:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Email delivery is not configured on this server")

    await session.execute(delete(IdentityBinding).where(IdentityBinding.profile_id == profile_id, IdentityBinding.kind == "domain_email", IdentityBinding.status == "pending"))
    code = f"{secrets.randbelow(10**6):06d}"
    binding = IdentityBinding(profile_id=profile_id, kind="domain_email", subject=domain, status="pending",
                              expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_MINUTES))
    session.add(binding)
    await session.flush()
    binding.code_hash = _hash(binding.id, code)
    await session.commit()

    out: dict = {"sent": True, "domain": domain, "expires_in_minutes": CODE_MINUTES}
    if mailer.configured():
        import asyncio

        from app.services.outreach import _smtp_send

        try:
            await asyncio.to_thread(_smtp_send, body.email.strip(), "Your Pramaan identity code", f"Your code is {code}. It expires in {CODE_MINUTES} minutes.\n\nIf you did not ask for it, ignore this email.")
        except Exception as exc:  # noqa: BLE001
            log.warning("identity code email failed: %s", getattr(exc, "reason", type(exc).__name__))
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, mailer.user_message(exc)) from exc
    else:  # local development without SMTP: show it where the developer can find it
        out["dev_code"] = code
    return out


@router.post("/{profile_id}/identity/email/confirm", dependencies=[Depends(ip_limit("identity-confirm", 20))])
async def confirm_email(profile_id: uuid.UUID, body: CodeIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    await _own(session, profile_id, principal)
    b = (await session.execute(select(IdentityBinding).where(
        IdentityBinding.profile_id == profile_id, IdentityBinding.kind == "domain_email", IdentityBinding.status == "pending")
        .order_by(IdentityBinding.created_at.desc()).limit(1))).scalar_one_or_none()
    if b is None or (b.expires_at and b.expires_at < datetime.now(timezone.utc)) or b.attempts >= MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code has expired - request a new one")
    b.attempts += 1
    if not hmac.compare_digest(b.code_hash, _hash(b.id, body.code)):
        await session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code")
    b.status, b.verified_at, b.code_hash = "verified", datetime.now(timezone.utc), ""
    await session.commit()
    return _view(b)


@router.post("/{profile_id}/identity/page", dependencies=[Depends(ip_limit("identity-page", 10))])
async def start_page(profile_id: uuid.UUID, body: PageIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    await _own(session, profile_id, principal)
    host = identity.page_host(body.url)
    if host is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give the full https address of a page on your institution's website.")
    if await _recent(session, profile_id, "page_code") >= MAX_PER_HOUR:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts - try again later")
    await session.execute(delete(IdentityBinding).where(IdentityBinding.profile_id == profile_id, IdentityBinding.kind == "page_code", IdentityBinding.status == "pending"))
    token = identity.new_token()
    session.add(IdentityBinding(profile_id=profile_id, kind="page_code", subject=host, status="pending", challenge=token, target=body.url.strip()))
    await session.commit()
    return {"token": token, "host": host, "url": body.url.strip(), "instructions": f"Put this exact text anywhere on that page (a comment is fine), then ask us to check: {token}"}


@router.post("/{profile_id}/identity/page/check", dependencies=[Depends(ip_limit("identity-page-check", 10))])
async def check_page(profile_id: uuid.UUID, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    await _own(session, profile_id, principal)
    b = (await session.execute(select(IdentityBinding).where(
        IdentityBinding.profile_id == profile_id, IdentityBinding.kind == "page_code", IdentityBinding.status == "pending")
        .order_by(IdentityBinding.created_at.desc()).limit(1))).scalar_one_or_none()
    if b is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Start by asking for a code for a page")
    try:
        text = await identity.fetch_page_text(b.target)
    except identity.UnsafeTarget as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if b.challenge not in text:
        raise HTTPException(status.HTTP_409_CONFLICT, "The code was not found on that page yet. Publish it exactly as shown and try again.")
    b.status, b.verified_at = "verified", datetime.now(timezone.utc)
    await session.commit()
    return _view(b)
