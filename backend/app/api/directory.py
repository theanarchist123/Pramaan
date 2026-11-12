"""Public directory: semantic search (Khoji), the relationship graph (Setu) and map counts."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.events import start_run
from app.agents.khoji import chips, plan_search
from app.core.ratelimit import check_rate_limit
from app.db import get_session
from app.models import Certificate, Profile
from app.schemas import ProfileSummary
from app.services import directory as svc
from app.services.embeddings import get_embedder

router = APIRouter(prefix="/v1", tags=["directory"])


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    state: str | None = None
    sector: str | None = None
    limit: int = Field(default=12, ge=1, le=50)


class ClaimBrief(BaseModel):
    value: str
    status: str


class SearchHit(ProfileSummary):
    score: float
    reasons: list[str]
    claims: list[ClaimBrief]
    is_demo: bool


class SearchOut(BaseModel):
    query: str
    plan: dict
    chips: list[dict] = []
    relaxed: bool
    embedder: str
    took_ms: int
    results: list[SearchHit]


def _hit(h: svc.Hit) -> SearchHit:
    p = h.profile
    verified = [ClaimBrief(value=c.value, status=c.status) for c in p.claims if c.status in svc.VERIFIED][:3]
    return SearchHit(
        id=p.id, slug=p.slug, full_name=p.full_name, headline=p.headline, sector=p.sector, state=p.state,
        city=p.city, photo_url=p.photo_url, status=p.status, score=h.score, reasons=h.reasons,
        claims=verified, is_demo=p.is_demo,
    )


@router.post("/search", response_model=SearchOut)
async def search(body: SearchIn, request: Request, session: AsyncSession = Depends(get_session)):
    """Ask in plain English (any language). Only approved, consenting profiles are searchable."""
    ip = request.client.host if request.client else "?"
    ok, _ = await check_rate_limit(f"search:{ip}", 40)
    if not ok:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many searches — try again in a minute")

    t0 = time.perf_counter()
    ctx = await start_run("search")
    plan = await plan_search(ctx, body.query.strip())
    # Explicit choices filter; an inferred sector only nudges the ranking.
    state, sector = body.state or plan.state, body.sector

    hits = await svc.search(
        session, plan.semantic_query, state=state, sector=sector,
        boost_sector=None if sector else plan.sector, limit=body.limit,
    )
    relaxed = False
    if not hits and (state or sector):
        relaxed = True  # never return an empty page just because a filter was too strict
        hits = await svc.search(session, plan.semantic_query, limit=body.limit)
        await ctx.emit("Khoji", "warning", "No exact match for those filters — showing the closest people instead")
    await ctx.finish("done", f"{len(hits)} result(s)")
    return SearchOut(
        query=body.query, plan=plan.model_dump(), chips=chips(plan), relaxed=relaxed, embedder=get_embedder().kind,
        took_ms=int((time.perf_counter() - t0) * 1000), results=[_hit(h) for h in hits],
    )


@router.get("/graph")
async def graph(session: AsyncSession = Depends(get_session)):
    return await svc.graph_payload(session)


@router.get("/stats/map")
async def map_stats(session: AsyncSession = Depends(get_session)):
    return await svc.counts(session)


@router.get("/public/{slug}/certificates")
async def public_certificates(slug: str, session: AsyncSession = Depends(get_session)):
    profile = (await session.execute(select(Profile).where(Profile.slug == slug))).scalar_one_or_none()
    if profile is None or profile.status != "approved":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    rows = (
        await session.execute(
            select(Certificate).where(Certificate.profile_id == profile.id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc())
        )
    ).scalars().all()
    return [{"code": c.code, "issued_at": c.issued_at} for c in rows]
