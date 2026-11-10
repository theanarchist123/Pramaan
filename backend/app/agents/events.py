"""Agent activity: every step an agent takes becomes a persisted event and a live broadcast.

This is what the Mission Control UI renders — agents are visible, not magic.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import AgentEvent, AgentRun


class EventBus:
    """In-process pub/sub (single API worker). Swap for Redis pub/sub when scaling out."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subs.discard(q)

    def deliver_local(self, event: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # a stalled client must never block an agent
                pass

    def publish(self, event: dict[str, Any]) -> None:
        self.deliver_local(event)
        # Also fan out through Redis so API replicas and the separate worker process see each other's events
        # immediately. Best effort: the SSE endpoint also tails the table, so a missed message only costs latency.
        try:
            task = asyncio.get_running_loop().create_task(_redis_publish(event))
            _pending.add(task)
            task.add_done_callback(_pending.discard)
        except RuntimeError:
            pass


bus = EventBus()

CHANNEL = "pramaan:events"
ORIGIN = uuid.uuid4().hex  # which process published an event, so a process ignores its own echo
_pending: set[asyncio.Task] = set()


async def _redis_publish(event: dict[str, Any]) -> None:
    import json

    from app.core import redis as rd

    async def op(r):
        await r.publish(CHANNEL, json.dumps({**event, "_origin": ORIGIN}, default=str))

    async def nothing():
        return None

    await rd.call(op, nothing)


async def relay_from_redis() -> None:
    """Run for the life of the API: hand events published by OTHER processes to this process's SSE subscribers."""
    import json

    from app.core import redis as rd

    while True:
        r = rd.get_redis()
        if r is None:
            return  # Redis not configured: nothing to relay
        try:
            pubsub = r.pubsub()
            await pubsub.subscribe(CHANNEL)
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    event = json.loads(msg["data"])
                except (ValueError, TypeError):
                    continue
                if event.pop("_origin", None) != ORIGIN:
                    bus.deliver_local(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - Redis down: back off and retry; rd.call alerts on its own paths
            rd._mark_down(exc)
            await asyncio.sleep(5)


class RunContext:
    def __init__(self, run_id: uuid.UUID, workflow: str, profile_id: uuid.UUID | None):
        self.run_id = run_id
        self.workflow = workflow
        self.profile_id = profile_id
        from app.core import telemetry

        telemetry.current_run_id.set(run_id)  # model calls made for this run are recorded against it

    async def emit(
        self,
        agent: str,
        kind: str,
        message: str,
        data: dict[str, Any] | None = None,
        confidence: float | None = None,
    ) -> None:
        """kind: thought | tool | result | handoff | warning | error"""
        data = data or {}
        async with get_sessionmaker()() as session:
            row = AgentEvent(
                run_id=self.run_id, agent=agent, kind=kind, message=message,
                data=data, confidence=confidence,
            )
            session.add(row)
            await session.commit()
            event_id = row.id
        bus.publish(
            {
                "id": event_id,
                "run_id": str(self.run_id),
                "workflow": self.workflow,
                "profile_id": str(self.profile_id) if self.profile_id else None,
                "agent": agent,
                "kind": kind,
                "message": message,
                "data": data,
                "confidence": confidence,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def finish(self, status: str, summary: str) -> None:
        async with get_sessionmaker()() as session:
            run = await session.get(AgentRun, self.run_id)
            if run:
                run.status = status
                run.summary = summary
                run.ended_at = datetime.now(timezone.utc)
                await session.commit()
        bus.publish(
            {
                "id": None, "run_id": str(self.run_id), "workflow": self.workflow,
                "profile_id": str(self.profile_id) if self.profile_id else None,
                "agent": "system", "kind": "run_finished", "message": summary,
                "data": {"status": status}, "confidence": None,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )


async def start_run(workflow: str, profile_id: uuid.UUID | None = None) -> RunContext:
    async with get_sessionmaker()() as session:
        run = AgentRun(workflow=workflow, profile_id=profile_id)
        session.add(run)
        await session.commit()
        run_id = run.id
    return RunContext(run_id, workflow, profile_id)


async def recent_events(
    *, profile_id: uuid.UUID | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Newest-first history for UIs that connect after the fact."""
    async with get_sessionmaker()() as session:
        stmt = (
            select(AgentEvent, AgentRun)
            .join(AgentRun, AgentRun.id == AgentEvent.run_id)
            .order_by(AgentEvent.id.desc())
            .limit(limit)
        )
        if profile_id:
            stmt = stmt.where(AgentRun.profile_id == profile_id)
        rows = (await session.execute(stmt)).all()
    return [
        {
            "id": ev.id, "run_id": str(ev.run_id), "workflow": run.workflow,
            "profile_id": str(run.profile_id) if run.profile_id else None,
            "agent": ev.agent, "kind": ev.kind, "message": ev.message, "data": ev.data,
            "confidence": ev.confidence, "ts": ev.created_at.isoformat(),
        }
        for ev, run in rows
    ]
