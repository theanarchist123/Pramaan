"""The dispute graph (AGT-02): someone says a claim on a profile is wrong.

    refetch ──► recheck ──► reaudit ──► escalate ──► await_person ──► END
                                         (always: a person decides; the graph PAUSES at an interrupt and resumes with their decision)

* refetch   gets fresh public evidence again (adapters), so a stale page cannot keep vouching.
* recheck   puts the disputed claim back to "self-claimed" and asks Pariksha to support it again, with every guard. If it no longer stands it stays self-claimed,
            so it can no longer be printed on a certificate (I-8).
* escalate  opens (or refreshes) a review item saying what was disputed and what the re-check found. Nothing is removed from the public record by the machine
            alone except a claim's confirmation level; hiding the whole profile is a person's decision (suspend).
Any error also ends at a person (I-2).
"""
from __future__ import annotations

import dataclasses
import uuid
from types import SimpleNamespace
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app import evidence
from app.agents import pariksha, prahari
from app.agents.events import RunContext
from app.agents.graphs.common import get_checkpointer, thread
from app.agents.textutil import name_similarity
from app.db import get_sessionmaker
from app.domain import STATUS_SELF
from app.evidence.base import EvidenceDoc
from app.models import Claim, Profile
from app.services.review_items import open_reason

NAME = "dispute"
SOURCE_NAME_MATCH = 0.75


class DisputeState(TypedDict, total=False):
    claim_id: str
    reason: str
    run_id: str
    profile_id: str
    sources: list[dict]
    still_supported: bool
    score: float
    person_decision: dict


def _ctx(state: DisputeState) -> RunContext:
    return RunContext(uuid.UUID(state["run_id"]), "dispute_claim", uuid.UUID(state["profile_id"]))


async def n_refetch(state: DisputeState) -> DisputeState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        profile = await session.get(Profile, ctx.profile_id)
        person = SimpleNamespace(name=profile.full_name, qid=profile.wikidata_qid, institutions=list(profile.institutions or []))
    found = await evidence.gather(person, evidence.default_adapters())
    sources = [s for s in found if name_similarity(s.title, person.name) >= SOURCE_NAME_MATCH]
    await ctx.emit("Pariksha", "result", f"{len(sources)} fresh public source(s) fetched for the disputed claim")
    return {"sources": [dataclasses.asdict(s) for s in sources]}


async def n_recheck(state: DisputeState) -> DisputeState:
    ctx = _ctx(state)
    sources = [EvidenceDoc(**d) for d in state.get("sources", [])]
    async with get_sessionmaker()() as session:
        profile = await session.get(Profile, ctx.profile_id)
        claim = await session.get(Claim, uuid.UUID(state["claim_id"]))
        if claim is None or claim.profile_id != profile.id:
            raise LookupError("claim not found on this profile")
        # Start from "self-claimed": the old confirmation does not get the benefit of the doubt.
        old = claim.status
        claim.status, claim.confidence = STATUS_SELF, 0.0
        counts = await pariksha.fact_check(ctx, session, profile, [claim], sources)
        await session.commit()
        still = claim.status != STATUS_SELF
    await ctx.emit("Pariksha", "handoff", f"Re-check done (was '{old}', now {'supported again' if still else 'not supported'})", data=counts)
    return {"still_supported": still}


async def n_reaudit(state: DisputeState) -> DisputeState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        profile = await session.get(Profile, ctx.profile_id)
        decision = await prahari.audit(ctx, session, profile)
    return {"score": decision.score}


async def n_escalate(state: DisputeState) -> DisputeState:
    ctx = _ctx(state)
    outcome = "the claim is still supported by fresh public evidence" if state.get("still_supported") else "the claim is no longer supported and was set back to self-claimed"
    async with get_sessionmaker()() as session:
        await open_reason(session, ctx.profile_id, f"Claim disputed: {state.get('reason', '')[:150]} ({outcome})",
                          {"kind": "dispute", "claim_id": state["claim_id"], "still_supported": bool(state.get("still_supported"))})
        await session.commit()
    await ctx.emit("Prahari", "handoff", "Dispute sent to a reviewer", data={"still_supported": bool(state.get("still_supported"))})
    return {}


async def n_await_person(state: DisputeState) -> DisputeState:
    """Pauses until a person decides; resumes with their decision. Does nothing else, so re-running it on resume is safe."""
    decision = interrupt({"claim_id": state["claim_id"], "profile_id": state["profile_id"]})
    return {"person_decision": decision if isinstance(decision, dict) else {"outcome": str(decision)}}


def build_graph(checkpointer=None):
    g = StateGraph(DisputeState)
    g.add_node("refetch", n_refetch)
    g.add_node("recheck", n_recheck)
    g.add_node("reaudit", n_reaudit)
    g.add_node("escalate", n_escalate)
    g.add_node("await_person", n_await_person)
    g.add_edge(START, "refetch")
    g.add_edge("refetch", "recheck")
    g.add_edge("recheck", "reaudit")
    g.add_edge("reaudit", "escalate")
    g.add_edge("escalate", "await_person")
    g.add_edge("await_person", END)
    return g.compile(checkpointer=checkpointer)


async def run(ctx: RunContext, payload: dict) -> dict:
    graph = build_graph(await get_checkpointer())
    cfg = {"configurable": {"thread_id": thread(NAME, payload["claim_id"], ctx.run_id)}}
    final = await graph.ainvoke({"claim_id": payload["claim_id"], "reason": str(payload.get("reason", ""))[:300], "run_id": str(ctx.run_id),
                                 "profile_id": str(ctx.profile_id)}, cfg)
    await ctx.finish("done", "dispute is with a reviewer")  # the graph is paused at the interrupt; the review item carries on from here
    return {"still_supported": bool(final.get("still_supported"))}


async def on_failure(ctx: RunContext, payload: dict, why: str) -> None:
    async with get_sessionmaker()() as session:
        if ctx.profile_id:
            await open_reason(session, ctx.profile_id, f"Claim disputed and automation could not finish ({why})", {"kind": "dispute", "claim_id": payload.get("claim_id")})
            await session.commit()
    await ctx.emit("Prahari", "handoff", f"Automation could not finish ({why}): sent to a human reviewer")
