"""Applies an interview turn to a profile, with normalisation so agent output can't corrupt data."""

from __future__ import annotations

import re
import secrets
from difflib import get_close_matches
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.schemas import ExtractedClaim, ProfileDelta, SaathiTurn
from app.agents.textutil import normalize
from app.domain import INDIAN_STATES, SECTORS
from app.models import Claim, Evidence, Profile

async def reload_profile(session: AsyncSession, profile_id) -> Profile:
    """Fresh copy with claims + evidence eagerly loaded (async sessions can't lazy-load)."""
    stmt = (
        select(Profile)
        .where(Profile.id == profile_id)
        .options(selectinload(Profile.claims).selectinload(Claim.evidence))
        .execution_options(populate_existing=True)
    )
    return (await session.execute(stmt)).scalar_one()


PLACEHOLDER_NAME = "New Profile"
GREETING = (
    "Namaste! I'm Saathi. I'll help you build your Pramaan profile — just talk to me, no forms. "
    "May I know your full name?"
)


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
    return f"{base[:60]}-{secrets.token_hex(4)}"


def normalize_state(value: str | None) -> str | None:
    if not value:
        return None
    match = get_close_matches(value.strip().lower(), [s.lower() for s in INDIAN_STATES], n=1, cutoff=0.85)
    return next((s for s in INDIAN_STATES if s.lower() == match[0]), None) if match else None


def normalize_sector(value: str | None) -> str | None:
    if not value:
        return None
    match = get_close_matches(value.strip().lower(), [s.lower() for s in SECTORS], n=1, cutoff=0.7)
    return next((s for s in SECTORS if s.lower() == match[0]), "Other") if match else "Other"


def profile_context(profile: Profile) -> dict[str, Any]:
    """What the interviewer is told about the current draft (also the mock's input)."""
    return {
        "name_known": profile.full_name != PLACEHOLDER_NAME,
        "full_name": profile.full_name if profile.full_name != PLACEHOLDER_NAME else None,
        "headline": profile.headline or None,
        "sector": profile.sector or None,
        "state": profile.state or None,
        "city": profile.city or None,
        "bio": profile.bio or None,
        "institutions": profile.institutions,
        "custom": dict(profile.custom or {}),
        "claims_count": len(profile.claims),
        "claims": [{"field": c.field, "value": c.value, "year": c.year} for c in profile.claims],
    }


def apply_delta(profile: Profile, delta: ProfileDelta, defs=()) -> None:
    if delta.full_name and profile.full_name == PLACEHOLDER_NAME and len(delta.full_name.strip()) >= 2:
        profile.full_name = delta.full_name.strip()[:255]
        profile.slug = _slug(profile.full_name)  # safe: still a draft, nothing is public yet
    if delta.headline:
        profile.headline = delta.headline.strip()[:300]
    if (sector := normalize_sector(delta.sector)):
        profile.sector = sector
    if (state := normalize_state(delta.state)):
        profile.state = state
    if delta.city:
        profile.city = delta.city.strip()[:120]
    if delta.bio:
        profile.bio = delta.bio.strip()[:5000]
    if delta.languages:
        profile.languages = sorted({*profile.languages, *[l.strip() for l in delta.languages if l.strip()]})
    if delta.custom and defs:
        from app.services.fields import clean_values

        by_key = {d.key: d for d in defs}
        raw = {}
        for item in delta.custom:
            d = by_key.get(item.key)
            if d is not None:
                raw[item.key] = [x.strip() for x in re.split(r"[,;]", item.value)] if d.type == "list" else item.value
        # AI output is untrusted: invalid values are silently dropped, never stored.
        profile.custom = {**(profile.custom or {}), **clean_values(raw, list(defs), strict=False)}
    if delta.institutions:
        profile.institutions = sorted(
            {*profile.institutions, *[i.strip() for i in delta.institutions if i.strip()]}
        )


def literal_span(message: str, quote: str) -> str:
    """The stretch of `message` that `quote` points at, taken from the MESSAGE itself (its own casing), or "" if the quote is not a literal
    stretch of it. A model's rewording or a made-up quote therefore never becomes "what the person said" (fact capture, M-03)."""
    q = quote.strip()
    if len(q) < 4 or not message:
        return ""
    at = message.lower().find(q.lower())
    return message[at : at + len(q)] if at >= 0 else ""


def add_claims(
    profile: Profile,
    claims: list[ExtractedClaim],
    *,
    evidence_kind: str = "chat",
    evidence_url: str = "",
    quotes: list[str] | None = None,
) -> list[Claim]:
    """Adds new claims as unverified 'self' claims; duplicates are ignored."""
    existing = {normalize(c.value) for c in profile.claims}
    created: list[Claim] = []
    for i, item in enumerate(claims):
        key = normalize(item.value)
        if not key or key in existing:
            continue
        existing.add(key)
        claim = Claim(
            profile_id=profile.id, field=item.field, value=item.value.strip()[:2000],
            year=item.year if item.year and 1800 <= item.year <= 2200 else None,
            status="self", confidence=0.2,
        )
        quote = (quotes[i] if quotes and i < len(quotes) and quotes[i] else item.value)[:1000]
        claim.evidence.append(Evidence(kind=evidence_kind, url=evidence_url, quote=quote))
        profile.claims.append(claim)
        created.append(claim)
    return created


def apply_turn(profile: Profile, turn: SaathiTurn, defs=(), message: str = "") -> list[Claim]:
    apply_delta(profile, turn.profile_delta, defs)
    # The chat evidence for each new claim is the person's own words when the model pointed at a real stretch of their message.
    return add_claims(profile, turn.new_claims, quotes=[literal_span(message, c.source_quote) for c in turn.new_claims])
