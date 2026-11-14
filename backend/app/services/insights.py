"""Privacy-safe profile insights: how many times a public page was opened and a certificate checked, per day.

Only counts are stored (profile, day, number). No IP address, user agent, account or any other trace of the visitor is recorded, and the
owner's own visits are not counted. Counts are deleted with the profile (ON DELETE CASCADE).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.models import ProfileDayStat

KINDS = {"views": ProfileDayStat.views, "cert_checks": ProfileDayStat.cert_checks}


async def record(profile_id: uuid.UUID, kind: str) -> None:
    """Add one to today's counter. Never raises into the request it is attached to."""
    if kind not in KINDS:
        raise ValueError(kind)
    try:
        today = datetime.now(timezone.utc).date()
        stmt = insert(ProfileDayStat).values(profile_id=profile_id, day=today, **{kind: 1})
        stmt = stmt.on_conflict_do_update(index_elements=["profile_id", "day"], set_={kind: KINDS[kind] + 1})
        async with get_sessionmaker()() as own:
            await own.execute(stmt)
            await own.commit()
    except Exception:  # noqa: BLE001 - a counter must never break a page load
        pass


async def summary(session: AsyncSession, profile_id: uuid.UUID) -> dict:
    totals = (
        await session.execute(
            select(func.coalesce(func.sum(ProfileDayStat.views), 0), func.coalesce(func.sum(ProfileDayStat.cert_checks), 0)).where(
                ProfileDayStat.profile_id == profile_id
            )
        )
    ).one()
    since: date = datetime.now(timezone.utc).date() - timedelta(days=6)
    rows = (
        await session.execute(select(ProfileDayStat).where(ProfileDayStat.profile_id == profile_id, ProfileDayStat.day >= since))
    ).scalars().all()
    by_day = {r.day: r for r in rows}
    last7 = []
    for i in range(7):
        d = since + timedelta(days=i)
        r = by_day.get(d)
        last7.append({"day": d.isoformat(), "views": r.views if r else 0, "checks": r.cert_checks if r else 0})
    return {"views_total": int(totals[0]), "checks_total": int(totals[1]), "last_7_days": last7}
