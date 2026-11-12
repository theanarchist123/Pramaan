"""The review workbench API (spec 7.5): lock a case, decide it claim by claim with reason codes, release it.

Rules enforced here:
  * you must HOLD the lock to decide (opening a case locks it to you for LOCK_MINUTES; others are told who has it);
  * nobody decides on their own profile (I-10);
  * every decision needs a reason code from the shared vocabulary; verifying a claim also needs a written note and an
    evidence reference, and produces the `human` status (never `document`/`web`: invariant I-8);
  * verifying an AWARD claim needs the senior permission (review.decide_high_risk): awards are the highest-trust claims;
  * every decision is stored as its own row and written to the audit log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.reasons import REASON_CODES
from app.core.rbac import permissions_for_user
from app.db import get_session
from app.deps import Principal, require_permission
from app.domain import HUMAN_CONFIDENCE_CAP, STATUS_HUMAN
from app.models import Claim, Evidence, Profile, ReviewDecision, ReviewItem, User
from app.services import audit

router = APIRouter(prefix="/v1/admin/review", tags=["review"])
LOCK_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _item(session: AsyncSession, item_id: uuid.UUID) -> ReviewItem:
    item = await session.get(ReviewItem, item_id)
    if item is None:
        raise HTTPException(404, "Review item not found")
    return item


def _held_by_other(item: ReviewItem, me: uuid.UUID) -> bool:
    return bool(item.assigned_to and item.assigned_to != me and item.locked_until and item.locked_until > _now())


def _no_self_review(principal: Principal, profile: Profile | None) -> None:
    if profile is not None and profile.owner_id == principal.user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot review your own profile")


@router.get("/reason-codes")
async def reason_codes(_: Principal = Depends(require_permission("review.read"))):
    return REASON_CODES


@router.get("/{item_id}")
async def case_detail(item_id: uuid.UUID, principal: Principal = Depends(require_permission("review.read")),
                      session: AsyncSession = Depends(get_session)):
    """Everything a reviewer needs on one page. Documents are shown as metadata and the forensic flags only: never the file, its
    storage path or its raw hash (opening the file itself is a separate, audited step)."""
    from app.agents.reasons import codes_for
    from app.models import Document, IdentityBinding
    from app.api.admin import ReviewItemOut
    from app.schemas import ProfileOut
    from app.services.doc_forensics import FLAG_TEXT

    item = await _item(session, item_id)
    profile = await session.get(Profile, item.profile_id)
    docs = (await session.execute(select(Document).where(Document.profile_id == item.profile_id).order_by(Document.created_at))).scalars().all()
    view = ReviewItemOut.model_validate(item)
    if not (view.details or {}).get("reason_codes"):
        view.details = {**(view.details or {}), "reason_codes": codes_for([item.reason])}
    # Only VERIFIED bindings, and only the domain/host: evidence for the reviewer to weigh, never an approval.
    bindings = (await session.execute(select(IdentityBinding).where(IdentityBinding.profile_id == item.profile_id, IdentityBinding.status == "verified")
                                      .order_by(IdentityBinding.verified_at))).scalars().all()
    perms = await permissions_for_user(session, principal.user)
    holds = bool(item.assigned_to == principal.user.id and item.locked_until and item.locked_until > _now())
    ex = lambda d: d.extracted or {}  # noqa: E731
    return {
        "item": view,
        "profile": ProfileOut.model_validate(profile) if profile else None,
        "documents": [
            {"id": str(d.id), "filename": d.filename, "uploaded_at": d.created_at, "match_score": d.match_score,
             "holder_name": ex(d).get("holder_name", ""), "title": ex(d).get("title", ""), "issuer": ex(d).get("issuer", ""),
             "flags": ex(d).get("flags", []), "flag_notes": [FLAG_TEXT[f] for f in ex(d).get("flags", []) if f in FLAG_TEXT]}
            for d in docs
        ],
        "bindings": [{"kind": b.kind, "subject": b.subject, "verified_at": b.verified_at} for b in bindings],
        "permissions": {"can_decide": "review.decide" in perms and holds and item.status == "open", "holds_lock": holds,
                        "own_profile": bool(profile and profile.owner_id == principal.user.id)},
    }


@router.get("/{item_id}/namesakes")
async def namesakes(item_id: uuid.UUID, _: Principal = Depends(require_permission("review.read")),
                    session: AsyncSession = Depends(get_session)):
    """Other people with this name on Wikidata, beside the item the applicant confirmed is them, so a reviewer can tell who might be
    mistaken for whom. Read-only; it is the same public lookup the applicant saw."""
    from app.services import wikidata

    item = await _item(session, item_id)
    profile = await session.get(Profile, item.profile_id)
    if profile is None:
        raise HTTPException(404, "Profile not found")
    return {"name": profile.full_name, "confirmed_qid": profile.wikidata_qid or "",
            "candidates": await wikidata.candidates(profile.full_name)}


@router.post("/{item_id}/claim")
async def lock_case(item_id: uuid.UUID, principal: Principal = Depends(require_permission("review.claim")),
                    session: AsyncSession = Depends(get_session)):
    """Take the case: it is yours for 15 minutes (renew by calling again). Someone else's live lock is a 409."""
    item = await _item(session, item_id)
    if item.status != "open":
        raise HTTPException(409, f"This case is already {item.status}")
    _no_self_review(principal, await session.get(Profile, item.profile_id))
    if _held_by_other(item, principal.user.id):
        holder = await session.get(User, item.assigned_to)
        raise HTTPException(409, f"Being reviewed by {holder.name or holder.email if holder else 'someone else'}")
    item.assigned_to, item.locked_until = principal.user.id, _now() + timedelta(minutes=LOCK_MINUTES)
    await session.commit()
    return {"assigned_to": str(item.assigned_to), "locked_until": item.locked_until}


