"""Sector imagery: a public read of the APPROVED set, and admin curation (search -> approve one by one)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ratelimit import check_rate_limit
from app.db import get_session
from app.deps import Principal, require_admin
from app.models import ImageAsset
from app.services import images as svc

public = APIRouter(prefix="/v1/images", tags=["images"])
admin = APIRouter(prefix="/v1/admin/images", tags=["images"])


@public.get("/sector/{sector}")
async def sector_images(sector: str, response: Response, purpose: str | None = None, session: AsyncSession = Depends(get_session)):
    """Approved images for a sector. Read from our own table (no Unsplash call, no key); safe to cache."""
    if sector not in svc.SECTORS:
        raise HTTPException(404, "Unknown sector")
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"
    return await svc.for_sector(session, sector, purpose)


@admin.get("/candidates")
async def candidates(q: str = Query(min_length=2, max_length=120), color: str = "", principal: Principal = Depends(require_admin)):
    """Look at candidates. Nothing is stored or shown publicly until a person approves one."""
    ok, _ = await check_rate_limit(f"img-search:{principal.user.id}", 20)
    if not ok:
        raise HTTPException(429, "Slow down: Unsplash's API allows few requests per hour")
    try:
        return await svc.search_candidates(q, color=color)
    except svc.ImagesUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


class ApproveIn(BaseModel):
    candidate: dict
    sector: str
    purpose: str = "tile"


@admin.post("/approve", status_code=201)
async def approve(body: ApproveIn, principal: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    """One image, one human decision. This is where Unsplash's download endpoint is triggered."""
    required = {"unsplash_id", "url_raw", "photographer_name", "photographer_url", "photo_url", "download_location"}
    if not required <= set(body.candidate):
        raise HTTPException(422, "candidate is incomplete")
    if not body.candidate["url_raw"].startswith("https://images.unsplash.com/"):
        raise HTTPException(422, "only Unsplash hotlinks are accepted")
    try:
        row = await svc.approve(session, body.candidate, sector=body.sector, purpose=body.purpose, approved_by=principal.user.id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    await session.commit()
    return svc.public_view(row)


@admin.post("/{image_id}/deactivate")
async def deactivate(image_id: uuid.UUID, _: Principal = Depends(require_admin), session: AsyncSession = Depends(get_session)):
    row = await session.get(ImageAsset, image_id)
    if row is None:
        raise HTTPException(404, "Image not found")
    row.active = False
    await session.commit()
    return {"active": False}
