"""Sector imagery from the Unsplash API (spec 4.9, class B images).

Compliance rules baked into the design (the guidelines must be re-read before launch: spec Appendix D):
  * HOTLINK ONLY. We store the `urls.raw` URL Unsplash returned (keeping its `ixid`, which powers view tracking) and the
    browser loads it from Unsplash with CDN sizing parameters. Nothing is downloaded or re-hosted.
  * ATTRIBUTION everywhere an image is shown: "Photo by <name> on Unsplash", both linked, with UTM parameters.
  * The DOWNLOAD ENDPOINT (`links.download_location`) is triggered once, when a human APPROVES an image for use, not on
    search results or listings.
  * The ACCESS KEY stays on the server; the browser never sees it and users need no Unsplash account.
  * HUMAN CURATION: there is no bulk or automatic import. An admin looks at candidates and approves them one at a time;
    runtime reads only the approved set from our own table (no live Unsplash call per page view).
  * No Unsplash branding as ours; certificates never use these (they use the frozen local photos).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ImageAsset

log = logging.getLogger("pramaan.images")
API = "https://api.unsplash.com"
SECTORS = {
    "Energy", "Agriculture", "Healthcare", "Technology", "Science", "Media", "Business", "Education", "Literature",
    "Social Work", "Arts & Culture", "Sports", "Law", "Public Service",
}
PURPOSES = {"tile", "cover", "empty"}  # never "certificate": certificates use frozen local images only


class ImagesUnavailable(Exception):
    pass


def utm(url: str) -> str:
    name = get_settings().unsplash_app_name or "pramaan"
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source={name}&utm_medium=referral"


async def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    """The one place that talks to Unsplash (tests replace it). Needs the server-side key."""
    key = get_settings().unsplash_access_key.strip()
    if not key:
        raise ImagesUnavailable("UNSPLASH_ACCESS_KEY is not set")
    url = path if path.startswith("http") else f"{API}{path}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params, headers={"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
        resp.raise_for_status()
        return resp.json()


async def search_candidates(query: str, *, color: str = "", per_page: int = 12) -> list[dict[str, Any]]:
    """Candidates for an admin to look at. Not stored, not shown publicly."""
    params: dict[str, Any] = {"query": query, "orientation": "landscape", "content_filter": "high", "per_page": min(per_page, 20)}
    if color:
        params["color"] = color
    data = await _get("/search/photos", params)
    out = []
    for p in data.get("results", []):
        out.append({
            "unsplash_id": p["id"], "url_raw": p["urls"]["raw"], "width": p.get("width", 0), "height": p.get("height", 0),
            "blur_hash": p.get("blur_hash") or "", "dominant_color": p.get("color") or "",
            "alt_text": p.get("alt_description") or p.get("description") or "",
            "photographer_name": p["user"]["name"], "photographer_url": p["user"]["links"]["html"],
            "photo_url": p["links"]["html"], "download_location": p["links"]["download_location"],
        })
    return out


async def approve(session: AsyncSession, cand: dict[str, Any], *, sector: str, purpose: str, approved_by) -> ImageAsset:
    """A human approved this image: record it and trigger Unsplash's download endpoint ONCE."""
    if sector not in SECTORS:
        raise ValueError("unknown sector")
    if purpose not in PURPOSES:
        raise ValueError("purpose must be tile, cover or empty")
    existing = (await session.execute(select(ImageAsset).where(ImageAsset.unsplash_id == cand["unsplash_id"]))).scalar_one_or_none()
    if existing is not None:
        existing.active, existing.sector, existing.purpose = True, sector, purpose
        return existing
    row = ImageAsset(
        source="unsplash_api", unsplash_id=cand["unsplash_id"], sector=sector, purpose=purpose, url_raw=cand["url_raw"],
        width=cand.get("width", 0), height=cand.get("height", 0), blur_hash=cand.get("blur_hash", ""),
        dominant_color=cand.get("dominant_color", ""), alt_text=cand.get("alt_text", "")[:300],
        photographer_name=cand["photographer_name"], photographer_url=cand["photographer_url"], photo_url=cand["photo_url"],
        download_location=cand["download_location"], approved_by=approved_by, approved_at=datetime.now(timezone.utc), active=True,
    )
    try:
        await _get(cand["download_location"])  # the guideline's "download" ping: once, on approval
        row.download_triggered_at = datetime.now(timezone.utc)
    except (httpx.HTTPError, ImagesUnavailable) as exc:
        log.warning("Unsplash download ping failed for %s: %s", cand["unsplash_id"], exc)
    session.add(row)
    return row


def public_view(row: ImageAsset) -> dict[str, Any]:
    """What the browser gets: the hotlink, a placeholder colour, and a ready-made attribution."""
    return {
        "id": str(row.id), "sector": row.sector, "purpose": row.purpose, "url_raw": row.url_raw,
        "width": row.width, "height": row.height, "blur_hash": row.blur_hash, "dominant_color": row.dominant_color,
        "alt": row.alt_text or f"{row.sector} photograph",
        "attribution": {
            "photographer": row.photographer_name, "photographer_url": utm(row.photographer_url),
            "photo_url": utm(row.photo_url), "unsplash_url": utm("https://unsplash.com/"),
        },
    }


async def for_sector(session: AsyncSession, sector: str, purpose: str | None = None) -> list[dict[str, Any]]:
    stmt = select(ImageAsset).where(ImageAsset.sector == sector, ImageAsset.active.is_(True)).order_by(ImageAsset.approved_at.desc())
    if purpose:
        stmt = stmt.where(ImageAsset.purpose == purpose)
    return [public_view(r) for r in (await session.execute(stmt)).scalars().all()]
