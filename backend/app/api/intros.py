"""Introduction requests between members (v3). Contact details are never exposed by a request."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import check_rate_limit
from app.db import get_session
from app.deps import Principal, require_scope, require_verified_email
from app.models import IntroRequest, Profile, User
from app.services.intros import IntroRejected, clean_message

router = APIRouter(prefix="/v1", tags=["introductions"])


class IntroIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class RespondIn(BaseModel):
    accept: bool


def _out(i: IntroRequest, asker_name: str = "") -> dict:
    return {"id": str(i.id), "profile_id": str(i.profile_id), "from_name": asker_name, "message": i.message, "status": i.status, "created_at": i.created_at}


@router.post("/profiles/{slug}/intro", status_code=status.HTTP_201_CREATED)
async def request_intro(
    slug: str,
    body: IntroIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    await require_verified_email(principal)
    profile = (await session.execute(select(Profile).where(Profile.slug == slug, Profile.status == "approved"))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    if profile.owner_id == principal.user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't ask to be introduced to yourself")
    ok, _ = await check_rate_limit(f"intro:{principal.user.id}", 5)
    if not ok:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You've sent several requests already. Try again in a minute.")
    try:
        message = clean_message(body.message)
    except IntroRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    pending = (
        await session.execute(
            select(IntroRequest).where(IntroRequest.profile_id == profile.id, IntroRequest.requester_id == principal.user.id, IntroRequest.status == "pending")
        )
    ).first()
    if pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "You already have a request waiting for this person")
    req = IntroRequest(profile_id=profile.id, requester_id=principal.user.id, message=message)
    session.add(req)
    await session.commit()
    return _out(req, principal.user.name)


@router.get("/intros/incoming")
async def incoming(principal: Principal = Depends(require_scope("profiles:read")), session: AsyncSession = Depends(get_session)):
    """Requests to the profiles I own. Shows the sender's name and note only, never their e-mail."""
    rows = (
        await session.execute(
            select(IntroRequest, User.name)
            .join(Profile, Profile.id == IntroRequest.profile_id)
            .join(User, User.id == IntroRequest.requester_id)
            .where(Profile.owner_id == principal.user.id)
            .order_by(IntroRequest.created_at.desc())
        )
    ).all()
    return [_out(r, name) for r, name in rows]


@router.post("/intros/{intro_id}/respond")
async def respond(
    intro_id: uuid.UUID,
    body: RespondIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    req = await session.get(IntroRequest, intro_id)
    profile = await session.get(Profile, req.profile_id) if req else None
    if req is None or profile is None or profile.owner_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Request not found")
    if req.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Already answered")
    req.status = "accepted" if body.accept else "declined"
    req.responded_at = datetime.now(timezone.utc)
    await session.commit()
    return _out(req)
