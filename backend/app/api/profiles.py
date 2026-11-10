from __future__ import annotations

import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Principal, get_optional_principal, require_scope, require_verified_email
from app.config import get_settings
from app.domain import is_known_photo, pick_photo
from app.services import fields as fields_svc
from app.services import webhooks
from app.models import Claim, Consent, Evidence, Profile, ReviewItem
from app.schemas import (
    CertificateOut,
    ClaimIn,
    ClaimOut,
    ProfileIn,
    ProfileOut,
    ProfilePatch,
    ProfileSummary,
)
from app.services.certificates import CertificateError, get_certificate, issue_certificate

router = APIRouter(prefix="/v1/profiles", tags=["profiles"])


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
    return f"{base[:60]}-{secrets.token_hex(2)}"


def can_edit(principal: Principal, profile: Profile) -> bool:
    return principal.is_admin or profile.owner_id == principal.user.id


async def _load(session: AsyncSession, profile_id: uuid.UUID) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


async def _load_editable(
    session: AsyncSession, profile_id: uuid.UUID, principal: Principal
) -> Profile:
    profile = await _load(session, profile_id)
    if not can_edit(principal, profile):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot modify this profile")
    return profile


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
async def create_profile(
    body: ProfileIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    data = body.model_dump(exclude={"consent_public_listing", "custom"})
    try:
        custom = fields_svc.clean_values(body.custom, await fields_svc.active_definitions(session), strict=True)
    except fields_svc.FieldError as exc:
        raise HTTPException(422, str(exc)) from exc
    profile = Profile(owner_id=principal.user.id, slug=slugify(body.full_name), custom=custom, **data)
    session.add(profile)
    await session.flush()
    session.add(
        Consent(
            profile_id=profile.id,
            kind="public_listing",
            granted=body.consent_public_listing,
            text="I agree to have my verified profile listed in the public Pramaan registry.",
        )
    )
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("", response_model=list[ProfileSummary])
async def list_profiles(
    q: str | None = Query(default=None, max_length=200),
    sector: str | None = None,
    state: str | None = None,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Public directory: only approved profiles."""
    stmt = select(Profile).where(Profile.status == "approved")
    if sector:
        stmt = stmt.where(Profile.sector.ilike(sector))
    if state:
        stmt = stmt.where(Profile.state.ilike(state))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Profile.full_name.ilike(like), Profile.headline.ilike(like), Profile.bio.ilike(like))
        )
    stmt = stmt.order_by(Profile.created_at.desc()).limit(limit).offset(offset)
    return (await session.execute(stmt)).scalars().all()


@router.get("/mine", response_model=list[ProfileOut])
async def my_profiles(
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.execute(
        select(Profile).where(Profile.owner_id == principal.user.id).order_by(Profile.created_at.desc())
    )
    return rows.scalars().all()


@router.get("/{slug}", response_model=ProfileOut)
async def get_profile(
    slug: str,
    principal: Principal | None = Depends(get_optional_principal),
    session: AsyncSession = Depends(get_session),
):
    profile = (await session.execute(select(Profile).where(Profile.slug == slug))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    if profile.status != "approved" and not (principal and can_edit(principal, profile)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


_PUBLIC_FIELDS = ("headline", "sector", "state", "city", "bio", "languages", "institutions", "photo_url", "custom")


@router.patch("/{profile_id}", response_model=ProfileOut)
async def patch_profile(
    profile_id: uuid.UUID,
    body: ProfilePatch,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    profile = await _load_editable(session, profile_id, principal)
    changes = body.model_dump(exclude_unset=True)
    if "custom" in changes:
        defs = await fields_svc.active_definitions(session)
        try:
            cleaned = fields_svc.clean_values(changes["custom"] or {}, defs, strict=True)
        except fields_svc.FieldError as exc:
            raise HTTPException(422, str(exc)) from exc
        # `null`/empty clears a field; values of deactivated fields are preserved.
        cleared = {k for k, v in changes["custom"].items() if v in (None, "", [])}
        changes["custom"] = {k: v for k, v in {**profile.custom, **cleaned}.items() if k not in cleared}
    public_changed = any(
        k in changes and changes[k] != getattr(profile, k) for k in _PUBLIC_FIELDS
    )
    for key, value in changes.items():
        setattr(profile, key, value)
    if public_changed and profile.status == "approved":
        # Approved text is what the public sees: edits must be re-reviewed before going live.
        profile.status = "pending_review"
        session.add(ReviewItem(profile_id=profile.id, reason="Edited after approval", confidence=0.0))
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post("/{profile_id}/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
async def add_claim(
    profile_id: uuid.UUID,
    body: ClaimIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    """New claims start as 'self' (unverified). Pariksha/Lipik upgrade them with evidence."""
    profile = await _load_editable(session, profile_id, principal)
    claim = Claim(
        profile_id=profile.id, field=body.field, value=body.value, year=body.year,
        status="self", confidence=0.2,
    )
    claim.evidence.append(Evidence(kind="chat", quote=body.value[:500]))
    session.add(claim)
    await session.commit()
    await session.refresh(claim)
    return claim


@router.post("/{profile_id}/submit", response_model=ProfileOut)
async def submit_for_review(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    profile = await _load_editable(session, profile_id, principal)
    require_verified_email(principal)
    consent = (
        await session.execute(
            select(Consent)
            .where(Consent.profile_id == profile.id, Consent.kind == "public_listing")
            .order_by(Consent.created_at.desc())
        )
    ).scalars().first()
    if not consent or not consent.granted:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Consent to public listing is required before review."
        )
    if profile.status in ("draft", "rejected"):
        profile.status = "pending_review"
        session.add(
            ReviewItem(profile_id=profile.id, reason="Submitted for review", confidence=0.0)
        )
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post("/{profile_id}/certificate", response_model=CertificateOut, status_code=201)
async def issue_profile_certificate(
    profile_id: uuid.UUID,
    photo_id: str = Query(default="", max_length=80),
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    profile = await _load_editable(session, profile_id, principal)
    if photo_id and not is_known_photo(photo_id):
        raise HTTPException(422, "Unknown photo_id")
    try:
        cert = await issue_certificate(session, profile, photo_id=photo_id)
    except CertificateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if not cert.photo_id:  # themed photo for the person's field, chosen deterministically
        cert.photo_id = pick_photo(profile.sector, cert.digest)
    await session.commit()
    webhooks.schedule("certificate.issued", {
        "code": cert.code, "verify_url": f"{get_settings().public_base_url}/verify/{cert.code}",
        "issued_at": cert.issued_at.isoformat(), "profile": webhooks.profile_payload(profile),
    })
    return cert


@router.get("/{profile_id}/certificates", response_model=list[CertificateOut])
async def list_profile_certificates(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    from app.models import Certificate

    profile = await _load_editable(session, profile_id, principal)
    rows = await session.execute(
        select(Certificate).where(Certificate.profile_id == profile.id).order_by(Certificate.issued_at.desc())
    )
    return rows.scalars().all()


@router.get("/{profile_id}/export")
async def export_my_data(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    profile = await _load_editable(session, profile_id, principal)
    return ProfileOut.model_validate(profile).model_dump(mode="json")


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_data(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    """Right to erasure. Signed certificates are revoked; the transparency log keeps only hashes."""
    from datetime import datetime, timezone

    from app.models import Certificate

    profile = await _load_editable(session, profile_id, principal)
    certs = (
        await session.execute(select(Certificate).where(Certificate.profile_id == profile.id))
    ).scalars().all()
    for cert in certs:
        cert.revoked_at = datetime.now(timezone.utc)
        cert.payload = {"redacted": True}
    await session.delete(profile)
    await session.commit()
