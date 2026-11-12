"""Sutradhar ("the narrator who holds the strings"): the one front door for agent work (AGT-01).

    event ──► dispatch ──► idempotency ──► admit (kill switches, budgets) ──► graph (verify | document | dispute | post_approval) ──► outcome

* Idempotency: every event carries a key; a replay finds the run it already started and does not start another.
* Kill switches: a global one and one per agent, read from the database (governed settings), so they work without a deploy.
* Budgets: a daily token budget for all agents (reaching it pauses them), a token cap and a wall-clock cap per run. A run that goes over is stopped.
* Versions: each run records the policy version, a hash of every prompt and the model names, so a decision can be replayed and explained.
* Invariant I-2 for EVERY graph: refusal, timeout, budget or error ends with a person looking at it (or, for work that cannot change anyone's status, a no-op).
  Nothing in this file can approve or publish anything.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.agents.events import RunContext
from app.db import get_sessionmaker
from app.models import AgentRun, LlmCall
from app.services import governed

log = logging.getLogger("pramaan.sutradhar")

# event -> (graph, the agent whose kill switch gates it)
EVENT_ROUTES: dict[str, tuple[str, str]] = {
    "profile.submitted": ("verify", "pariksha"),
    "document.added": ("document", "lipik"),
    "claim.disputed": ("dispute", "pariksha"),
    "profile.approved": ("post_approval", "setu"),
}
WORKFLOW_NAMES = {"verify": "verify_profile", "document": "document_check", "dispute": "dispute_claim", "post_approval": "post_approval"}


class BudgetExceeded(Exception):
    pass


@dataclass
class Admission:
    ok: bool
    reason: str = ""


@dataclass
class Outcome:
    status: str  # started | done | deduped | refused | timed_out | failed
    run_id: uuid.UUID | None = None
    reason: str = ""


def _day_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


async def tokens_today() -> int:
    async with get_sessionmaker()() as s:
        n = (await s.execute(select(func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0)).where(LlmCall.at >= _day_start()))).scalar_one()
    return int(n)


async def tokens_for_run(run_id: uuid.UUID) -> int:
    async with get_sessionmaker()() as s:
        n = (await s.execute(select(func.coalesce(func.sum(LlmCall.input_tokens + LlmCall.output_tokens), 0)).where(LlmCall.run_id == run_id))).scalar_one()
    return int(n)


async def admit(agent: str) -> Admission:
    if await governed.get("agents_paused"):
        return Admission(False, "AI agents are paused by an administrator")
    key = f"agent_{agent}_enabled"
    if key in governed.GOVERNED and not await governed.get(key):
        return Admission(False, f"The {agent} agent is switched off by an administrator")
    budget = float(await governed.get("daily_token_budget"))
    if budget > 0 and await tokens_today() >= budget:
        return Admission(False, "The daily token budget for AI agents has been reached")
    return Admission(True)


async def check_run_budget(run_id: uuid.UUID) -> None:
    """Called between steps of a run. Raises BudgetExceeded when the run has used more than its token cap."""
    cap = float(await governed.get("run_token_cap"))
    used = await tokens_for_run(run_id)
    if used > cap:
        raise BudgetExceeded(f"this run used {used} tokens, over its cap of {int(cap)}")


async def _wall_clock() -> float:
    return float(await governed.get("run_wall_clock_seconds"))


def versions() -> dict:
    """What made this decision: policy version, a hash of each prompt, and the model names. Cheap and deterministic."""
    from app.agents import pariksha, policy, prahari, saathi
    from app.llm.client import get_llm

    def h(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:12]

    prompts = {"pariksha": h(pariksha.SYSTEM), "entailment": h(pariksha.ENTAIL_SYSTEM), "prahari_bio": h(prahari.BIO_SYSTEM), "saathi": h(getattr(saathi, "SYSTEM", ""))}
    llm = get_llm()
    return {"policy": policy.VERSION, "prompts": prompts, "mode": llm.mode, "provider": llm.provider, "models": getattr(llm, "model_names", {})}


def _graph_module(graph: str):
    from app.agents.graphs import dispute, document, post_approval

    return {"document": document, "dispute": dispute, "post_approval": post_approval}.get(graph)


async def _on_failure(graph: str, ctx: RunContext, payload: dict, why: str) -> None:
    """Every graph ends at a person (or a recorded no-op) when it cannot finish."""
    if graph == "verify":
        from app.agents.workflows import _escalate_on_failure

        await _escalate_on_failure(ctx, uuid.UUID(payload["profile_id"]), why)
        return
    mod = _graph_module(graph)
    if mod is not None:
        await mod.on_failure(ctx, payload, why)


async def _execute(graph: str, ctx: RunContext, payload: dict) -> Outcome:
    limit = await _wall_clock()
    try:
        if graph == "verify":
            from app.agents import workflows

            result = await asyncio.wait_for(workflows.run_verification(ctx, uuid.UUID(payload["profile_id"])), limit)
        else:
            result = await asyncio.wait_for(_graph_module(graph).run(ctx, payload), limit)
        await check_run_budget(ctx.run_id)  # over the token cap: the run still finished, but this is recorded for the admin view
        return Outcome("done", ctx.run_id, str(result)[:200])
    except asyncio.TimeoutError:
        await _on_failure(graph, ctx, payload, "it took too long")
        await ctx.finish("failed", "Stopped: wall-clock limit")
        return Outcome("timed_out", ctx.run_id, "it took too long")
    except BudgetExceeded as exc:
        await _on_failure(graph, ctx, payload, str(exc))
        await ctx.finish("failed", f"Stopped: {exc}")
        return Outcome("failed", ctx.run_id, str(exc))
    except Exception as exc:  # noqa: BLE001 - I-2
        log.exception("%s run failed", graph)
        await _on_failure(graph, ctx, payload, "an error occurred")
        await ctx.finish("failed", f"Error: {type(exc).__name__}")
        return Outcome("failed", ctx.run_id, type(exc).__name__)


async def dispatch(event_type: str, *, key: str, payload: dict, wait: bool = False) -> Outcome:
    """Start the graph for an event. Idempotent on `key`. With wait=True the run finishes before this returns (tests, admin tools); otherwise it is queued."""
    route = EVENT_ROUTES.get(event_type)
    if route is None:
        return Outcome("refused", None, f"Unknown event type: {event_type}")
    graph, agent = route
    profile_id = uuid.UUID(payload["profile_id"]) if payload.get("profile_id") else None

    async with get_sessionmaker()() as s:
        existing = (await s.execute(select(AgentRun).where(AgentRun.idempotency_key == key))).scalar_one_or_none()
        if existing is not None:
            return Outcome("deduped", existing.id, "this event was already handled")
        run = AgentRun(workflow=WORKFLOW_NAMES[graph], profile_id=profile_id, idempotency_key=key, versions=versions())
        s.add(run)
        try:
            await s.commit()
        except IntegrityError:  # two replays raced: the other one won
            await s.rollback()
            existing = (await s.execute(select(AgentRun).where(AgentRun.idempotency_key == key))).scalar_one()
            return Outcome("deduped", existing.id, "this event was already handled")
        run_id = run.id
    ctx = RunContext(run_id, WORKFLOW_NAMES[graph], profile_id)

    admission = await admit(agent)
    if not admission.ok:
        await _on_failure(graph, ctx, payload, admission.reason)
        await ctx.finish("failed", f"Refused: {admission.reason}")
        return Outcome("refused", run_id, admission.reason)

    if wait:
        return await _execute(graph, ctx, payload)

    from app import jobs

    await jobs.enqueue("sutradhar_run", {"graph": graph, "run_id": str(run_id), "payload": payload}, idempotency_key=f"sutradhar:{key}")
    return Outcome("started", run_id)


async def run_job(job: dict) -> None:
    """The queue handler: re-checks admission (a switch may have changed while the job waited), then runs."""
    graph, payload = job["graph"], job["payload"]
    profile_id = uuid.UUID(payload["profile_id"]) if payload.get("profile_id") else None
    ctx = RunContext(uuid.UUID(job["run_id"]), WORKFLOW_NAMES[graph], profile_id)
    agent = next(a for g, a in EVENT_ROUTES.values() if g == graph)
    admission = await admit(agent)
    if not admission.ok:
        await _on_failure(graph, ctx, payload, admission.reason)
        await ctx.finish("failed", f"Refused: {admission.reason}")
        return
    await _execute(graph, ctx, payload)


async def after_approval(profile_id: uuid.UUID, how: str) -> None:
    """Start the post-approval graph. Never raises: this runs after a decision is already saved, and nothing in it can change that decision."""
    try:
        await dispatch("profile.approved", key=f"approved:{profile_id}:{uuid.uuid4().hex[:12]}", payload={"profile_id": str(profile_id), "how": how})
    except Exception:  # noqa: BLE001
        log.exception("could not start the post-approval graph")
