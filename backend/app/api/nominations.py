"""Nominate someone (DR-22): a signed-in member suggests a person who should be listed.

What it does: creates ONE DRAFT invitation in the outbox, for staff to look at, edit and schedule. What it never does: email anyone by itself, create a profile for the
nominee (nothing exists until they join and agree, I-5), or put anything the nominator typed that could be a link, address or phone number into the invitation (I-7: the
same cleaning as every other outreach text). The answer is always the same, so it cannot be used to find out who already has an account.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.db import get_session
from app.deps import Principal, require_scope, require_verified_email
from app.models import OutboxMessage, User
from app.services import outreach as svc

router = APIRouter(prefix="/v1", tags=["nominations"])
MAX_PENDING = 200  # a flood of nominations must never bury the staff queue


class NominationIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    note: str = Field(default="", max_length=300, description="Why this person should be listed. Links, addresses and phone numbers are removed.")


@router.post("/nominations", status_code=status.HTTP_202_ACCEPTED)
async def nominate(body: NominationIn, principal: Principal = Depends(require_scope("profiles:write")), session: AsyncSession = Depends(get_session)):
    await require_verified_email(principal)
    ok, _ = await check_rate_limit(f"nominate:{principal.user.id}", 3)
    if not ok:
        from fastapi import HTTPException

        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "That is a lot of nominations at once. Try again in a minute.")
    email = body.email.strip().lower()
    nominator = (principal.user.name or "").strip() or "A Pramaan member"
    already = (await session.execute(select(User.id).where(User.email == email))).first() is not None
    pending = (await session.execute(select(OutboxMessage.id).where(OutboxMessage.kind == "nomination", OutboxMessage.status == "draft").limit(MAX_PENDING))).all()
    duplicate = (await session.execute(select(OutboxMessage.id).where(OutboxMessage.kind == "nomination", OutboxMessage.to_email == email))).first() is not None
    if not (already or duplicate or len(pending) >= MAX_PENDING or await svc.is_suppressed(session, email)):
        note = f"{nominator} suggested we invite you." + (f" Their words: {body.note.strip()}" if body.note.strip() else "")
        subject, text = svc.invite_message(body.name, note, get_settings().public_base_url)  # cleans the note: no links, addresses or phone numbers
        session.add(OutboxMessage(profile_id=None, kind="nomination", to_email=email, subject=subject, body=text, status="draft"))
        await session.commit()
    return {"status": "received"}
