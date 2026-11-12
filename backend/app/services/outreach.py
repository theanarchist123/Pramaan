"""Outreach: find who needs a nudge, draft it (Doot), and send only what a human approved."""

from __future__ import annotations

import asyncio
import hmac
import hashlib
import base64
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
from app.models import EmailSuppression, Certificate, Consent, OutboxMessage, Profile, ReviewItem, User

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


# ---- safeguards (AGT-09): enforced in send(), the one place every email passes, so no route (immediate, scheduled, retried) can skip them -------
FREQUENCY_CAP = 3          # most emails to one address ...
FREQUENCY_WINDOW_DAYS = 30  # ... in this many days; the next one waits for a person to decide


def _norm(email: str) -> str:
    return email.strip().lower()


def email_hash(email: str) -> str:
    """Keyed hash of the address (the suppression list never stores addresses)."""
    return hmac.new(get_settings().jwt_secret.encode(), _norm(email).encode(), hashlib.sha256).hexdigest()


def unsubscribe_token(email: str) -> str:
    """address (base64url) + a signature only this server can make, so nobody can unsubscribe someone else or mint a token for a made-up address."""
    raw = base64.urlsafe_b64encode(_norm(email).encode()).decode().rstrip("=")
    return f"{raw}.{hmac.new(get_settings().jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]}"


def email_from_token(token: str) -> str | None:
    try:
        raw, sig = token.rsplit(".", 1)
        good = hmac.new(get_settings().jwt_secret.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, good):
            return None
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


async def suppress(session: AsyncSession, email: str, reason: str = "") -> None:
    if not (await session.execute(select(EmailSuppression).where(EmailSuppression.email_hash == email_hash(email)))).first():
        session.add(EmailSuppression(email_hash=email_hash(email), reason=reason[:200]))


async def is_suppressed(session: AsyncSession, email: str) -> bool:
    return (await session.execute(select(EmailSuppression.id).where(EmailSuppression.email_hash == email_hash(email)))).first() is not None


async def _recent_sent(session: AsyncSession, email: str) -> int:
    since = _now() - timedelta(days=FREQUENCY_WINDOW_DAYS)
    rows = (await session.execute(select(OutboxMessage.to_email).where(OutboxMessage.status == "sent", OutboxMessage.sent_at > since))).scalars().all()
    return sum(1 for e in rows if _norm(e) == _norm(email))


def _with_unsubscribe(body: str, email: str) -> str:
    """The system, not the model, appends this (invariant I-7 concerns links the MODEL adds)."""
    url = f"{get_settings().api_base_url.rstrip('/')}/v1/outreach/unsubscribe?token={unsubscribe_token(email)}"
    return f"{body.rstrip()}\n\n--\nYou are getting this because of your Pramaan record. To stop these emails, open:\n{url}\n"


async def send(session: AsyncSession, msg: OutboxMessage) -> OutboxMessage:
    """Deliver one message. Without SMTP configured this is a recorded dry run, not a silent no-op."""
    if "\n" in msg.to_email or "\r" in msg.to_email or "@" not in msg.to_email:
        msg.status, msg.error = "draft", "invalid recipient address"
        return msg
    # Safeguards first, in this order, for EVERY path (a dry run must not pretend to send to someone who opted out).
    if await is_suppressed(session, msg.to_email):
        msg.status, msg.error = "discarded", "recipient has opted out: not sent"
        return msg
    if msg.profile_id is not None and await _opted_out(session, msg.profile_id):
        msg.status, msg.error = "discarded", "outreach consent was withdrawn: not sent"
        return msg
    if await _recent_sent(session, msg.to_email) >= FREQUENCY_CAP:
        msg.status, msg.error = "draft", f"frequency cap: already {FREQUENCY_CAP} emails to this address in {FREQUENCY_WINDOW_DAYS} days; a person decides"
        return msg
    if not get_settings().smtp_host:
        msg.status, msg.sent_at, msg.error = "sent", _now(), "dry-run: SMTP not configured, nothing was emailed"
        return msg
    try:
        await asyncio.to_thread(_smtp_send, msg.to_email, msg.subject, _with_unsubscribe(msg.body, msg.to_email))
        msg.status, msg.sent_at, msg.error = "sent", _now(), ""
    except Exception as exc:  # noqa: BLE001
        msg.status, msg.error = "draft", f"send failed: {type(exc).__name__}"  # back to draft; a human decides
        log.warning("outreach send failed: %s", exc)
    return msg


async def send_due(now: datetime | None = None) -> int:
    """Scheduler tick: send messages SCHEDULED (by an admin, or by the welcome policy) whose time has come and only inside the sending hours. Drafts are never sent."""
    now = now or _now()
    if next_send_window(now) > now:
        return 0
    async with get_sessionmaker()() as session:
        due = (
            await session.execute(
                select(OutboxMessage)
                .where(OutboxMessage.status == "scheduled", OutboxMessage.scheduled_for <= now)
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


# ---- policy (AGT-09) ----------------------------------------------------------------------------------------------------------------------
# Only a FIXED template (no model wording) of a low-risk kind may go out without a person reading it, and only while the governed switch is on.
AUTO_SEND_KINDS = {"welcome_share"}
SEND_START_HOUR, SEND_END_HOUR = 9, 18  # India time: nobody is emailed at night
_IST = timezone(timedelta(hours=5, minutes=30))


def next_send_window(now: datetime) -> datetime:
    """`now` if it is inside the sending hours (09:00-18:00 India time), otherwise the next 09:00."""
    local = now.astimezone(_IST)
    start = local.replace(hour=SEND_START_HOUR, minute=0, second=0, microsecond=0)
    if local < start:
        return start.astimezone(now.tzinfo or timezone.utc)
    if local.hour >= SEND_END_HOUR:
        return (start + timedelta(days=1)).astimezone(now.tzinfo or timezone.utc)
    return now


async def welcome_if_allowed(session: AsyncSession, profile_id, now: datetime | None = None) -> OutboxMessage | None:
    """Send the fixed welcome email for a profile that has an active certificate, if and only if the governed switch is on.
    Once per profile. Goes through send(), so suppression, withdrawn consent and the frequency cap all still apply."""
    from app.services import governed

    if not await governed.get("outreach_autosend_welcome"):
        return None
    now = now or _now()
    profile = await session.get(Profile, profile_id)
    if profile is None or profile.status != "approved" or profile.owner_id is None or profile.is_demo:
        return None
    cert = (await session.execute(select(Certificate).where(Certificate.profile_id == profile.id, Certificate.revoked_at.is_(None))
                                  .order_by(Certificate.issued_at.desc()))).scalars().first()
    if cert is None:
        return None
    already = (await session.execute(select(OutboxMessage.id).where(OutboxMessage.profile_id == profile.id, OutboxMessage.kind == "welcome_share",
                                                                    OutboxMessage.status != "discarded"))).first()
    if already:
        return None
    owner = await session.get(User, profile.owner_id)
    if owner is None:
        return None
    facts = {"first_name": (owner.name or profile.full_name).split()[0], "status": profile.status, "claims": len(profile.claims),
             "verified": sum(1 for c in profile.claims if c.status != "self")}
    subject, body = doot.fixed_message("welcome_share", facts, doot.links_for(profile.slug, cert.code))
    msg = OutboxMessage(profile_id=profile.id, kind="welcome_share", to_email=owner.email, subject=subject, body=body, status="draft")
    session.add(msg)
    window = next_send_window(now)
    if window > now:
        msg.status, msg.scheduled_for = "scheduled", window  # picked up by send_due() when the window opens
    else:
        await send(session, msg)
    return msg
