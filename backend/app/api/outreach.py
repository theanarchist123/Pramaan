"""Admin outbox: review, edit, schedule or send the follow-ups Doot drafted."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import start_run
from app.db import get_session
from app.deps import Principal, require_admin
from app.config import get_settings
from app.models import OutboxMessage, User
from app.services import outreach as svc

router = APIRouter(prefix="/v1/admin", tags=["outreach"])


class MessageOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID | None
    kind: str
    to_email: str
    subject: str
    body: str
    status: str
    error: str
    scheduled_for: datetime | None
    sent_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class SuggestIn(BaseModel):
    review_after_hours: float = Field(default=24, ge=0, le=720)
    idle_after_hours: float = Field(default=48, ge=0, le=720)


class EditIn(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=10, max_length=4000)


class ScheduleIn(BaseModel):
    at: datetime


async def _get(session: AsyncSession, msg_id: uuid.UUID) -> OutboxMessage:
    m = await session.get(OutboxMessage, msg_id)
    if m is None:
        raise HTTPException(404, "Message not found")
    return m


@router.post("/outreach/suggest", response_model=list[MessageOut])
async def suggest(
    body: SuggestIn = SuggestIn(), _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    """Ask Doot who needs a nudge. Creates drafts only — nothing is sent."""
    ctx = await start_run("doot_suggest")
    created = await svc.suggest(session, ctx, review_after_hours=body.review_after_hours, idle_after_hours=body.idle_after_hours)
    await session.commit()
    await ctx.finish("done", f"{len(created)} draft(s)")
    return created


class InviteIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    note: str = Field(default="", max_length=1500)


@router.post("/outreach/invite", response_model=MessageOut)
async def invite(body: InviteIn, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Invite a specific person to get listed. Creates a DRAFT in the outbox; a person sends it (and the send cap, the opt-out list and the
    unsubscribe link apply). People who already have an account, or who opted out, are refused."""
    email = body.email.strip().lower()
    if (await session.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise HTTPException(409, "This person already has an account")
    if await svc.is_suppressed(session, email):
        raise HTTPException(409, "This address has opted out of email from Pramaan")
    subject, text = svc.invite_message(body.name, body.note, get_settings().public_base_url)
    msg = OutboxMessage(profile_id=None, kind="invite", to_email=email, subject=subject, body=text, status="draft")
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


@router.get("/outbox", response_model=list[MessageOut])
async def outbox(
    status: str | None = None, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    stmt = select(OutboxMessage).order_by(OutboxMessage.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(OutboxMessage.status == status)
    return (await session.execute(stmt)).scalars().all()


@router.patch("/outbox/{msg_id}", response_model=MessageOut)
async def edit(msg_id: uuid.UUID, body: EditIn, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    m = await _get(session, msg_id)
    if m.status not in ("draft", "scheduled"):
        raise HTTPException(409, f"A {m.status} message can't be edited")
    if body.subject is not None:
        m.subject = " ".join(body.subject.split())  # a subject is one line: no header injection
    if body.body is not None:
        m.body = body.body
    await session.commit()
    await session.refresh(m)
    return m


@router.post("/outbox/{msg_id}/send", response_model=MessageOut)
async def send_now(msg_id: uuid.UUID, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    m = await _get(session, msg_id)
    if m.status not in ("draft", "scheduled"):
        raise HTTPException(409, f"This message is already {m.status}")
    await svc.send(session, m)
    await session.commit()
    await session.refresh(m)
    return m


@router.post("/outbox/{msg_id}/schedule", response_model=MessageOut)
async def schedule(msg_id: uuid.UUID, body: ScheduleIn, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    m = await _get(session, msg_id)
    if m.status not in ("draft", "scheduled"):
        raise HTTPException(409, f"This message is already {m.status}")
    at = body.at if body.at.tzinfo else body.at.replace(tzinfo=timezone.utc)
    m.status, m.scheduled_for = "scheduled", at
    await session.commit()
    await session.refresh(m)
    return m


@router.post("/outbox/{msg_id}/discard", response_model=MessageOut)
async def discard(msg_id: uuid.UUID, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    m = await _get(session, msg_id)
    if m.status == "sent":
        raise HTTPException(409, "Already sent")
    m.status = "discarded"
    await session.commit()
    await session.refresh(m)
    return m


# ---- public unsubscribe (linked from every email) and the suppression list -------------------------------------------------------------------
public = APIRouter(prefix="/v1/outreach", tags=["outreach"])


@public.get("/unsubscribe")
async def unsubscribe(token: str, session: AsyncSession = Depends(get_session)):
    """One click, no sign-in. Safe to open twice. A token that was not made by this server does nothing."""
    email = svc.email_from_token(token)
    if email is None:
        raise HTTPException(400, "This unsubscribe link is not valid")
    await svc.suppress(session, email, reason="unsubscribed from an email link")
    await session.commit()
    return {"unsubscribed": True, "message": "You will not receive any more emails from Pramaan."}


class SuppressIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    reason: str = Field(default="", max_length=200)


@router.post("/suppressions", status_code=201)
async def add_suppression(body: SuppressIn, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    await svc.suppress(session, body.email, reason=body.reason or "added by staff")
    await session.commit()
    return {"suppressed": True}