@router.post("/{item_id}/release")
async def release_case(item_id: uuid.UUID, principal: Principal = Depends(require_permission("review.claim")),
                       session: AsyncSession = Depends(get_session)):
    item = await _item(session, item_id)
    if item.assigned_to == principal.user.id:
        item.assigned_to = item.locked_until = None
        await session.commit()
    return {"released": True}


class ClaimDecisionIn(BaseModel):
    claim_id: uuid.UUID
    decision: Literal["verify", "hold", "reject"]
    reason_code: str
    note: str = Field(default="", max_length=500)
    evidence_ref: str = Field(default="", max_length=600)


class DecideIn(BaseModel):
    claims: list[ClaimDecisionIn] = []
    outcome: Literal["approve", "reject", "hold"] = "hold"
    reason_code: str
    note: str = Field(default="", max_length=500)


@router.post("/{item_id}/decide")
async def decide(item_id: uuid.UUID, body: DecideIn, request: Request,
                 principal: Principal = Depends(require_permission("review.decide")),
                 session: AsyncSession = Depends(get_session)):
    item = await _item(session, item_id)
    if item.status != "open":
        raise HTTPException(409, f"This case is already {item.status}")
    profile = await session.get(Profile, item.profile_id)
    _no_self_review(principal, profile)
    me = principal.user.id
    if item.assigned_to != me or not item.locked_until or item.locked_until <= _now():
        raise HTTPException(409, "Take the case first (POST .../claim): decisions need a live lock")

    for code in (body.reason_code, *[c.reason_code for c in body.claims]):
        if code not in REASON_CODES:
            raise HTTPException(422, f"Unknown reason code '{code}'")
    if body.outcome in ("reject", "approve") and len(body.note.strip()) < 10:
        raise HTTPException(422, "Explain the decision in a note (at least 10 characters)")

    perms = await permissions_for_user(session, principal.user)
    by_id = {c.id: c for c in (profile.claims if profile else [])}
    rows: list[ReviewDecision] = []
    for cd in body.claims:
        claim = by_id.get(cd.claim_id)
        if claim is None:
            raise HTTPException(422, f"Claim {cd.claim_id} is not part of this profile")
        if cd.decision == "verify":
            if len(cd.note.strip()) < 10 or len(cd.evidence_ref.strip()) < 5:
                raise HTTPException(422, "Verifying a claim needs a written note and an evidence reference")
            if claim.field == "award" and "review.decide_high_risk" not in perms:
                raise HTTPException(403, "Award claims need a senior verifier (review.decide_high_risk)")
            claim.status = STATUS_HUMAN
            claim.confidence = HUMAN_CONFIDENCE_CAP
            claim.evidence.append(Evidence(kind="human", quote=cd.note, url=cd.evidence_ref, source_hash=f"reviewer:{me}"))
        elif cd.decision == "reject":
            claim.status, claim.confidence = "self", 0.0
        rows.append(ReviewDecision(review_item_id=item.id, claim_id=claim.id, decided_by=me, decision=cd.decision,
                                   reason_code=cd.reason_code, note=cd.note, evidence_ref=cd.evidence_ref))
    rows.append(ReviewDecision(review_item_id=item.id, claim_id=None, decided_by=me, decision=body.outcome,
                               reason_code=body.reason_code, note=body.note))
    session.add_all(rows)

    thread = (item.details or {}).get("thread_id", "")
    if body.outcome in ("approve", "reject"):
        profile.status = "approved" if body.outcome == "approve" else "rejected"
        profile.decision_basis = "reviewer" if body.outcome == "approve" else ""
        item.status, item.resolved_by, item.resolved_at = ("approved" if body.outcome == "approve" else "rejected"), me, _now()
        item.assigned_to = item.locked_until = None
        if body.outcome == "approve":
            from app.services.directory import on_approved

            await on_approved(session, profile)
    await audit.record(session, actor_id=me, actor_role="staff", action="review.decide", target_type="review",
                       target_id=str(item.id), before={"status": "open"},
                       after={"outcome": body.outcome, "claims": [{"claim": str(c.claim_id), "decision": c.decision, "code": c.reason_code} for c in body.claims]},
                       reason=f"{body.reason_code}: {body.note}", ip=request.client.host if request.client else "")
    await session.commit()

    if body.outcome in ("approve", "reject"):
        from app.agents.workflows import resume_review

        await resume_review(thread, "approved" if body.outcome == "approve" else "rejected", str(me))
        if body.outcome == "approve":
            from app.services import webhooks

            await session.refresh(profile)
            webhooks.schedule("profile.approved", webhooks.profile_payload(profile))
    return {"outcome": body.outcome, "decisions": len(rows), "case_status": item.status}


@router.get("/{item_id}/decisions")
async def decisions(item_id: uuid.UUID, _: Principal = Depends(require_permission("review.read")),
                    session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(ReviewDecision).where(ReviewDecision.review_item_id == item_id)
                                  .order_by(ReviewDecision.decided_at))).scalars().all()
    return [{"id": str(r.id), "claim_id": str(r.claim_id) if r.claim_id else None, "decided_by": str(r.decided_by),
             "decision": r.decision, "reason_code": r.reason_code, "note": r.note, "evidence_ref": r.evidence_ref,
             "decided_at": r.decided_at} for r in rows]
