"""Mission Control: a live view of every agent, over Server-Sent Events."""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import bus, recent_events
from app.core.security import decode_access_token
from app.db import get_session, get_sessionmaker
from app.deps import Principal, require_admin
from app.models import AgentRun, Profile, User

router = APIRouter(prefix="/v1/agents", tags=["agents"])

CATALOG = [
    {"name": "Saathi", "role": "Interviewer", "does": "Talks with the person (any language) and builds the profile live", "replaces": "Form filling"},
    {"name": "Khoji-Pehle", "role": "Researcher", "does": "Finds public information so the person only has to confirm", "replaces": "Typing in a biography"},
    {"name": "Lipik", "role": "Document reader", "does": "Reads uploaded credentials and checks the holder is the applicant", "replaces": "Manual data entry from certificates"},
    {"name": "Pariksha", "role": "Fact-checker", "does": "Checks each claim against public sources and quotes its evidence", "replaces": "Googling every claim"},
    {"name": "Prahari", "role": "Auditor", "does": "Approves only at ≥95% confidence; otherwise escalates to a human with reasons", "replaces": "Reviewing every profile by hand"},
    {"name": "Setu", "role": "Connector", "does": "Links people by institution, sector and place", "replaces": "Manual tagging and clustering"},
    {"name": "Khoji", "role": "Search", "does": "Answers plain-English questions about the registry", "replaces": "Building filters and queries"},
    {"name": "Chitrakar", "role": "Artist", "does": "Designs each certificate's unique artwork", "replaces": "Designing certificates"},
    {"name": "Doot", "role": "Outreach", "does": "Drafts and schedules follow-up messages", "replaces": "Writing emails"},
    {"name": "Shilpkar", "role": "Builder", "does": "Adds new fields and features on request, tested before release", "replaces": "Developer tickets"},
]


@router.get("/catalog")
async def catalog():
    return CATALOG


@router.get("/runs")
async def runs(
    limit: int = 50,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(AgentRun).order_by(AgentRun.started_at.desc()).limit(min(limit, 200)))
    ).scalars().all()
    return [
        {"id": str(r.id), "workflow": r.workflow, "profile_id": str(r.profile_id) if r.profile_id else None,
         "status": r.status, "summary": r.summary, "started_at": r.started_at, "ended_at": r.ended_at}
        for r in rows
    ]


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: uuid.UUID,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    from app.models import AgentEvent

    rows = (
        await session.execute(select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.id))
    ).scalars().all()
    return [{"id": e.id, "agent": e.agent, "kind": e.kind, "message": e.message,
             "data": e.data, "confidence": e.confidence, "ts": e.created_at} for e in rows]


async def _authorize_stream(token: str, profile_id: uuid.UUID | None) -> bool:
    """EventSource can't send headers, so the JWT arrives as ?token=. Admins may watch
    everything; anyone else only the profile they own."""
    claims = decode_access_token(token)
    if not claims or "purpose" in claims:
        return False
    async with get_sessionmaker()() as session:
        user = await session.get(User, uuid.UUID(claims["sub"]))
        if user is None:
            return False
        if user.role == "admin":
            return True
        if profile_id is None:
            return False
        profile = await session.get(Profile, profile_id)
        return bool(profile and profile.owner_id == user.id)


@router.get("/stream")
async def stream(request: Request, token: str, profile_id: uuid.UUID | None = None):
    if not await _authorize_stream(token, profile_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not allowed to watch this stream")

    history = list(reversed(await recent_events(profile_id=profile_id, limit=40)))
    queue = bus.subscribe()
    wanted = str(profile_id) if profile_id else None

    async def gen():
        try:
            yield "retry: 3000\n\n"
            for event in history:
                yield f"event: history\ndata: {json.dumps(event, default=str)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if wanted and event.get("profile_id") != wanted:
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
