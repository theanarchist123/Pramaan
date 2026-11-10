"""Admin review queue. (Prahari, the auditor agent, will drive most of this automatically.)"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Principal, require_admin
from app.core import redis as rd
from app.domain import HUMAN_CONFIDENCE_CAP, STATUS_HUMAN
from app.models import Claim, Evidence, Profile, ReviewItem
from app.schemas import ClaimOut, ProfileOut, StatusChangeIn

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class ReviewItemOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    reason: str
    confidence: float
    status: str
    created_at: datetime
    details: dict = {}
    profile: ProfileOut | None = None
    model_config = {"from_attributes": True}


class ClaimVerifyIn(BaseModel):
    """A person vouching for (or withdrawing) a claim. It can only ever produce `human` or `self`: a reviewer cannot
    mint `web` or `document` status, because those mean "an evidence record of that kind exists" (invariant I-8)."""

    status: str = Field(default="human", pattern="^(self|human)$")
    reason: str = Field(min_length=10, max_length=500, description="Why you are overriding the automated result")
    evidence_ref: str = Field(min_length=5, max_length=600, description="URL or case reference that supports it")
    confidence: float = Field(default=HUMAN_CONFIDENCE_CAP, ge=0, le=1)


def _no_self_review(principal: Principal, profile: Profile | None) -> None:
    """Invariant I-10: nobody approves, overrides or reviews their own profile."""
    if profile is not None and profile.owner_id == principal.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review your own profile")


@router.get("/system")
async def system_status(_: Principal = Depends(require_admin)):
    """What the running server is really doing. Admin-only (the public /healthz reveals nothing).
    `degraded` lists features that silently fell back to something weaker."""
    from app.config import get_settings
    from app.llm.client import get_llm
    from app.services.embeddings import get_embedder

    s, llm, emb = get_settings(), get_llm(), get_embedder()
    degraded = []
    if rd.status()["fallback_active"]:
        degraded.append("Redis is unreachable: rate limits and locks are per-process only")
    if s.embeddings.lower() != "hash" and emb.kind == "hash":
        degraded.append("Semantic search is using the lexical hash fallback (fastembed is not installed or failed to load)")
    if s.llm_mode == "live" and llm.mode != "live":
        degraded.append("LLM_MODE=live but no API key: agents are running on the offline mock")
    if llm.mode == "mock":
        degraded.append("Agents are in offline mock mode: verification is not using a real model")
    if not s.wikimedia_contact.strip():
        degraded.append("WIKIMEDIA_CONTACT is not set: Wikipedia may refuse lookups, so there is no public evidence")
    return {
        "environment": "development" if s.is_local else "production",
        "llm": {"mode": llm.mode, "provider": llm.provider, "models": llm.model_names},
        "embeddings": emb.kind,
        "plugins_enabled": s.plugins_enabled,
        "redis": rd.status(),
        "job_backend": s.job_backend,
        "worker_inline": s.worker_inline,
        "sandbox_in_api": s.sandbox_in_api,
        "degraded": degraded,
    }


@router.get("/agent-runs")
async def agent_runs(
    workflow: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Every agent run with its model usage: calls, tokens, latency and errors (from the llm_calls table), plus how many
    events it produced. Tokens are reported, not priced: confirm the current price list before turning them into cost."""
    from sqlalchemy import func

    from app.models import AgentEvent, AgentRun, LlmCall

    calls = (
        select(
            LlmCall.run_id.label("run_id"), func.count().label("calls"),
            func.coalesce(func.sum(LlmCall.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LlmCall.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.avg(LlmCall.latency_ms), 0).label("avg_latency_ms"),
            func.count().filter(LlmCall.ok.is_(False)).label("errors"),
        ).group_by(LlmCall.run_id).subquery()
    )
    events = select(AgentEvent.run_id.label("run_id"), func.count().label("n")).group_by(AgentEvent.run_id).subquery()
    stmt = (
        select(AgentRun, calls.c.calls, calls.c.input_tokens, calls.c.output_tokens, calls.c.avg_latency_ms, calls.c.errors, events.c.n)
        .outerjoin(calls, calls.c.run_id == AgentRun.id)
        .outerjoin(events, events.c.run_id == AgentRun.id)
        .order_by(AgentRun.started_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if workflow:
        stmt = stmt.where(AgentRun.workflow == workflow)
    if status_filter:
        stmt = stmt.where(AgentRun.status == status_filter)
    out = []
    for run, n_calls, tin, tout, avg_ms, errs, n_events in (await session.execute(stmt)).all():
        out.append({
            "id": str(run.id), "workflow": run.workflow, "profile_id": str(run.profile_id) if run.profile_id else None,
            "status": run.status, "summary": run.summary, "started_at": run.started_at, "ended_at": run.ended_at,
            "events": n_events or 0,
            "llm": {"calls": n_calls or 0, "input_tokens": int(tin or 0), "output_tokens": int(tout or 0),
                    "avg_latency_ms": int(avg_ms or 0), "errors": errs or 0},
        })
    return out


@router.get("/review", response_model=list[ReviewItemOut])
async def review_queue(
    _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    items = (
        await session.execute(
            select(ReviewItem).where(ReviewItem.status == "open").order_by(ReviewItem.created_at)
        )
    ).scalars().all()
    out = []
    for item in items:
        profile = await session.get(Profile, item.profile_id)  # claims + evidence load eagerly
        out.append(
            ReviewItemOut.model_validate(item).model_copy(
                update={"profile": ProfileOut.model_validate(profile) if profile else None}
            )
        )
    return out


class ResolveIn(BaseModel):
    note: str = Field(default="", max_length=500)


@router.post("/review/{item_id}/resolve")
async def resolve_review(
    item_id: uuid.UUID,
    body: ResolveIn,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Close a review item without changing the profile's published status (used for document / requested reviews)."""
    item = await session.get(ReviewItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review item not found")
    if item.status != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Already {item.status}")
    _no_self_review(principal, await session.get(Profile, item.profile_id))
    item.status = "resolved"
    item.details = {**(item.details or {}), "resolution_note": body.note}
    item.resolved_by = principal.user.id
    item.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "resolved"}


@router.get("/profiles", response_model=list[ProfileOut])
async def all_profiles(
    status_filter: str | None = None,
    _: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Profile).order_by(Profile.created_at.desc()).limit(200)
    if status_filter:
        stmt = stmt.where(Profile.status == status_filter)
    return (await session.execute(stmt)).scalars().all()


@router.post("/profiles/{profile_id}/status", response_model=ProfileOut)
async def set_status(
    profile_id: uuid.UUID,
    body: StatusChangeIn,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    _no_self_review(principal, profile)
    profile.status = body.status
    profile.decision_basis = "reviewer" if body.status == "approved" else ""
    open_items = (
        await session.execute(
            select(ReviewItem).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open")
        )
    ).scalars().all()
    paused_threads = [(i.details or {}).get("thread_id", "") for i in open_items]
    if body.status in ("approved", "rejected"):
        for item in open_items:
            item.status = body.status
            item.resolved_by = principal.user.id
            item.resolved_at = datetime.now(timezone.utc)
    if body.status == "approved":
        from app.services.directory import on_approved

        await on_approved(session, profile)
    await session.commit()
    await session.refresh(profile)
    if body.status in ("approved", "rejected"):
        from app.agents.workflows import resume_review

        for t in paused_threads:  # finish the paused agent run(s) that were waiting for this decision
            await resume_review(t, body.status, str(principal.user.id))
    if body.status == "approved":
        from app.services import webhooks

        webhooks.schedule("profile.approved", webhooks.profile_payload(profile))
    return profile


@router.post("/reindex")
async def reindex(_: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """Rebuild every embedding and the whole relationship graph (after bulk changes)."""
    from app.services.directory import rebuild_graph, reindex_all

    profiles = await reindex_all(session)
    edges = await rebuild_graph(session)
    await session.commit()
    return {"profiles_indexed": profiles, "edges": edges}


@router.post("/claims/{claim_id}/verify", response_model=ClaimOut)
async def set_claim_verification(
    claim_id: uuid.UUID,
    body: ClaimVerifyIn,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Manual override of a claim's verification (agents do this automatically in Phase 2)."""
    claim = await session.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    _no_self_review(principal, await session.get(Profile, claim.profile_id))
    claim.status = body.status
    if body.status == STATUS_HUMAN:
        claim.confidence = min(body.confidence, HUMAN_CONFIDENCE_CAP)
        claim.evidence.append(Evidence(kind="human", quote=body.reason, url=body.evidence_ref,
                                       source_hash=f"reviewer:{principal.user.id}"))
    else:
        claim.confidence = 0.0
    await session.commit()
    await session.refresh(claim)
    return claim
