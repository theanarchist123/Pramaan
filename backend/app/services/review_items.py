"""Review-queue helpers shared by the API and the agent graphs."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, Profile, ReviewItem


async def open_document_review(session: AsyncSession, profile: Profile, doc: Document, flags: list[str]) -> None:
    """One open 'document' review item per profile; a newer upload refreshes it instead of piling up duplicates."""
    ex = doc.extracted or {}
    details = {
        "kind": "document", "document_id": str(doc.id), "filename": doc.filename, "flags": list(flags),
        "title": ex.get("title", ""), "issuer": ex.get("issuer", ""), "notes": ex.get("notes", ""),
    }
    reason = "Document needs attention: " + (", ".join(flags) if flags else f"low match score {(doc.match_score or 0.0):.2f}")
    open_items = (
        await session.execute(select(ReviewItem).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open"))
    ).scalars().all()
    existing = next((i for i in open_items if (i.details or {}).get("kind") == "document"), None)
    if existing:
        existing.reason, existing.confidence, existing.details = reason, doc.match_score or 0.0, details
    else:
        session.add(ReviewItem(profile_id=profile.id, reason=reason, confidence=doc.match_score or 0.0, details=details))


async def open_reason(session: AsyncSession, profile_id, reason: str, details: dict | None = None) -> None:
    """Make sure a person will look at this profile: refresh its open item, or open one. The reason is shown to the reviewer."""
    item = (await session.execute(select(ReviewItem).where(ReviewItem.profile_id == profile_id, ReviewItem.status == "open"))).scalars().first()
    if item is not None:
        item.reason = reason[:300]
        if details:
            item.details = {**(item.details or {}), **details}
    else:
        session.add(ReviewItem(profile_id=profile_id, reason=reason[:300], confidence=0.0, details=details or {}))
