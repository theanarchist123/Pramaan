"""Conversational onboarding: Saathi interview, public-source discovery, documents, verification."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import discovery as discovery_agent
from app.agents import lipik, saathi
from app.agents.events import recent_events, start_run
from app.agents.schemas import DiscoveryDraft, ExtractedClaim
from app import jobs
from app.config import get_settings
from app.core.locks import LockBusy, short_lock
from app.core.ratelimit import check_rate_limit
from app.db import get_session
from app.deps import Principal, require_scope, require_verified_email
from app.llm.client import LLMError, LLMRefusal, get_llm
from app.models import AgentRun, ChatMessage, Consent, Document, Profile, ReviewItem
from app.schemas import ClaimOut, ProfileOut
from app.services import fields as fields_svc
from app.services import onboarding as svc

router = APIRouter(prefix="/v1/onboarding", tags=["onboarding"])
EDITABLE = ("draft", "rejected")
_EXT = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif",
    "application/pdf": ".pdf", "text/plain": ".txt",
}


# ----- helpers -----
async def _limit_llm(principal: Principal, per_minute: int = 40) -> None:
    ok, _ = await check_rate_limit(f"llm:{principal.user.id}", per_minute)
    if not ok:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Slow down a little — too many AI requests")


async def _owned(session: AsyncSession, profile_id: uuid.UUID, principal: Principal) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None or not (principal.is_admin or profile.owner_id == principal.user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return profile


def _require_editable(profile: Profile) -> None:
    if profile.status not in EDITABLE:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Profile is '{profile.status}' and can't be edited by chat right now"
        )


# ----- start -----
class StartIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    consent_public_listing: bool = False
    consent_web_research: bool = False


class StartOut(BaseModel):
    profile: ProfileOut
    greeting: str
    llm_mode: str


@router.post("/start", response_model=StartOut, status_code=status.HTTP_201_CREATED)
async def start(
    body: StartIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    name = (body.full_name or "").strip() or svc.PLACEHOLDER_NAME
    profile = Profile(owner_id=principal.user.id, slug=svc._slug(name), full_name=name)
    session.add(profile)
    await session.flush()
    session.add(Consent(
        profile_id=profile.id, kind="public_listing", granted=body.consent_public_listing,
        text="I agree to have my verified profile listed in the public Pramaan registry.",
    ))
    session.add(Consent(
        profile_id=profile.id, kind="web_research", granted=body.consent_web_research,
        text="Pramaan may look up public information about me to pre-fill and verify my profile.",
    ))
    session.add(ChatMessage(profile_id=profile.id, role="assistant", content=svc.GREETING))
    await session.commit()
    await session.refresh(profile)
    return StartOut(profile=ProfileOut.model_validate(profile), greeting=svc.GREETING, llm_mode=get_llm().mode)


# ----- chat -----
class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class TurnOut(BaseModel):
    reply: str
    detected_language: str
    profile: ProfileOut
    new_claims: list[ClaimOut]
    missing: list[str]
    ready_to_submit: bool
    run_id: uuid.UUID


@router.post("/{profile_id}/message", response_model=TurnOut)
async def message(
    profile_id: uuid.UUID,
    body: MessageIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    await _limit_llm(principal)
    profile = await _owned(session, profile_id, principal)
    _require_editable(profile)

    history_rows = (
        await session.execute(
            select(ChatMessage).where(ChatMessage.profile_id == profile.id).order_by(ChatMessage.id)
        )
    ).scalars().all()
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    defs = await fields_svc.active_definitions(session)
    ctx = await start_run("onboarding_turn", profile.id)
    try:
        turn = await saathi.interview_turn(
            ctx, profile=svc.profile_context(profile), history=history, user_text=body.text, fields=defs
        )
    except LLMRefusal:
        await ctx.finish("failed", "Model declined")
        raise HTTPException(422, "I can't help with that message. Could you rephrase?") from None
    except LLMError as exc:
        await ctx.finish("failed", "Model unavailable")
        raise HTTPException(502, "The assistant is temporarily unavailable. Please try again.") from exc

    session.add(ChatMessage(profile_id=profile.id, role="user", content=body.text))
    created = svc.apply_turn(profile, turn, defs, message=body.text)
    session.add(ChatMessage(profile_id=profile.id, role="assistant", content=turn.reply))
    await session.commit()
    created_ids = {c.id for c in created}
    profile = await svc.reload_profile(session, profile.id)
    await ctx.finish("done", f"{len(created)} claim(s) captured")

    return TurnOut(
        reply=turn.reply,
        detected_language=turn.detected_language,
        profile=ProfileOut.model_validate(profile),
        new_claims=[ClaimOut.model_validate(c) for c in profile.claims if c.id in created_ids],
        missing=turn.missing,
        ready_to_submit=turn.ready_to_submit,
        run_id=ctx.run_id,
    )


@router.get("/{profile_id}/messages")
async def messages(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    await _owned(session, profile_id, principal)
    rows = (
        await session.execute(
            select(ChatMessage).where(ChatMessage.profile_id == profile_id).order_by(ChatMessage.id)
        )
    ).scalars().all()
    return [{"role": m.role, "content": m.content, "at": m.created_at} for m in rows]


# ----- "Is this you?" -----
class DiscoverIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)


@router.post("/discover")
async def discover(
    body: DiscoverIn,
    principal: Principal = Depends(require_scope("profiles:write")),
):
    await _limit_llm(principal, 10)
    ctx = await start_run("discover")
    try:
        result = await discovery_agent.discover(ctx, body.name.strip())
    except (LLMError, LLMRefusal):
        await ctx.finish("failed", "Model unavailable")
        return {"found": False, "run_id": str(ctx.run_id)}
    await ctx.finish("done", "match found" if result.found else "no match")
    return {**result.model_dump(), "run_id": str(ctx.run_id)}


class ApplyDiscoveryIn(BaseModel):
    draft: DiscoveryDraft
    source_url: str = Field(max_length=600)


@router.post("/{profile_id}/apply-discovery", response_model=ProfileOut)
async def apply_discovery(
    profile_id: uuid.UUID,
    body: ApplyDiscoveryIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    """The person said 'yes, that's me'. Claims enter as unverified: Pariksha must still prove them."""
    profile = await _owned(session, profile_id, principal)
    _require_editable(profile)
    consent = (
        await session.execute(
            select(Consent).where(Consent.profile_id == profile.id, Consent.kind == "web_research")
            .order_by(Consent.created_at.desc())
        )
    ).scalars().first()
    if not consent or not consent.granted:
        raise HTTPException(409, "Consent to public-source lookup is required")

    d = body.draft
    from app.agents.schemas import ProfileDelta

    svc.apply_delta(profile, ProfileDelta(headline=d.headline or None, sector=d.sector or None,
                                          state=d.state or None, city=d.city or None))
    svc.add_claims(
        profile,
        [ExtractedClaim(field=c.field, value=c.value, year=c.year) for c in d.claims],
        evidence_kind="web", evidence_url=body.source_url, quotes=[c.source_quote for c in d.claims],
    )
    await session.commit()
    return await svc.reload_profile(session, profile.id)


