"""Background jobs behind one thin interface:

    await enqueue("verify_profile", {"profile_id": "...", "run_id": "..."}, idempotency_key="verify:<profile>")

Backends (JOB_BACKEND):
  inline         runs the task in this process. Dev and tests. (JOB_INLINE_WAIT=true runs it before returning.)
  procrastinate  a Postgres-backed queue: the job is a row, survives restarts and is run by `python -m app.worker`
                 (or the API's inline worker). No extra infrastructure: it is the database we already have.

Callers never import procrastinate; swapping the queue means changing this file only.

Idempotency: a second enqueue with the same key while the first is still WAITING returns the first (deduped=True)
instead of queueing a duplicate. A job that is already RUNNING is guarded by the caller's own state checks (for
example an AgentRun with status "running"), which is why those exist too.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

log = logging.getLogger("pramaan.jobs")

TaskFn = Callable[[dict[str, Any]], Awaitable[None]]
TASKS: dict[str, TaskFn] = {}
_inline_tasks: set[asyncio.Task] = set()  # keep references so detached inline jobs are not garbage-collected


@dataclass
class EnqueueResult:
    job_id: str
    deduped: bool
    backend: str


def task(name: str) -> Callable[[TaskFn], TaskFn]:
    """Register a job handler. Handlers take one JSON-able dict and must be idempotent (a job may run twice)."""

    def deco(fn: TaskFn) -> TaskFn:
        TASKS[name] = fn
        return fn

    return deco


def psycopg_dsn() -> str:
    """DATABASE_URL in the spelling psycopg/libpq wants (the app stores the asyncpg spelling)."""
    url = get_settings().database_url
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url.replace("ssl=", "sslmode=")


# ---------------------------------------------------------------------------- procrastinate wiring
_app: Any = None
_run_task: Any = None
_opened = False


def _procrastinate():
    """The Procrastinate App (created lazily; opening the pool is separate: see start())."""
    global _app, _run_task
    if _app is None:
        import procrastinate

        _app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=psycopg_dsn()))

        @_app.task(name="pramaan.run", queue="default")
        async def run(task_name: str, payload: dict[str, Any]) -> None:
            await _execute(task_name, payload)

        _run_task = run
    return _app


async def _execute(task_name: str, payload: dict[str, Any]) -> None:
    fn = TASKS.get(task_name)
    if fn is None:
        raise RuntimeError(f"unknown job task: {task_name}")
    await fn(payload)


def ensure_schema_sync() -> bool:
    """Create Procrastinate's tables if they are missing. True if it created them. Idempotent."""
    import procrastinate
    import psycopg
    from procrastinate import schema

    sql = schema.SchemaManager(procrastinate.PsycopgConnector(conninfo=psycopg_dsn())).get_schema()
    with psycopg.connect(psycopg_dsn(), autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('public.procrastinate_jobs')").fetchone()[0] is not None:
            return False
        conn.execute(sql)
        return True


async def start() -> None:
    """Open the queue's connection pool (API and worker call this once at startup)."""
    global _opened
    if get_settings().job_backend != "procrastinate" or _opened:
        return
    if "Proactor" in type(asyncio.get_running_loop()).__name__:
        # psycopg's async mode cannot run on Windows' default event loop (which Playwright needs). Linux (where this is
        # deployed) is unaffected; on Windows dev machines use the inline backend.
        raise RuntimeError("JOB_BACKEND=procrastinate needs a selector event loop; on Windows use JOB_BACKEND=inline")
    await _procrastinate().open_async()
    _opened = True


async def stop() -> None:
    global _opened
    if _opened and _app is not None:
        await _app.close_async()
    _opened = False


async def run_worker(*, wait: bool = True) -> None:
    """Process queued jobs (forever when wait=True). Used by `python -m app.worker` and by tests with wait=False."""
    if get_settings().job_backend != "procrastinate":
        return
    app = _procrastinate()
    if not _opened:
        await start()
    await app.run_worker_async(wait=wait, install_signal_handlers=False, concurrency=4)


# ---------------------------------------------------------------------------- the interface
async def enqueue(task_name: str, payload: dict[str, Any], idempotency_key: str | None = None) -> EnqueueResult:
    if task_name not in TASKS:
        raise ValueError(f"unknown job task: {task_name}")
    s = get_settings()

    if s.job_backend == "procrastinate":
        from procrastinate import exceptions

        if not _opened:
            await start()
        _procrastinate()
        try:
            job_id = await _run_task.configure(queueing_lock=idempotency_key).defer_async(task_name=task_name, payload=payload)
        except exceptions.AlreadyEnqueued:
            return EnqueueResult(job_id="", deduped=True, backend="procrastinate")
        return EnqueueResult(job_id=str(job_id), deduped=False, backend="procrastinate")

    # inline
    job_id = uuid.uuid4().hex
    if s.job_inline_wait:
        await _safe_run(task_name, payload)
    else:
        t = asyncio.get_running_loop().create_task(_safe_run(task_name, payload))
        _inline_tasks.add(t)
        t.add_done_callback(_inline_tasks.discard)
    return EnqueueResult(job_id=job_id, deduped=False, backend="inline")


async def _safe_run(task_name: str, payload: dict[str, Any]) -> None:
    try:
        await _execute(task_name, payload)
    except Exception:  # noqa: BLE001 - a failing job must not take the API down; handlers escalate on their own
        log.exception("job %s failed", task_name)


async def drain() -> None:
    """Wait for detached inline jobs (tests, shutdown)."""
    while _inline_tasks:
        await asyncio.gather(*list(_inline_tasks), return_exceptions=True)


# ---------------------------------------------------------------------------- the jobs
@task("sutradhar_run")
async def _sutradhar_run(payload: dict[str, Any]) -> None:
    from app.agents import sutradhar

    await sutradhar.run_job(payload)


@task("verify_profile")
async def _verify_profile(payload: dict[str, Any]) -> None:
    from app.agents.events import RunContext
    from app.agents.workflows import WORKFLOW, run_verification

    pid = uuid.UUID(payload["profile_id"])
    await run_verification(RunContext(uuid.UUID(payload["run_id"]), WORKFLOW, pid), pid)
