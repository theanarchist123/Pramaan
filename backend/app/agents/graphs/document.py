"""The document graph (AGT-02): load a stored document, read it (classify, extract, forensics, cross-check), and send anything doubtful to a person.

    load ──► read ──┬─► flag ──► END     (any forensic flag, or a name match below 0.95: a person looks, even if the profile is already public)
                    └─► END

It is the same Lipik pipeline the upload endpoint runs, but re-runnable from a stored file (a re-check after a rule change, or a document whose first
read was refused by a kill switch). Errors never approve anything: the node that fails sends the document to review instead (I-2).
"""
from __future__ import annotations

import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import lipik
from app.agents.events import RunContext
from app.agents.graphs.common import get_checkpointer, thread
from app.db import get_sessionmaker
from app.models import Document, Profile
from app.services.review_items import open_document_review

NAME = "document"


class DocState(TypedDict, total=False):
    document_id: str
    run_id: str
    profile_id: str
    flags: list[str]
    needs_review: bool
    upgraded: int


def _ctx(state: DocState) -> RunContext:
    return RunContext(uuid.UUID(state["run_id"]), "document_check", uuid.UUID(state["profile_id"]))


async def n_read(state: DocState) -> DocState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        doc = await session.get(Document, uuid.UUID(state["document_id"]))
        profile = await session.get(Profile, uuid.UUID(state["profile_id"]))
        if doc is None or profile is None:
            raise LookupError("document or profile is gone")
        from pathlib import Path

        data = Path(doc.path).read_bytes()
        result = await lipik.read_document(ctx, session, profile, doc, doc.content_type, data)
        await session.commit()
    return {"flags": list(result.flags), "needs_review": bool(result.flags) or (result.match_score or 0) < 0.95, "upgraded": result.upgraded_claims}


async def n_flag(state: DocState) -> DocState:
    ctx = _ctx(state)
    async with get_sessionmaker()() as session:
        doc = await session.get(Document, uuid.UUID(state["document_id"]))
        profile = await session.get(Profile, uuid.UUID(state["profile_id"]))
        await open_document_review(session, profile, doc, state.get("flags", []))
        await session.commit()
    await ctx.emit("Lipik", "handoff", "A document the machine cannot vouch for was sent to a reviewer")
    return {}


def _route(state: DocState) -> str:
    return "flag" if state.get("needs_review") else "end"


def build_graph(checkpointer=None):
    g = StateGraph(DocState)
    g.add_node("read", n_read)
    g.add_node("flag", n_flag)
    g.add_edge(START, "read")
    g.add_conditional_edges("read", _route, {"flag": "flag", "end": END})
    g.add_edge("flag", END)
    return g.compile(checkpointer=checkpointer)


async def run(ctx: RunContext, payload: dict) -> dict:
    graph = build_graph(await get_checkpointer())
    doc_id = payload["document_id"]
    final = await graph.ainvoke({"document_id": doc_id, "run_id": str(ctx.run_id), "profile_id": str(ctx.profile_id)},
                                {"configurable": {"thread_id": thread(NAME, doc_id, ctx.run_id)}})
    summary = f"{final.get('upgraded', 0)} claim(s) upgraded; flags: {final.get('flags') or 'none'}"
    await ctx.finish("done", summary)
    return {"flags": final.get("flags", []), "sent_to_review": bool(final.get("needs_review"))}


async def on_failure(ctx: RunContext, payload: dict, why: str) -> None:
    """The document could not be read: a person must look at it."""
    async with get_sessionmaker()() as session:
        doc = await session.get(Document, uuid.UUID(payload["document_id"]))
        profile = await session.get(Profile, ctx.profile_id) if ctx.profile_id else None
        if doc is not None and profile is not None:
            await open_document_review(session, profile, doc, ["unreadable"])
            await session.commit()
    await ctx.emit("Lipik", "handoff", f"Automation could not finish ({why}): sent to a human reviewer")
