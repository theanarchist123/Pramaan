"""Registry and compliance (ADM-16): suspend / restore a profile, and a read-only view of consents.

Suspension is deliberately simple and reversible: the profile stops being public everywhere (every public query already requires
status == "approved"), its owner still sees it and why, and a person with `profile.suspend` can restore it. Both directions need a
written reason and are audited. The owner cannot suspend or restore their own profile (I-10), and resubmitting cannot undo it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Principal, require_permission, require_stepup
from app.models import Consent, Profile
from app.services import audit

router = APIRouter(prefix="/v1/admin", tags=["registry"])


class ReasonIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


async def _profile(session: AsyncSession, profile_id: uuid.UUID, principal: Principal) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    if profile.owner_id == principal.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot change the status of your own profile")  # I-10
    return profile


async def _change(session, request, principal, profile, *, expect: str, to: str, action: str, reason: str) -> Profile:
    if profile.status != expect:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The profile is {profile.status}, not {expect}")
    before = profile.status
    profile.status = to
    await audit.record(session, actor_id=principal.user.id, actor_role="registry", action=action, target_type="profile",
                       target_id=str(profile.id), before={"status": before}, after={"status": to}, reason=reason,
                       ip=request.client.host if request.client else "")
    await session.commit()
    # The graph and the "members by state" counts are derived from approved profiles: keep them in step.
    from app.services.directory import rebuild_graph

    await rebuild_graph(session)
    await session.commit()
    return profile


@router.post("/registry/profiles/{profile_id}/suspend")
async def suspend(profile_id: uuid.UUID, body: ReasonIn, request: Request,
                  principal: Principal = Depends(require_permission("profile.suspend")),
                  session: AsyncSession = Depends(get_session)):
    require_stepup(principal)
    p = await _change(session, request, principal, await _profile(session, profile_id, principal),
                      expect="approved", to="suspended", action="profile.suspend", reason=body.reason)
    return {"id": str(p.id), "status": p.status}


@router.post("/registry/profiles/{profile_id}/restore")
async def restore(profile_id: uuid.UUID, body: ReasonIn, request: Request,
                  principal: Principal = Depends(require_permission("profile.suspend")),
                  session: AsyncSession = Depends(get_session)):
    require_stepup(principal)
    p = await _change(session, request, principal, await _profile(session, profile_id, principal),
                      expect="suspended", to="approved", action="profile.restore", reason=body.reason)
    return {"id": str(p.id), "status": p.status}


@router.get("/consents")
async def consents(profile_id: uuid.UUID, _: Principal = Depends(require_permission("consent.read")),
                   session: AsyncSession = Depends(get_session)):
    """What the person agreed to, and when. Read-only: consent is changed by the person, never by staff."""
    rows = (await session.execute(select(Consent).where(Consent.profile_id == profile_id).order_by(Consent.created_at.desc()))).scalars().all()
    return [{"kind": c.kind, "granted": c.granted, "text": c.text, "created_at": c.created_at} for c in rows]
