"""Automatic photograph seeding: pick and approve a tile photo and a cover photo for every field, safely, within Unsplash's hourly limit.

The owner asked for this to happen by itself instead of a person approving each photo. What stays safe regardless:
  * HOTLINK ONLY: only https://images.unsplash.com/ URLs are accepted; nothing is downloaded or re-hosted.
  * NEVER PEOPLE: a candidate whose description mentions a person, a face, a group or a profession shown at work is skipped (a stock photo of a
    person next to a real person's record would read as that person's photo). Search queries are landscapes, objects, buildings, textures.
  * Unsplash's download ping is made once per approved photo, as their guidelines require.
  * It never touches a slot that already has an active photo, never reuses a photo, and stops before the request budget runs out
    (a demo-mode key allows 50 requests an hour). Re-running continues where it stopped.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ImageAsset

log = logging.getLogger("pramaan.imageseed")
PURPOSES = ("tile", "cover")

# Queries are things, places and textures; each field has a few so a blocked or exhausted query does not stall it.
SECTOR_QUERIES: dict[str, list[str]] = {
    "Energy": ["wind turbines on a hill", "solar panels field", "power transmission towers sunset"],
    "Agriculture": ["rice terraces", "wheat field sunrise", "tea plantation hills"],
    "Healthcare": ["laboratory medical equipment", "empty hospital corridor", "stethoscope on a table"],
    "Technology": ["circuit board close up", "server room corridor", "fiber optic cables"],
    "Science": ["laboratory glassware", "microscope on a bench", "telescope observatory dome"],
    "Media": ["printing press", "vintage camera on a table", "broadcast microphone studio"],
    "Business": ["city skyline financial district", "glass office building", "stock exchange building facade"],
    "Education": ["library shelves of books", "empty classroom desks", "university building courtyard"],
    "Literature": ["stack of old books", "typewriter on a desk", "quill and ink"],
    "Social Work": ["community garden", "village street india", "donation boxes"],
    "Arts & Culture": ["indian temple carving", "rangoli colours", "pottery wheel clay"],
    "Sports": ["running track lanes", "empty stadium seats", "cricket bat and ball"],
    "Law": ["gavel and law books", "courthouse columns", "justice statue scales"],
    "Public Service": ["government building india", "parliament building", "city hall facade"],
}

# Whole words only (so "manhattan" or "mantis" do not trip "man"). Deliberately broad: a false skip costs nothing, a person's photo costs a lot.
_PEOPLE = re.compile(
    r"\b(man|men|woman|women|person|people|persons|girl|girls|boy|boys|child|children|kid|kids|baby|face|faces|portrait|portraits|selfie|"
    r"student|students|teacher|doctor|doctors|nurse|nurses|surgeon|patient|patients|athlete|athletes|player|players|runner|runners|"
    r"team|crowd|crowds|farmer|farmers|worker|workers|scientist|scientists|lawyer|judge|couple|family|smiling|posing|hand|hands|"
    r"human|humans|silhouette|dancer|dancers|musician|musicians|monk|monks|priest|bride|groom|"
    # religious figures and iconography are not something a registry should show on its field tiles
    r"deity|deities|god|gods|goddess|idol|idols|buddha|buddhist|hindu|christian|islamic|muslim|jesus|shiva|ganesh|krishna|mosque|church)\b",
    re.I,
)

Search = Callable[[str], Awaitable[list[dict[str, Any]]]]
Ping = Callable[[str], Awaitable[None]]


def all_queries() -> list[str]:
    return [q for qs in SECTOR_QUERIES.values() for q in qs]


def mentions_people(text: str) -> bool:
    return bool(_PEOPLE.search(text or ""))


def acceptable(c: dict[str, Any]) -> bool:
    url = c.get("url_raw", "")
    needed = ("unsplash_id", "url_raw", "photographer_name", "photographer_url", "photo_url", "download_location")
    return (
        all(c.get(k) for k in needed)
        and url.startswith("https://images.unsplash.com/")
        and not mentions_people(c.get("alt_text", ""))
        and (c.get("width") or 0) >= (c.get("height") or 0)  # landscape, so a band or a tile crops well
    )


async def seed_images(
    session: AsyncSession, *, search: Search, ping: Ping, budget: int = 40, dry_run: bool = False, cache: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Fill every empty (field, slot). `search(query)` returns Unsplash candidates and `ping(download_location)` makes the download call; each costs one
    request from `budget`. `cache` (query -> candidates) lets a dry run's searches be reused by the real run."""
    cache = {} if cache is None else cache
    used = 0
    report: dict[str, Any] = {"approved": 0, "already_filled": 0, "requests_used": 0, "stopped_early": False, "would_approve": [], "chosen": [], "skipped_slots": []}

    active = (await session.execute(select(ImageAsset).where(ImageAsset.active.is_(True)))).scalars().all()
    filled = {(a.sector, a.purpose) for a in active}
    taken = {a.unsplash_id for a in (await session.execute(select(ImageAsset))).scalars().all()}

    for sector, queries in SECTOR_QUERIES.items():
        for purpose in PURPOSES:
            if (sector, purpose) in filled:
                report["already_filled"] += 1
                continue
            picked: dict[str, Any] | None = None
            for q in queries:
                if q not in cache:
                    if used + 1 + (0 if dry_run else 1) > budget:
                        report["stopped_early"] = True
                        break
                    cache[q] = await search(q)
                    used += 1
                picked = next((c for c in cache[q] if acceptable(c) and c["unsplash_id"] not in taken), None)
                if picked:
                    break
            if picked is None:
                if report["stopped_early"]:
                    break
                report["skipped_slots"].append(f"{sector}/{purpose}")
                continue
            if not dry_run and used + 1 > budget:
                report["stopped_early"] = True
                break
            taken.add(picked["unsplash_id"])
            entry = {"sector": sector, "purpose": purpose, "unsplash_id": picked["unsplash_id"], "photographer": picked["photographer_name"], "alt": picked.get("alt_text", "")}
            if dry_run:
                report["would_approve"].append(entry)
                continue
            row = ImageAsset(
                source="unsplash_api", unsplash_id=picked["unsplash_id"], sector=sector, purpose=purpose, url_raw=picked["url_raw"],
                width=picked.get("width", 0), height=picked.get("height", 0), blur_hash=picked.get("blur_hash", ""),
                dominant_color=picked.get("dominant_color", ""), alt_text=(picked.get("alt_text") or "")[:300],
                photographer_name=picked["photographer_name"], photographer_url=picked["photographer_url"], photo_url=picked["photo_url"],
                download_location=picked["download_location"], approved_by=None, approved_at=datetime.now(timezone.utc), active=True,
            )
            try:
                await ping(picked["download_location"])  # Unsplash's required "download" call, once per approved photo
                row.download_triggered_at = datetime.now(timezone.utc)
            except Exception as exc:  # noqa: BLE001 - a failed ping must not lose the approval; it is recorded as not triggered
                log.warning("download ping failed for %s: %s", picked["unsplash_id"], type(exc).__name__)
            used += 1
            session.add(row)
            report["approved"] += 1
            report["chosen"].append(entry)
        if report["stopped_early"]:
            break
    report["requests_used"] = used
    return report
