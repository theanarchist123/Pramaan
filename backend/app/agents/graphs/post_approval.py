"""The post-approval graph (AGT-02): what the registry does after a person is approved.

    index ──► connect (Setu) ──► welcome (Doot, only when its policy allows) ──► END

Each step is best effort and independent: a failure in one is recorded and the next still runs, because none of them can change who is approved or what a
certificate says. Certificates are NOT issued here: only the person can ask for one, with their consent (I-5).
"""
from __future__ import annotations

import logging
import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import setu
from app.agents.events import RunContext
from app.agents.graphs.common import get_checkpointer, thread
from app.db import get_sessionmaker
from app.models import Profile

NAME = "post_approval"
log = logging.getLogger("pramaan.post_approval")


class PostState(TypedDict, total=False):
    profile_id: str
    run_id: str
    notes: list[str]


def _ctx(state: PostState) -> RunContext:
    return RunContext(uuid.UUID(state["run_id"]), "post_approval", uuid.UUID(state["profile_id"]))


async def _guard(state: PostState, step: str, fn) -> PostState:
    ctx = _ctx(state)
    notes = list(state.get("notes", []))
    try:
        await fn(ctx)
        notes.append(f"{step}: ok")
    except Exception as exc:  # noqa: BLE001 - one step failing must not stop the others
        log.exception("post-approval step %s failed", step)
        notes.append(f"{step}: failed ({type(exc).__name__})")
        await ctx.emit("Sutradhar", "warning", f"Step '{step}' failed and was skipped")
    return {"notes": notes}


async def n_index(state: PostState) -> PostState:
    async def go(ctx: RunContext):
        from app.services.directory import on_approved

        async with get_sessionmaker()() as session:
            profile = await session.get(Profile, ctx.profile_id)
            if profile is None or profile.status != "approved":
                raise LookupError("profile is not approved")
            await on_approved(session, profile)
            await session.commit()

    return await _guard(state, "index", go)


async def n_connect(state: PostState) -> PostState:
    async def go(ctx: RunContext):
        async with get_sessionmaker()() as session:
            report = await setu.run(ctx, session, limit=500)
            await session.commit()
        await ctx.emit("Setu", "result", f"{report['accepted']} new connection(s)", data={"proposed": report["proposed"], "rejected": report["rejected"]})

    return await _guard(state, "connect", go)


async def n_welcome(state: PostState) -> PostState:
    async def go(ctx: RunContext):
        from app.services import outreach

        async with get_sessionmaker()() as session:
            await outreach.welcome_if_allowed(session, ctx.profile_id)
            await session.commit()

    return await _guard(state, "welcome", go)


def build_graph(checkpointer=None):
    g = StateGraph(PostState)
    g.add_node("index", n_index)
    g.add_node("connect", n_connect)
    g.add_node("welcome", n_welcome)
    g.add_edge(START, "index")
    g.add_edge("index", "connect")
    g.add_edge("connect", "welcome")
    g.add_edge("welcome", END)
    return g.compile(checkpointer=checkpointer)


async def run(ctx: RunContext, payload: dict) -> dict:
    graph = build_graph(await get_checkpointer())
    final = await graph.ainvoke({"profile_id": str(ctx.profile_id), "run_id": str(ctx.run_id), "notes": []},
                                {"configurable": {"thread_id": thread(NAME, ctx.profile_id, ctx.run_id)}})
    await ctx.finish("done", "; ".join(final.get("notes", [])))
    return {"notes": final.get("notes", [])}


async def on_failure(ctx: RunContext, payload: dict, why: str) -> None:
    await ctx.emit("Sutradhar", "warning", f"Post-approval work stopped ({why}); nothing about the approval changed")
