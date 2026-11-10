"""Outreach: find who needs a nudge, draft it (Doot), and send only what a human approved."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import doot
from app.agents.events import RunContext
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Certificate, Consent, OutboxMessage, Profile, ReviewItem, User

log = logging.getLogger("pramaan.outreach")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _opted_out(session: AsyncSession, profile_id) -> bool:
    c = (
        await session.execute(
            select(Consent).where(Consent.profile_id == profile_id, Consent.kind == "outreach").order_by(Consent.created_at.desc())
        )
    ).scalars().first()
    return bool(c and not c.granted)


async def suggest(
    session: AsyncSession, ctx: RunContext, *, review_after_hours: float = 24, idle_after_hours: float = 48
) -> list[OutboxMessage]:
    """Create DRAFTS (never sends). One per (profile, kind), ever — re-running is harmless."""
    existing = {
        (m.profile_id, m.kind)
        for m in (await session.execute(select(OutboxMessage).where(OutboxMessage.status != "discarded"))).scalars()
    }
    created: list[OutboxMessage] = []
    now = _now()

    profiles = (await session.execute(select(Profile).where(Profile.owner_id.is_not(None), Profile.is_demo.is_(False)))).scalars().all()
    for p in profiles:
        owner = await session.get(User, p.owner_id)
        if owner is None or await _opted_out(session, p.id):
            continue
        kind: str | None = None
        facts = {"first_name": (owner.name or p.full_name).split()[0] if (owner.name or p.full_name) else "",
                 "status": p.status, "claims": len(p.claims), "verified": sum(1 for c in p.claims if c.status != "self")}
        cert_code = None

        if p.status == "approved":
            cert = (await session.execute(
                select(Certificate).where(Certificate.profile_id == p.id, Certificate.revoked_at.is_(None))
                .order_by(Certificate.issued_at.desc()))).scalars().first()
            if cert:
                kind, cert_code = "welcome_share", cert.code
        elif p.status == "pending_review":
            item = (await session.execute(
                select(ReviewItem).where(ReviewItem.profile_id == p.id, ReviewItem.status == "open")
                .order_by(ReviewItem.created_at))).scalars().first()
            waited = item and (now - item.created_at) >= timedelta(hours=review_after_hours)
            if item and waited and "document" in (item.reason or "").lower():
                kind = "needs_document"
                facts["reasons"] = item.reason[:200]
        elif p.status == "draft":
            if p.claims and (now - p.updated_at) >= timedelta(hours=idle_after_hours):
                kind = "finish_profile"

        if not kind or (p.id, kind) in existing:
            continue
        subject, body = await doot.draft_message(ctx, kind, facts, doot.links_for(p.slug, cert_code))
        msg = OutboxMessage(profile_id=p.id, kind=kind, to_email=owner.email, subject=subject, body=body, status="draft")
        session.add(msg)
        created.append(msg)
        existing.add((p.id, kind))
    await session.flush()
    await ctx.emit("Doot", "result", f"{len(created)} draft message(s) are waiting for your approval")
    return created


def _smtp_send(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


async def send(session: AsyncSession, msg: OutboxMessage) -> OutboxMessage:
    """Deliver one message. Without SMTP configured this is a recorded dry run, not a silent no-op."""
    if "\n" in msg.to_email or "\r" in msg.to_email or "@" not in msg.to_email:
        msg.status, msg.error = "draft", "invalid recipient address"
        return msg
    if not get_settings().smtp_host:
        msg.status, msg.sent_at, msg.error = "sent", _now(), "dry-run: SMTP not configured, nothing was emailed"
        return msg
    try:
        await asyncio.to_thread(_smtp_send, msg.to_email, msg.subject, msg.body)
        msg.status, msg.sent_at, msg.error = "sent", _now(), ""
    except Exception as exc:  # noqa: BLE001
        msg.status, msg.error = "draft", f"send failed: {type(exc).__name__}"  # back to draft; a human decides
        log.warning("outreach send failed: %s", exc)
    return msg


async def send_due() -> int:
    """Scheduler tick: send messages an admin SCHEDULED whose time has come. Drafts are never sent."""
    async with get_sessionmaker()() as session:
        due = (
            await session.execute(
                select(OutboxMessage)
                .where(OutboxMessage.status == "scheduled", OutboxMessage.scheduled_for <= _now())
                # Row locks: with several replicas/workers each message is claimed by exactly one of them,
                # the others skip it, so nobody gets the same email twice.
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for m in due:
            await send(session, m)
        await session.commit()
        return len(due)


async def scheduler_loop(interval: float = 30.0) -> None:  # kept for callers that only want email
    while True:
        try:
            await send_due()
        except Exception:  # noqa: BLE001 - the loop must survive a bad tick
            log.exception("outreach scheduler tick failed")
        await asyncio.sleep(interval)
