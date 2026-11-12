"""Nigrani ("the watcher"): notices a spike of agent failures and opens ONE incident per kind of failure (AGT-13, spec 8.5).

It only counts and records. It never changes code, switches anything or notifies anyone outside the admin console. A failure caused by a kill switch, a
budget or a person's own action ("Refused:", "Stopped:") is the system working as designed, not a bug, so it is not counted.
Run it from cron or the admin console: `python -m app.cli nigrani-scan`.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Incident

NOT_A_BUG = ("Refused:", "Stopped:", "Paused:")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def safe_summary(text: str, limit: int = 160) -> str:
    """What may be stored in an incident: no email addresses, phone numbers or ids."""
    t = _UUID.sub("<id>", text or "")
    t = _EMAIL.sub("<email>", t)
    t = _PHONE.sub("<number>", t)
    return t[:limit]


def signature(workflow: str, summary: str) -> str:
    """The same bug gives the same signature whatever ids or numbers it mentions."""
    t = _UUID.sub("", summary or "")
    t = re.sub(r"\d+", "", t.lower())
    words = re.findall(r"[a-z_]{2,}", t)[:6]
    return f"agent:{workflow}:{'-'.join(words) or 'unknown'}"[:160]


@dataclass
class Signal:
    signature: str
    workflow: str
    count: int
    total: int
    sample: str = ""
    rate: float = 0.0
    ids: list = field(default_factory=list)


async def scan(session: AsyncSession, *, window_minutes: int = 60, min_count: int = 5, min_rate: float = 0.3) -> list[Signal]:
    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    runs = (await session.execute(select(AgentRun).where(AgentRun.started_at >= since))).scalars().all()
    totals: Counter[str] = Counter(r.workflow for r in runs)
    groups: dict[str, list[AgentRun]] = {}
    for r in runs:
        if r.status == "failed" and not (r.summary or "").startswith(NOT_A_BUG):
            groups.setdefault(signature(r.workflow, r.summary), []).append(r)
    out = []
    for sig, rs in groups.items():
        wf = rs[0].workflow
        rate = len(rs) / max(1, totals[wf])
        if len(rs) >= min_count and rate >= min_rate:
            out.append(Signal(sig, wf, len(rs), totals[wf], safe_summary(rs[0].summary), round(rate, 3), [str(r.id) for r in rs[:10]]))
    return sorted(out, key=lambda s: -s.count)


async def record(session: AsyncSession, signals: list[Signal]) -> list[Incident]:
    """Open an incident per new signature; refresh the one that is already open. Returns only the newly opened ones. Caller commits."""
    opened = []
    for sg in signals:
        inc = (await session.execute(select(Incident).where(Incident.signature == sg.signature, Incident.status.in_(("open", "patch_proposed"))))).scalars().first()
        if inc is None:
            inc = Incident(signature=sg.signature, summary=sg.sample, count=sg.count)
            session.add(inc)
            opened.append(inc)
        else:
            inc.count, inc.summary, inc.last_seen = sg.count, sg.sample, datetime.now(timezone.utc)
    return opened
