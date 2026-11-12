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
from app.deps import SESSION_COOKIE, Principal, require_admin
from app.models import AgentRun, Profile, User

router = APIRouter(prefix="/v1/agents", tags=["agents"])

# `kind` says what is really behind each name, so the product never claims more than the code does:
#   llm      a model call (structured output) does the work
#   hybrid   deterministic rules decide; a model only assists
#   service  ordinary code, no model
CATALOG = [
    {"name": "Saathi", "kind": "llm", "role": "Interviewer", "does": "Talks with the person (any language) and builds the profile live", "replaces": "Form filling"},
    {"name": "Khoji-Pehle", "kind": "llm", "role": "Researcher", "does": "Finds public information so the person only has to confirm", "replaces": "Typing in a biography"},
    {"name": "Lipik", "kind": "llm", "role": "Document reader", "does": "Reads uploaded credentials (vision model) and checks the holder and issuer", "replaces": "Manual data entry from certificates"},
    {"name": "Pariksha", "kind": "llm", "role": "Fact-checker", "does": "Checks each claim against Wikipedia and Wikidata; a citation only counts if the quote is really in the source", "replaces": "Googling every claim"},
    {"name": "Prahari", "kind": "hybrid", "role": "Auditor", "does": "Fixed rules decide approve vs. escalate (a model only checks the bio); first listings and awards always go to a human", "replaces": "Reviewing every profile by hand"},
    {"name": "Setu", "kind": "service", "role": "Connector", "does": "Links people who share an institution, sector or place (plain code, no model)", "replaces": "Manual tagging and clustering"},
    {"name": "Khoji", "kind": "llm", "role": "Search", "does": "A model turns a plain-English question into filters; ranking is vector search", "replaces": "Building filters and queries"},
    {"name": "Chitrakar", "kind": "service", "role": "Certificate artwork", "does": "Draws each certificate's artwork deterministically from its hash, over a curated sector photo (no image model)", "replaces": "Designing certificates"},
    {"name": "Doot", "kind": "llm", "role": "Outreach", "does": "Drafts follow-up messages; a human approves every send", "replaces": "Writing emails"},
    {"name": "Shilpkar", "kind": "llm", "role": "Builder", "does": "Proposes new profile fields and read-only API endpoints, tested in a sandbox before a human approves them", "replaces": "Developer tickets"},
]


@router.get("/catalog")
async def catalog():
    return CATALOG


@router.get("/replay")
async def replay(session: AsyncSession = Depends(get_session)):
    """A recorded REAL verification run, for the public Agent Floor (spec 6.7). Safe by construction: only runs on profiles flagged as
    fictional demos are ever eligible, so no real person's name or evidence can appear; the payload carries no profile, user or owner
    identifier; and times are offsets from the start of the run. With no demo run on record it says so instead of falling back to a real one."""
    from app.models import AgentEvent

    run = (
        await session.execute(
            select(AgentRun)
            .join(Profile, Profile.id == AgentRun.profile_id)
            .where(AgentRun.workflow == "verify_profile", AgentRun.status == "done", Profile.is_demo.is_(True))
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        return {"available": False}
    profile = await session.get(Profile, run.profile_id)
    rows = (await session.execute(select(AgentEvent).where(AgentEvent.run_id == run.id).order_by(AgentEvent.id).limit(200))).scalars().all()
    if not rows:
        return {"available": False}
    t0 = rows[0].created_at
    outcome = {"approved": "sealed", "pending_review": "with_reviewer"}.get(profile.status, "stopped")
    return {
        "available": True,
        "demo": True,
        "run_id": str(run.id),
        "outcome": outcome,
        "events": [
            {"t_ms": max(0, int((e.created_at - t0).total_seconds() * 1000)), "agent": e.agent, "kind": e.kind, "message": e.message, "confidence": e.confidence}
            for e in rows
        ],
    }


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


async def _authorize_stream(request: Request, profile_id: uuid.UUID | None) -> bool:
    """EventSource can't send headers, so the browser authenticates with its httpOnly session cookie (never a
    token in the URL, which would end up in logs and history). Admins may watch everything; anyone else
    only the profile they own."""
    token = request.cookies.get(SESSION_COOKIE)
    auth = request.headers.get("authorization", "")
    if not token and auth.lower().startswith("bearer "):
        token = auth[7:].strip()  # non-browser clients
    claims = decode_access_token(token) if token else None
    if not claims or "purpose" in claims:
        return False
    async with get_sessionmaker()() as session:
        user = await session.get(User, uuid.UUID(claims["sub"]))
        if user is None:
            return False
        if user.tokens_valid_after is not None and float(claims.get("iatf", 0)) < user.tokens_valid_after.timestamp():
            return False
        if user.role == "admin":
            return True
        if profile_id is None:
            return False
        profile = await session.get(Profile, profile_id)
        return bool(profile and profile.owner_id == user.id)


@router.get("/stream")
async def stream(request: Request, profile_id: uuid.UUID | None = None):
    if not await _authorize_stream(request, profile_id):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not allowed to watch this stream")

    history = list(reversed(await recent_events(profile_id=profile_id, limit=40)))
    queue = bus.subscribe()
    wanted = str(profile_id) if profile_id else None
    last_id = max((e["id"] for e in history if e.get("id")), default=0)

    async def gen():
        nonlocal last_id
        try:
            yield "retry: 3000\n\n"
            for event in history:
                yield f"event: history\ndata: {json.dumps(event, default=str)}\n\n"
            idle = 0
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=3)
                except asyncio.TimeoutError:
                    idle += 3
                    # Events written by ANOTHER process (the worker) never reach this process's in-memory bus,
                    # so also tail the table.
                    for ev in reversed(await recent_events(profile_id=profile_id, limit=20)):
                        if ev["id"] and ev["id"] > last_id:
                            last_id = ev["id"]
                            yield f"data: {json.dumps(ev, default=str)}\n\n"
                    if idle >= 15:
                        idle = 0
                        yield ": keepalive\n\n"
                    continue
                if event.get("id"):
                    if event["id"] <= last_id:
                        continue
                    last_id = event["id"]
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
