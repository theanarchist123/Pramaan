"""The one checkpointer every agent graph shares (AGT-02).

State is checkpointed to Postgres (CHECKPOINT_BACKEND=postgres), so a case waiting for a reviewer survives a restart and the reviewer's decision
resumes the very same run. On Windows' default event loop psycopg's async mode cannot run, so an in-memory checkpointer is used there (dev only).
Each graph uses its own `thread_id` prefix, so graphs never read each other's state.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.config import get_settings

log = logging.getLogger("pramaan.graphs")
_saver = None
_pool = None


def thread(graph: str, subject: uuid.UUID | str, run_id: uuid.UUID | str) -> str:
    return f"{graph}:{subject}:{run_id}"


async def get_checkpointer():
    global _saver, _pool
    if _saver is not None:
        return _saver
    saver = None
    if get_settings().checkpoint_backend == "postgres":
        if "Proactor" in type(asyncio.get_running_loop()).__name__:
            log.warning("Windows' default event loop cannot run psycopg async: using the in-memory LangGraph checkpointer "
                        "(a paused review will not survive a restart here; Linux/Docker uses Postgres)")
        else:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool

            from app.jobs import psycopg_dsn

            _pool = AsyncConnectionPool(psycopg_dsn(), min_size=1, max_size=3, open=False, kwargs={"autocommit": True, "prepare_threshold": 0})
            await _pool.open()
            saver = AsyncPostgresSaver(_pool)
            await saver.setup()  # creates its tables if missing
    if saver is None:
        from langgraph.checkpoint.memory import MemorySaver

        saver = MemorySaver()
    _saver = saver
    return _saver


async def dispose_checkpointer() -> None:
    global _saver, _pool
    _saver = None
    if _pool is not None:
        await _pool.close()
    _pool = None
