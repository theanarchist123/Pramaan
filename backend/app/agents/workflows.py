"""The verification workflow, orchestrated as a LangGraph state machine.

    research ──► factcheck ──► audit ──┬─► approve   (confidence ≥ 95% and identity confirmed)
                                       └─► escalate  (everything else → human review queue)

Fail-safe by construction: any error ends in 'escalate', never in an approval.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import pariksha, prahari
from app.agents.events import RunContext, start_run
from app.agents.prahari import AuditDecision
from app.agents.textutil import name_similarity
from app.db import get_sessionmaker
from app.domain import STATUS_SELF
from app.llm.client import LLMError, LLMRefusal
from app.models import Profile, ReviewItem
from app.services import wikidata, wikipedia
from app.services.wikipedia import Source

log = logging.getLogger("pramaan.workflow")
SOURCE_NAME_MATCH = 0.75


class VerifyState(TypedDict, total=False):
    ctx: RunContext
    profile_id: uuid.UUID
    sources: list[Source]
    decision: AuditDecision


async def _load_profile(session, profile_id: uuid.UUID) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise LookupError("Profile vanished during verification")
    return profile


async def n_research(state: VerifyState) -> VerifyState:
    ctx = state["ctx"]
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, state["profile_id"])
        name = profile.full_name
    await ctx.emit("Pariksha", "tool", f"Looking for public evidence about {name}")
    found = await wikipedia.fetch_sources(name, limit=3)
    found = [*found, *await wikidata.fetch_sources(name, limit=3)]  # structured facts for people with no article
    # Only keep pages that are plausibly about this person, so a namesake can't vouch for them.
    sources = [s for s in found if name_similarity(s.title, name) >= SOURCE_NAME_MATCH]
    await ctx.emit(
        "Pariksha", "result",
        f"{len(sources)} relevant public source(s) found" if sources else "No public sources match this name",
        data={"sources": [s.url for s in sources]},
    )
    return {"sources": sources}


async def n_factcheck(state: VerifyState) -> VerifyState:
    ctx = state["ctx"]
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, state["profile_id"])
        pending = [c for c in profile.claims if c.status == STATUS_SELF]
        counts = await pariksha.fact_check(ctx, session, profile, pending, state.get("sources", []))
        await session.commit()
    await ctx.emit("Pariksha", "handoff", "Fact-check complete → handing to Prahari", data=counts)
    return {}


async def n_audit(state: VerifyState) -> VerifyState:
    ctx = state["ctx"]
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, state["profile_id"])
        decision = await prahari.audit(ctx, session, profile)
    return {"decision": decision}


def _route(state: VerifyState) -> str:
    return "approve" if state["decision"].decision == "auto_approve" else "escalate"


async def _apply(state: VerifyState) -> VerifyState:
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, state["profile_id"])
        await prahari.apply_decision(state["ctx"], session, profile, state["decision"])
        await session.commit()
        from app.services import webhooks

        if profile.status == "approved":
            webhooks.schedule("profile.approved", webhooks.profile_payload(profile))
        else:
            webhooks.schedule("review.queued", {"profile_id": str(profile.id), "slug": profile.slug,
                                                 "full_name": profile.full_name,
                                                 "reasons": state["decision"].reasons})
    return {}


def build_graph():
    g = StateGraph(VerifyState)
    g.add_node("research", n_research)
    g.add_node("factcheck", n_factcheck)
    g.add_node("audit", n_audit)
    g.add_node("approve", _apply)
    g.add_node("escalate", _apply)
    g.add_edge(START, "research")
    g.add_edge("research", "factcheck")
    g.add_edge("factcheck", "audit")
    g.add_conditional_edges("audit", _route, {"approve": "approve", "escalate": "escalate"})
    g.add_edge("approve", END)
    g.add_edge("escalate", END)
    return g.compile()


_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def _escalate_on_failure(ctx: RunContext, profile_id: uuid.UUID, why: str) -> None:
    async with get_sessionmaker()() as session:
        profile = await session.get(Profile, profile_id)
        if profile is None:
            return
        profile.status = "pending_review"
        open_item = (
            await session.execute(
                select(ReviewItem).where(ReviewItem.profile_id == profile_id, ReviewItem.status == "open")
            )
        ).scalars().first()
        if open_item:
            open_item.reason = why[:300]
        else:
            session.add(ReviewItem(profile_id=profile_id, reason=why[:300], confidence=0.0))
        await session.commit()
    await ctx.emit("Prahari", "handoff", f"Automation could not finish ({why}) — sent to a human reviewer")


async def run_verification(ctx: RunContext, profile_id: uuid.UUID) -> dict[str, Any]:
    """Run the workflow inside an existing run (so callers can return the run id immediately)."""
    try:
        final = await _get_graph().ainvoke({"ctx": ctx, "profile_id": profile_id})
        decision: AuditDecision = final["decision"]
        summary = (
            f"Auto-approved at {decision.score:.0%}"
            if decision.decision == "auto_approve"
            else f"Escalated to human review at {decision.score:.0%}: {'; '.join(decision.reasons)}"
        )
        await ctx.finish("done", summary)
        return {"decision": decision.decision, "score": decision.score, "reasons": decision.reasons}
    except LLMRefusal as exc:
        await _escalate_on_failure(ctx, profile_id, "The AI declined to assess this profile")
        await ctx.finish("failed", f"Model refusal: {exc}")
        return {"decision": "escalate", "score": 0.0, "reasons": ["AI refusal"]}
    except (LLMError, LookupError, Exception) as exc:  # noqa: BLE001 - fail safe, never approve
        log.exception("verification failed")
        await _escalate_on_failure(ctx, profile_id, "Automated verification failed")
        await ctx.finish("failed", f"Error: {type(exc).__name__}")
        return {"decision": "escalate", "score": 0.0, "reasons": ["automation error"]}


async def verify_profile(profile_id: uuid.UUID) -> dict[str, Any]:
    ctx = await start_run("verify_profile", profile_id)
    return await run_verification(ctx, profile_id)