async def _open_document_review(session: AsyncSession, profile: Profile, doc: Document, flags: list[str]) -> None:
    """One open 'document' review item per profile; a newer upload refreshes it instead of piling up duplicates."""
    ex = doc.extracted or {}
    details = {
        "kind": "document", "document_id": str(doc.id), "filename": doc.filename, "flags": list(flags),
        "title": ex.get("title", ""), "issuer": ex.get("issuer", ""), "notes": ex.get("notes", ""),
    }
    reason = "Document needs attention: " + (", ".join(flags) if flags else f"low match score {doc.match_score:.2f}")
    open_items = (
        await session.execute(select(ReviewItem).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open"))
    ).scalars().all()
    existing = next((i for i in open_items if (i.details or {}).get("kind") == "document"), None)
    if existing:
        existing.reason, existing.confidence, existing.details = reason, doc.match_score or 0.0, details
    else:
        session.add(ReviewItem(profile_id=profile.id, reason=reason, confidence=doc.match_score or 0.0, details=details))


@router.post("/{profile_id}/request-review", status_code=status.HTTP_201_CREATED)
async def request_review(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    """Ask a human to look at this profile (e.g. after a document the reader couldn't confirm)."""
    profile = await _owned(session, profile_id, principal)
    open_items = (
        await session.execute(select(ReviewItem).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open"))
    ).scalars().all()
    if open_items:
        return {"status": "already_in_queue"}
    session.add(ReviewItem(
        profile_id=profile.id, reason="Applicant asked for a manual review", confidence=0.0, details={"kind": "requested"},
    ))
    await session.commit()
    return {"status": "queued"}


# ----- documents (Lipik) -----
@router.post("/{profile_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    profile_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    await _limit_llm(principal, 15)
    profile = await _owned(session, profile_id, principal)
    content_type = (file.content_type or "").lower()
    if content_type not in _EXT:
        raise HTTPException(415, "Upload a PNG, JPG, WebP, GIF, PDF or plain-text file")
    data = await file.read(lipik.MAX_BYTES + 1)
    if len(data) > lipik.MAX_BYTES:
        raise HTTPException(413, "File is larger than 8 MB")

    # Store under a server-generated name — never trust the client's filename for paths.
    folder = get_settings().data_dir / "uploads" / str(profile.id)
    folder.mkdir(parents=True, exist_ok=True)
    stored = folder / f"{uuid.uuid4().hex}{_EXT[content_type]}"
    stored.write_bytes(data)
    display_name = re.sub(r"[^\w.\- ]", "_", file.filename or "document")[:120]

    doc = Document(profile_id=profile.id, filename=display_name, content_type=content_type, path=str(stored))
    session.add(doc)
    await session.flush()

    ctx = await start_run("document_intake", profile.id)
    try:
        result = await lipik.read_document(ctx, session, profile, doc, content_type, data)
    except lipik.DocumentRejected as exc:
        await ctx.finish("failed", str(exc))
        await session.rollback()
        stored.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except (LLMError, LLMRefusal) as exc:
        await ctx.finish("failed", "Model unavailable")
        await session.rollback()
        stored.unlink(missing_ok=True)
        raise HTTPException(502, "Document reader is temporarily unavailable") from exc
    needs_review = bool(result.flags) or (doc.match_score or 0) < 0.95
    if needs_review:
        # A document the machine can't vouch for must reach a person — even if the profile is already published.
        await _open_document_review(session, profile, doc, result.flags)
    await session.commit()
    await ctx.finish("done", f"{result.upgraded_claims} claim(s) upgraded; flags: {result.flags or 'none'}")
    return {
        "sent_to_review": needs_review,
        "document_id": str(doc.id),
        "extracted": {k: v for k, v in doc.extracted.items() if k != "sha256"},
        "match_score": doc.match_score,
        "flags": result.flags,
        "claims_verified_by_document": result.upgraded_claims,
        "run_id": str(ctx.run_id),
    }


# ----- verification -----

async def _start_verification(session: AsyncSession, profile: Profile) -> dict:
    # Idempotent: a verification already running for this profile is returned, never started a second time
    # (a double-click, a retry or two tabs used to produce two complete agent runs back to back).
    running = (
        await session.execute(
            select(AgentRun).where(
                AgentRun.workflow == "verify_profile", AgentRun.profile_id == profile.id, AgentRun.status == "running",
                AgentRun.started_at > datetime.now(timezone.utc) - timedelta(minutes=10),
            ).order_by(AgentRun.started_at.desc())
        )
    ).scalars().first()
    if running is not None:
        return {"run_id": str(running.id), "status": "already_running"}
    if profile.status not in ("draft", "rejected", "pending_review"):
        raise HTTPException(409, f"Profile is already '{profile.status}'")

    if profile.status != "pending_review":
        profile.status = "pending_review"  # locks chat edits while agents work
        profile.decision_basis = ""
        already_open = (
            await session.execute(
                select(ReviewItem.id).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open")
            )
        ).first()
        if not already_open:  # e.g. a flagged document already queued: Prahari will update that item
            session.add(ReviewItem(profile_id=profile.id, reason="Automated verification in progress", confidence=0.0))
    await session.commit()

    ctx = await start_run("verify_profile", profile.id)
    await jobs.enqueue("verify_profile", {"profile_id": str(profile.id), "run_id": str(ctx.run_id)},
                       idempotency_key=f"verify:{profile.id}")
    return {"run_id": str(ctx.run_id), "status": "started"}

@router.post("/{profile_id}/verify", status_code=status.HTTP_202_ACCEPTED)
async def verify(
    profile_id: uuid.UUID,
    background: BackgroundTasks,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    """Kick off Pariksha → Prahari. Returns at once; follow progress on the agent stream."""
    profile = await _owned(session, profile_id, principal)
    await require_verified_email(principal)
    consent = (
        await session.execute(
            select(Consent).where(Consent.profile_id == profile.id, Consent.kind == "public_listing")
            .order_by(Consent.created_at.desc())
        )
    ).scalars().first()
    if not consent or not consent.granted:
        raise HTTPException(409, "Consent to public listing is required before verification")
    if not profile.claims:
        raise HTTPException(409, "Add at least one achievement before verification")
    try:
        # The lock closes the check-then-act race: two simultaneous requests must not both see "nothing running".
        async with short_lock(f"verify:{profile.id}"):
            return await _start_verification(session, profile)
    except LockBusy as exc:
        raise HTTPException(409, "A verification is already being started for this profile") from exc


class WikidataConfirmIn(BaseModel):
    qid: str | None = Field(default=None, max_length=20, description="The Wikidata item that is you, or null for 'none of these'")


@router.get("/{profile_id}/wikidata-candidates")
async def wikidata_candidates(
    profile_id: uuid.UUID,
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    """People on Wikidata with your name. You choose which (if any) is you: that item, and only that item, is then
    used as evidence, so a namesake's awards can never be credited to you."""
    from app.services import wikidata

    profile = await _owned(session, profile_id, principal)
    await _limit_llm(principal, 20)
    return {"confirmed_qid": profile.wikidata_qid or None, "candidates": await wikidata.candidates(profile.full_name)}


@router.post("/{profile_id}/wikidata-confirm", response_model=ProfileOut)
async def wikidata_confirm(
    profile_id: uuid.UUID,
    body: WikidataConfirmIn,
    principal: Principal = Depends(require_scope("profiles:write")),
    session: AsyncSession = Depends(get_session),
):
    from app.services import wikidata

    profile = await _owned(session, profile_id, principal)
    _require_editable(profile)
    if body.qid is None:
        profile.wikidata_qid = ""
    else:
        if not wikidata.QID_RE.match(body.qid):
            raise HTTPException(422, "That is not a Wikidata item id (like Q12345)")
        # Only an item that was actually offered for this name can be confirmed.
        offered = {c["qid"] for c in await wikidata.candidates(profile.full_name)}
        if body.qid not in offered:
            raise HTTPException(409, "That item is not one of the candidates for this name")
        profile.wikidata_qid = body.qid
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/{profile_id}/agent-events")
async def profile_agent_events(
    profile_id: uuid.UUID,
    limit: int = 100,
    principal: Principal = Depends(require_scope("profiles:read")),
    session: AsyncSession = Depends(get_session),
):
    await _owned(session, profile_id, principal)
    return list(reversed(await recent_events(profile_id=profile_id, limit=min(limit, 300))))
