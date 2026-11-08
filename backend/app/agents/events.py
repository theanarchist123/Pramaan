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

    def publish(self, event: dict[str, Any]) -> None:
        for q in list(self._subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:  # a stalled client must never block an agent
                pass


bus = EventBus()


class RunContext:
    def __init__(self, run_id: uuid.UUID, workflow: str, profile_id: uuid.UUID | None):
        self.run_id = run_id
        self.workflow = workflow
        self.profile_id = profile_id

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
