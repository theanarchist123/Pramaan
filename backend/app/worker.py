"""Background worker: everything that must not live (and die) inside a web request.

    python -m app.worker

* webhook outbox   - first attempts, retries with backoff (rows claimed with SKIP LOCKED)
* scheduled email  - messages an admin scheduled (rows claimed with SKIP LOCKED)
* sandbox jobs     - AI-written plugin checks, which need Docker. Run this process on a host that has it;
                     the API image deliberately does not, and queues the job instead.

By default the API also runs this loop (WORKER_INLINE=true) so a single-container setup just works. For
production set WORKER_INLINE=false on the API and run one or more workers; any number is safe.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.agents.events import RunContext
from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker
from app.models import CodeChange

log = logging.getLogger("pramaan.worker")


async def claim_change() -> tuple[uuid.UUID, RunContext] | None:
    """Take one queued plugin job. SKIP LOCKED + an immediate status change = one worker per job."""
    async with get_sessionmaker()() as session:
        row = (
            await session.execute(
                select(CodeChange).where(CodeChange.status == "queued").order_by(CodeChange.created_at)
                .limit(1).with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row.status = "proposed"  # now in progress
        run_id = row.run_id
        await session.commit()
    if run_id is None:
        from app.agents.events import start_run

        return row.id, await start_run("shilpkar_plugin")
    return row.id, RunContext(run_id, "shilpkar_plugin", None)


async def run_sandbox_jobs() -> int:
    from app.api.builder import process_change

    n = 0
    while (claimed := await claim_change()) is not None:
        change_id, ctx = claimed
        await process_change(change_id, ctx)
        n += 1
    return n


_last_guest_purge = 0.0


async def purge_guests_if_due(every_seconds: float = 6 * 3600) -> None:
    """Delete guests (and their drafts) older than 14 days, at most every few hours."""
    import time

    global _last_guest_purge
    if time.monotonic() - _last_guest_purge < every_seconds and _last_guest_purge:
        return
    _last_guest_purge = time.monotonic()
    from app.services.guests import purge_stale_guests

    async with get_sessionmaker()() as session:
        n = await purge_stale_guests(session, days=14)
        await session.commit()
    if n:
        log.info("purged %d stale guest account(s)", n)


async def tick(*, sandbox: bool = True) -> None:
    from app.services import outreach, webhooks

    await purge_guests_if_due()
    await webhooks.process_due()
    if get_settings().outreach_scheduler:
        await outreach.send_due()
    if sandbox:
        await run_sandbox_jobs()


async def run_forever(interval: float = 5.0, *, sandbox: bool = True) -> None:
    while True:
        try:
            await tick(sandbox=sandbox)
        except Exception:  # noqa: BLE001 - the loop must survive a bad tick
            log.exception("worker tick failed")
        await asyncio.sleep(interval)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    log.info("worker started")
    from app import jobs

    try:
        await jobs.start()
        # The bespoke loop (webhook outbox, scheduled email, sandbox) and the Postgres job queue side by side.
        await asyncio.gather(run_forever(), jobs.run_worker())
    finally:
        await jobs.stop()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
