"""Directory intelligence: indexing (embeddings), Setu's relationship graph, and Khoji's search."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from itertools import combinations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.textutil import normalize
from app.models import Edge, Profile, ProfileEmbedding
from app.services.embeddings import get_embedder

VERIFIED = ("web", "document", "human", "issuer")


def profile_text(p: Profile, defs: list | None = None) -> str:
    """What a person 'means' to the search engine: only facts that are in their verified profile."""
    claims = [c.value for c in p.claims if c.status in VERIFIED]
    extra = []
    for d in defs or []:
        v = (p.custom or {}).get(d.key)
        if d.searchable and v not in (None, "", []):
            extra.append(f"{d.label}: {', '.join(v) if isinstance(v, list) else v}")
    parts = [
        p.full_name, p.headline, p.sector, p.state, p.city, p.bio,
        "Institutions: " + ", ".join(p.institutions) if p.institutions else "",
        "Achievements: " + "; ".join(claims) if claims else "",
        ". ".join(extra),
    ]
    return ". ".join(x for x in parts if x)


# --------------------------------------------------------------------------- #
# Indexing
# --------------------------------------------------------------------------- #
async def index_profile(session: AsyncSession, profile: Profile) -> None:
    from app.services.fields import active_definitions

    text = profile_text(profile, await active_definitions(session))
    digest = hashlib.sha256(text.encode()).hexdigest()
    row = await session.get(ProfileEmbedding, profile.id)
    if row is not None and row.text_hash == digest:
        return
    [vec] = await get_embedder().embed([text])
    if row is None:
        session.add(ProfileEmbedding(profile_id=profile.id, embedding=vec, text_hash=digest))
    else:
        row.embedding, row.text_hash = vec, digest


async def reindex_all(session: AsyncSession) -> int:
    profiles = (
        await session.execute(select(Profile).where(Profile.status == "approved"))
    ).scalars().all()
    from app.services.fields import active_definitions

    defs = await active_definitions(session)
    texts = [profile_text(p, defs) for p in profiles]
    vecs = await get_embedder().embed(texts) if texts else []
    await session.execute(delete(ProfileEmbedding))
    for p, t, v in zip(profiles, texts, vecs):
        session.add(ProfileEmbedding(profile_id=p.id, embedding=v, text_hash=hashlib.sha256(t.encode()).hexdigest()))
    return len(profiles)


# --------------------------------------------------------------------------- #
# Setu: relationship graph
# --------------------------------------------------------------------------- #
EDGE_WEIGHT = {"alumni": 1.0, "org": 0.9, "city": 0.5, "sector": 0.35}


def _edges_for(a: Profile, b: Profile) -> list[tuple[str, float, str]]:
    out: list[tuple[str, float, str]] = []
    mine = {normalize(i): i for i in a.institutions if normalize(i)}
    theirs = {normalize(i) for i in b.institutions}
    shared = [mine[k] for k in sorted(set(mine) & theirs)]
    if shared:
        # One edge per (pair, type) — more shared institutions make the tie stronger, not duplicated.
        weight = min(EDGE_WEIGHT["alumni"] + 0.25 * (len(shared) - 1), 1.5)
        out.append(("alumni", weight, "Both associated with " + " and ".join(shared)))
    if a.city and a.city.lower() == b.city.lower():
        out.append(("city", EDGE_WEIGHT["city"], f"Both based in {a.city}"))
    if a.sector and a.sector == b.sector and a.state and a.state == b.state:
        out.append(("sector", EDGE_WEIGHT["sector"], f"Both in {a.sector}, {a.state}"))
    return out


async def rebuild_graph(session: AsyncSession) -> int:
    profiles = (
        await session.execute(select(Profile).where(Profile.status == "approved").order_by(Profile.id))
    ).scalars().all()
    await session.execute(delete(Edge))
    n = 0
    for a, b in combinations(profiles, 2):
        a_id, b_id = sorted([a.id, b.id], key=str)
        for etype, weight, ev in _edges_for(a, b):
            session.add(Edge(a_id=a_id, b_id=b_id, type=etype, weight=weight, evidence=ev))
            n += 1
    return n


_SETU_LABEL = {"co_author": "Co-authored", "co_founder": "Co-founded", "board": "Same board", "joint_project": "Joint project"}


async def graph_payload(session: AsyncSession) -> dict:
    profiles = (
        await session.execute(select(Profile).where(Profile.status == "approved"))
    ).scalars().all()
    ids = {p.id for p in profiles}
    edges = (await session.execute(select(Edge))).scalars().all()
    from app.models import SetuEdge

    setu_edges = (await session.execute(select(SetuEdge))).scalars().all()
    return {
        "nodes": [
            {"id": str(p.id), "slug": p.slug, "name": p.full_name, "sector": p.sector, "state": p.state,
             "headline": p.headline, "demo": p.is_demo}
            for p in profiles
        ],
        "links": [
            {"source": str(e.a_id), "target": str(e.b_id), "type": e.type, "weight": e.weight, "why": e.evidence}
            for e in edges if e.a_id in ids and e.b_id in ids
        ]
        + [
            # Setu's validated connections: the person's own words travel with the edge
            {"source": str(e.a_id), "target": str(e.b_id), "type": "collab", "weight": 0.9,
             "why": f"{_SETU_LABEL[e.kind]}: \u201c{e.span}\u201d"}
            for e in setu_edges if e.a_id in ids and e.b_id in ids
        ],
    }


# --------------------------------------------------------------------------- #
# Khoji: search
# --------------------------------------------------------------------------- #
@dataclass
class Hit:
    profile: Profile
    score: float
    reasons: list[str] = field(default_factory=list)


def _reasons(p: Profile, query: str, state: str | None, sector: str | None) -> list[str]:
    """Plain-language 'why this person matched', grounded in fields we actually have."""
    reasons: list[str] = []
    if state and p.state == state:
        reasons.append(f"Based in {state}")
    if sector and p.sector == sector:
        reasons.append(f"Works in {sector}")
    q_tokens = {t for t in normalize(query).split() if len(t) > 3}
    for c in p.claims:
        if c.status in VERIFIED and q_tokens & set(normalize(c.value).split()):
            label = {"document": "document verified", "human": "confirmed by a reviewer", "issuer": "verified by issuer"}.get(c.status, "public evidence")
            reasons.append(f"{c.value} ({label})")
            break
    for inst in p.institutions:
        if q_tokens & set(normalize(inst).split()):
            reasons.append(f"Associated with {inst}")
            break
    if q_tokens & set(normalize(p.headline + " " + p.bio).split()) and len(reasons) < 3:
        reasons.append(f"Profile mentions: {p.headline or p.sector}")
    return reasons[:4]


SECTOR_BOOST = 0.08


async def search(
    session: AsyncSession,
    query: str,
    *,
    state: str | None = None,
    sector: str | None = None,
    boost_sector: str | None = None,
    limit: int = 12,
) -> list[Hit]:
    """`state`/`sector` are hard filters (explicit user choices). `boost_sector` is a soft nudge for a
    sector the language model merely *inferred*, since an inferred field is a guess and must never hide people."""
    [qvec] = await get_embedder().embed([query])
    dist = ProfileEmbedding.embedding.cosine_distance(qvec)
    stmt = (
        select(Profile, dist.label("d"))
        .join(ProfileEmbedding, ProfileEmbedding.profile_id == Profile.id)
        .where(Profile.status == "approved")
        .order_by(dist)
        .limit(limit * 2 if boost_sector else limit)
    )
    if state:
        stmt = stmt.where(Profile.state == state)
    if sector:
        stmt = stmt.where(Profile.sector == sector)
    rows = (await session.execute(stmt)).all()
    hits = []
    for p, d in rows:
        score = max(0.0, 1 - float(d)) + (SECTOR_BOOST if boost_sector and p.sector == boost_sector else 0.0)
        hits.append(Hit(p, round(score, 3), _reasons(p, query, state, sector or boost_sector)))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


async def counts(session: AsyncSession) -> dict:
    by_state = (
        await session.execute(
            select(Profile.state, func.count()).where(Profile.status == "approved", Profile.state != "").group_by(Profile.state)
        )
    ).all()
    by_sector = (
        await session.execute(
            select(Profile.sector, func.count()).where(Profile.status == "approved", Profile.sector != "").group_by(Profile.sector)
        )
    ).all()
    by_pair = (
        await session.execute(
            select(Profile.state, Profile.sector, func.count())
            .where(Profile.status == "approved", Profile.state != "", Profile.sector != "")
            .group_by(Profile.state, Profile.sector)
        )
    ).all()
    total = sum(c for _, c in by_state)
    return {
        "total": total,
        "by_state": {s: c for s, c in by_state},
        "by_sector": {s: c for s, c in by_sector},
        "by_state_sector": [{"state": s, "sector": sec, "count": c} for s, sec, c in by_pair],
    }


async def update_graph_for(session: AsyncSession, profile: Profile) -> int:
    """Incremental Setu: relate one newly-approved profile to everyone else (no full O(n²) rebuild)."""
    await session.execute(delete(Edge).where((Edge.a_id == profile.id) | (Edge.b_id == profile.id)))
    others = (
        await session.execute(select(Profile).where(Profile.status == "approved", Profile.id != profile.id))
    ).scalars().all()
    n = 0
    for other in others:
        a_id, b_id = sorted([profile.id, other.id], key=str)
        for etype, weight, ev in _edges_for(profile, other):
            session.add(Edge(a_id=a_id, b_id=b_id, type=etype, weight=weight, evidence=ev))
            n += 1
    return n


async def on_approved(session: AsyncSession, profile: Profile) -> None:
    """Everything the directory needs when a profile becomes public."""
    await index_profile(session, profile)
    await update_graph_for(session, profile)
