"""Per-key usage counts (API-10). One upsert per authenticated call; counts only."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKeyUsage


async def record(session: AsyncSession, key_id: uuid.UUID, *, throttled: bool = False) -> None:
    today = datetime.now(timezone.utc).date()
    stmt = insert(ApiKeyUsage).values(key_id=key_id, day=today, requests=1, throttled=1 if throttled else 0)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ApiKeyUsage.key_id, ApiKeyUsage.day],
        set_={"requests": ApiKeyUsage.requests + 1, "throttled": ApiKeyUsage.throttled + (1 if throttled else 0)},
    )
    await session.execute(stmt)


async def series(session: AsyncSession, key_id: uuid.UUID, days: int = 30) -> list[dict]:
    """Every day in the window, zero-filled, oldest first."""
    since = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    rows = {r.day: r for r in (await session.execute(select(ApiKeyUsage).where(ApiKeyUsage.key_id == key_id, ApiKeyUsage.day >= since))).scalars()}
    out = []
    for i in range(days):
        d: date = since + timedelta(days=i)
        r = rows.get(d)
        out.append({"day": d.isoformat(), "requests": r.requests if r else 0, "throttled": r.throttled if r else 0})
    return out
