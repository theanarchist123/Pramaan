"""The verification workflow, orchestrated as a LangGraph state machine with a durable human-review step.

    research ──► factcheck ──► audit ──┬─► approve                       (confidence >= 95% and every rule satisfied)
                                       └─► escalate ──► await_review ──► end
                                                         (interrupt: the graph PAUSES here until a person decides)

* Fail-safe by construction: any error ends in escalation, never in an approval (invariant I-2).
* Durable: state is checkpointed to Postgres (CHECKPOINT_BACKEND=postgres), so a case waiting for a reviewer survives a
  restart, and the reviewer's decision resumes the very same run. State holds only plain data (ids, dicts) so it can
  be serialised; nodes rebuild what they need (a RunContext is just ids) from it.
* On Windows' default event loop psycopg's async mode cannot run, so the in-memory checkpointer is used there (dev
  only); Linux, where this is deployed, uses Postgres.
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from types import SimpleNamespace
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from app.agents import pariksha, prahari
from app.agents.events import RunContext, start_run
from app.agents.prahari import AuditDecision
from app.agents.textutil import name_similarity
from app.config import get_settings
from app.db import get_sessionmaker
from app.domain import STATUS_SELF
from app.llm.client import LLMError, LLMRefusal
from app.models import Profile, ReviewItem
from app import evidence
from app.evidence.base import EvidenceDoc

log = logging.getLogger("pramaan.workflow")
SOURCE_NAME_MATCH = 0.75
WORKFLOW = "verify_profile"


class VerifyState(TypedDict, total=False):
    profile_id: str
    run_id: str
    sources: list[dict]
    decision: dict
    review_outcome: dict


def thread_id(profile_id: uuid.UUID | str, run_id: uuid.UUID | str) -> str:
    return f"verify:{profile_id}:{run_id}"


def _ctx(state: VerifyState) -> RunContext:
    return RunContext(uuid.UUID(state["run_id"]), WORKFLOW, uuid.UUID(state["profile_id"]))


async def _load_profile(session, profile_id: uuid.UUID) -> Profile:
    profile = await session.get(Profile, profile_id)
    if profile is None:
        raise LookupError("Profile vanished during verification")
    return profile


async def n_research(state: VerifyState) -> VerifyState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, ctx.profile_id)
        name, qid, institutions = profile.full_name, profile.wikidata_qid, list(profile.institutions or [])
    await ctx.emit("Pariksha", "tool", f"Looking for public evidence about {name}")
    # Pluggable adapters (Wikipedia, Wikidata for the item the applicant confirmed, OpenAlex for people with a stated institution). A failing source
    # is skipped; every document is stamped with when it was fetched and a hash of exactly that text.
    found = await evidence.gather(SimpleNamespace(name=name, qid=qid, institutions=institutions), evidence.default_adapters())
    # Only keep pages that are plausibly about this person, so a namesake can't vouch for them.
    sources = [s for s in found if name_similarity(s.title, name) >= SOURCE_NAME_MATCH]
    await ctx.emit(
        "Pariksha", "result",
        f"{len(sources)} relevant public source(s) found" if sources else "No public sources match this name",
        data={"sources": [s.url for s in sources]},
    )
    return {"sources": [dataclasses.asdict(s) for s in sources]}


async def n_factcheck(state: VerifyState) -> VerifyState:
    ctx = _ctx(state)
    sources = [EvidenceDoc(**d) for d in state.get("sources", [])]
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, ctx.profile_id)
        pending = [c for c in profile.claims if c.status == STATUS_SELF]
        counts = await pariksha.fact_check(ctx, session, profile, pending, sources)
        await session.commit()
    await ctx.emit("Pariksha", "handoff", "Fact-check complete → handing to Prahari", data=counts)
    return {}


async def n_audit(state: VerifyState) -> VerifyState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, ctx.profile_id)
        decision = await prahari.audit(ctx, session, profile)
    return {"decision": dataclasses.asdict(decision)}


def _route(state: VerifyState) -> str:
    return "approve" if state["decision"]["decision"] == "auto_approve" else "escalate"


async def _apply(state: VerifyState) -> VerifyState:
    ctx = _ctx(state)
    decision = AuditDecision(**state["decision"])
    async with get_sessionmaker()() as session:
        profile = await _load_profile(session, ctx.profile_id)
        await prahari.apply_decision(ctx, session, profile, decision)
        if decision.decision != "auto_approve":
            # Remember which paused run this review belongs to, so the reviewer's decision can resume it.
            item = (await session.execute(
                select(ReviewItem).where(ReviewItem.profile_id == profile.id, ReviewItem.status == "open")
            )).scalars().first()
            if item is not None:
                from app.agents.reasons import codes_for

                item.details = {**(item.details or {}), "thread_id": thread_id(profile.id, ctx.run_id),
                                "reason_codes": codes_for(decision.reasons)}
        await session.commit()
        from app.services import webhooks

        if profile.status == "approved":
            webhooks.schedule("profile.approved", webhooks.profile_payload(profile))
        else:
            webhooks.schedule("review.queued", {"profile_id": str(profile.id), "slug": profile.slug,
                                                 "full_name": profile.full_name, "reasons": decision.reasons})
    return {}


async def n_await_review(state: VerifyState) -> VerifyState:
    """Pause until a person decides. The value passed to Command(resume=...) comes back here. This node does nothing
    else, so it is safe for LangGraph to run it again on resume."""
    outcome = interrupt({"profile_id": state["profile_id"], "reasons": state["decision"].get("reasons", [])})
    return {"review_outcome": outcome if isinstance(outcome, dict) else {"outcome": str(outcome)}}


def build_graph(checkpointer=None):
    g = StateGraph(VerifyState)
    g.add_node("research", n_research)
    g.add_node("factcheck", n_factcheck)
    g.add_node("audit", n_audit)
    g.add_node("approve", _apply)
    g.add_node("escalate", _apply)
    g.add_node("await_review", n_await_review)
    g.add_edge(START, "research")
    g.add_edge("research", "factcheck")
    g.add_edge("factcheck", "audit")
    g.add_conditional_edges("audit", _route, {"approve": "approve", "escalate": "escalate"})
    g.add_edge("approve", END)
    g.add_edge("escalate", "await_review")
    g.add_edge("await_review", END)
    return g.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------- the graph + its checkpointer
_graph = None
_pool = None


async def get_graph():
    global _graph, _pool
    if _graph is not None:
        return _graph
    import asyncio

    saver = None
    if get_settings().checkpoint_backend == "postgres":
        if "Proactor" in type(asyncio.get_running_loop()).__name__:
            log.warning("Windows' default event loop cannot run psycopg async: using the in-memory LangGraph checkpointer "
                        "(a paused review will not survive a restart here; Linux/Docker uses Postgres)")
        else:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            from app.jobs import psycopg_dsn

            _pool = AsyncConnectionPool(psycopg_dsn(), min_size=1, max_size=5, open=False, kwargs={"autocommit": True, "prepare_threshold": 0})
            await _pool.open()
            saver = AsyncPostgresSaver(_pool)
            await saver.setup()  # creates its tables if missing
    if saver is None:
        from langgraph.checkpoint.memory import MemorySaver

        saver = MemorySaver()
    _graph = build_graph(saver)
    return _graph


async def dispose_graph() -> None:
    global _graph, _pool
    _graph = None
    if _pool is not None:
        await _pool.close()
    _pool = None


# ---------------------------------------------------------------------------- running and resuming
async def _escalate_on_failure(ctx: RunContext, profile_id: uuid.UUID, why: str) -> None:
    async with get_sessionmaker()() as session:
        profile = await session.get(Profile, profile_id)
        if profile is None:
            return
        profile.status = "pending_review"
        profile.decision_basis = ""
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
    from app.services import governed

    if await governed.get("agents_paused"):  # AGT-01 kill switch: no model call, a human takes it (I-2)
        await _escalate_on_failure(ctx, profile_id, "AI agents are paused by an administrator")
        await ctx.finish("failed", "Paused: agents are switched off")
        return {"decision": "escalate", "score": 0.0, "reasons": ["agents paused"]}
    try:
        graph = await get_graph()
        config = {"configurable": {"thread_id": thread_id(profile_id, ctx.run_id)}}
        final = await graph.ainvoke({"profile_id": str(profile_id), "run_id": str(ctx.run_id)}, config)
        decision = AuditDecision(**final["decision"])
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


async def resume_review(thread: str, outcome: str, decided_by: str) -> bool:
    """A person decided: wake the paused run so it finishes. Best effort: returns False if there is nothing to resume
    (no such thread, already finished, or the case predates checkpointing). The decision itself is already saved by
    the caller; this only completes the graph's bookkeeping."""
    if not thread:
        return False
    try:
        graph = await get_graph()
        config = {"configurable": {"thread_id": thread}}
        snapshot = await graph.aget_state(config)
        if not snapshot or not snapshot.next:
            return False
        await graph.ainvoke(Command(resume={"outcome": outcome, "decided_by": decided_by}), config)
        return True
    except Exception:  # noqa: BLE001 - never fail a reviewer's action because of graph bookkeeping
        log.exception("could not resume review thread %s", thread)
        return False


async def verify_profile(profile_id: uuid.UUID) -> dict[str, Any]:
    ctx = await start_run(WORKFLOW, profile_id)
    return await run_verification(ctx, profile_id)
