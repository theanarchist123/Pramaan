"""Webhooks: signed, durable, SSRF-safe delivery of registry events to developers.

Receivers verify with the signing secret (shown once at creation):
    X-Pramaan-Signature: t=<unix>,v1=<hex hmac_sha256(secret, f"{t}.{raw_body}")>
Reject anything older than 5 minutes to stop replays.

Delivery is an outbox: an event becomes one WebhookJob row per subscriber. Workers claim due rows with
FOR UPDATE SKIP LOCKED, so a restart loses nothing and two replicas never send the same delivery twice.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import User, Webhook, WebhookDelivery, WebhookJob

log = logging.getLogger("pramaan.webhooks")

EVENTS: dict[str, str] = {
    "profile.approved": "A profile was verified and published to the directory.",
    "certificate.issued": "A signed certificate was issued (and logged publicly).",
    "review.queued": "A profile needs human review. Administrators only.",
}
ADMIN_ONLY = {"review.queued"}
RETRY_DELAYS = (30.0, 300.0)  # seconds before attempt 2 and 3 -> 3 attempts in total
TIMEOUT = 8.0
_tasks: set[asyncio.Task] = set()  # hold references so background deliveries aren't garbage-collected


class UnsafeURL(ValueError):
    pass


def _is_private(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast


def resolve_public(host: str, port: int) -> str:
    """Resolve once, refuse private/internal answers, and return the exact IP that was checked.
    The caller must connect to THIS address, so DNS cannot change its answer between check and use."""
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror as exc:
        raise UnsafeURL("Webhook host could not be resolved") from exc
    ips = [i[4][0] for i in infos]
    if not get_settings().webhook_allow_private and any(_is_private(ip) for ip in ips):
        raise UnsafeURL("Webhook URL may not point to a private or internal address")
    return ips[0]


def pin_url(url: str, ip: str) -> tuple[str, str, str]:
    """-> (url that connects to `ip`, Host header value, original hostname for TLS SNI + certificate check)."""
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    default = (parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)
    host_header = parsed.hostname if default else f"{parsed.hostname}:{port}"
    ip_host = f"[{ip}]" if ":" in ip else ip
    pinned = parsed._replace(netloc=f"{ip_host}:{port}").geturl()
    return pinned, host_header or "", parsed.hostname or ""


def check_url(url: str) -> str:
    """Reject non-HTTP(S) and private/internal targets. Called at creation AND before every delivery,
    because DNS can change after registration (rebinding)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURL("Webhook URL must be a valid http(s) address")
    if parsed.scheme == "http" and not get_settings().webhook_allow_private:
        raise UnsafeURL("Webhook URL must use https")
    resolve_public(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    return url


def sign(secret: str, timestamp: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, header: str, body: bytes, tolerance: int = 300) -> bool:
    """Reference verifier (the SDKs ship the same logic)."""
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts = int(parts["t"])
        expected = sign(secret, ts, body)
        return abs(time.time() - ts) <= tolerance and hmac.compare_digest(expected, parts["v1"])
    except (KeyError, ValueError):
        return False


async def _post(url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    """The one place that touches the network (tests replace it). Resolves the host itself, validates the
    answer and connects to that very IP (Host header + SNI keep the original name): no DNS-rebinding window."""
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    ip = await asyncio.to_thread(resolve_public, parsed.hostname or "", port)
    pinned, host_header, sni = pin_url(url, ip)
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        return await client.post(
            pinned, content=body, headers={**headers, "Host": host_header}, extensions={"sni_hostname": sni}
        )


def _envelope(delivery_id: str, event: str, data: dict[str, Any], created: datetime) -> bytes:
    envelope = {"id": delivery_id, "event": event, "data": data, "created_at": created.isoformat()}
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode()


REPLAY_HEADER = "X-Pramaan-Replay"
RETENTION_DAYS = 30


async def _attempt(
    url: str, secret: str, delivery_id: str, event: str, body: bytes, replay: bool = False
) -> tuple[bool, int | None, str, bool, int]:
    """One HTTP attempt. Returns (ok, status_code, error, retryable, duration_ms)."""
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Pramaan-Webhooks/1.0",
        "X-Pramaan-Event": event,
        "X-Pramaan-Delivery": delivery_id,
        "X-Pramaan-Signature": f"t={ts},v1={sign(secret, ts, body)}",
    }
    if replay:
        headers[REPLAY_HEADER] = "1"  # the same delivery id, sent again on request: an idempotent consumer can recognise it
    started = time.perf_counter()
    status_code: int | None = None
    error, retryable = "", True
    try:
        # DNS resolution blocks: do it off the event loop so a slow resolver can't stall the server.
        await asyncio.to_thread(check_url, url)
        resp = await _post(url, body, headers)
        status_code = resp.status_code
        ok = 200 <= status_code < 300
        if not ok:
            error = f"HTTP {status_code}"
    except UnsafeURL as exc:
        ok, error, retryable = False, str(exc)[:300], False  # never retry an unsafe target
    except Exception as exc:  # noqa: BLE001 - a subscriber's outage must never crash the app
        ok, error = False, type(exc).__name__
    return ok, status_code, error, retryable, int((time.perf_counter() - started) * 1000)


async def deliver(webhook_id: uuid.UUID, event: str, data: dict[str, Any], delivery_id: str | None = None) -> bool:
    """Deliver one event right now, with all retries in-process (used by the 'send test ping' button).
    Real events go through the durable outbox instead (schedule -> WebhookJob -> process_due)."""
    delivery_id = delivery_id or uuid.uuid4().hex
    async with get_sessionmaker()() as session:
        hook = await session.get(Webhook, webhook_id)
        if hook is None or not hook.active:
            return False
        url, secret = hook.url, hook.secret

    body = _envelope(delivery_id, event, data, datetime.now(timezone.utc))
    last_attempt = len(RETRY_DELAYS) + 1
    for attempt in range(1, last_attempt + 1):
        ok, status_code, error, retryable, ms = await _attempt(url, secret, delivery_id, event, body)
        async with get_sessionmaker()() as session:
            session.add(WebhookDelivery(
                webhook_id=webhook_id, delivery_id=delivery_id, event=event, attempt=attempt,
                status_code=status_code, ok=ok, error=error, duration_ms=ms,
            ))
            await session.commit()
        if ok:
            return True
        if not retryable or attempt == last_attempt:
            return False
        await asyncio.sleep(min(RETRY_DELAYS[attempt - 1], 5.0))  # a user is waiting on the ping: keep it short
    return False


# ---------------------------------------------------------------------------- durable outbox
async def enqueue(event: str, data: dict[str, Any]) -> int:
    """Write one pending job per subscribed webhook. Survives restarts; any worker may deliver it."""
    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                select(Webhook, User.role).join(User, User.id == Webhook.owner_id).where(Webhook.active.is_(True))
            )
        ).all()
        targets = [h.id for h, role in rows if event in h.events and (event not in ADMIN_ONLY or role == "admin")]
        for t in targets:
            session.add(WebhookJob(webhook_id=t, delivery_id=uuid.uuid4().hex, event=event, data=data))
        await session.commit()
    return len(targets)


async def _run_job(session: AsyncSession, job: WebhookJob) -> None:
    hook = await session.get(Webhook, job.webhook_id)
    if hook is None or not hook.active:
        job.status = "failed"  # paused or deleted since it was queued: drop it
        return
    replay = bool((job.data or {}).get("_replay"))
    data = {k: v for k, v in (job.data or {}).items() if k != "_replay"}
    body = _envelope(job.delivery_id, job.event, data, job.created_at)
    ok, status_code, error, retryable, ms = await _attempt(hook.url, hook.secret, job.delivery_id, job.event, body, replay=replay)
    job.attempt += 1
    session.add(WebhookDelivery(
        webhook_id=job.webhook_id, delivery_id=job.delivery_id, event=job.event, attempt=job.attempt,
        status_code=status_code, ok=ok, error=error, duration_ms=ms,
    ))
    if ok:
        job.status = "done"
    elif not retryable or job.attempt >= len(RETRY_DELAYS) + 1:
        job.status = "failed"
    else:
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAYS[job.attempt - 1])


async def replay(webhook_id: uuid.UUID, delivery_id: str) -> str:
    """Queue the same event again for one webhook. Returns "queued", "missing" (no such stored delivery, or it was purged) or "pending" (still being delivered)."""
    async with get_sessionmaker()() as session:
        orig = (await session.execute(select(WebhookJob).where(WebhookJob.webhook_id == webhook_id, WebhookJob.delivery_id == delivery_id)
                                      .order_by(WebhookJob.created_at.desc()).limit(1))).scalar_one_or_none()
        if orig is None:
            return "missing"
        if orig.status == "pending":
            return "pending"
        session.add(WebhookJob(webhook_id=webhook_id, delivery_id=delivery_id, event=orig.event,
                               data={**{k: v for k, v in (orig.data or {}).items() if k != "_replay"}, "_replay": True}))
        await session.commit()
    return "queued"


async def purge_old(days: int = RETENTION_DAYS) -> int:
    """Delete finished outbox rows (and so the stored payloads) older than `days`: payloads are kept only long enough to replay and debug."""
    from sqlalchemy import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_sessionmaker()() as session:
        res = await session.execute(delete(WebhookJob).where(WebhookJob.created_at < cutoff, WebhookJob.status.in_(("done", "failed"))))
        await session.commit()
        return res.rowcount or 0


async def purge_subject(session, slug: str) -> int:
    """Right to erasure: remove every stored payload that names this profile (top-level `slug`, or nested under `profile`)."""
    from sqlalchemy import delete, or_

    res = await session.execute(delete(WebhookJob).where(or_(WebhookJob.data["slug"].astext == slug, WebhookJob.data["profile"]["slug"].astext == slug)))
    return res.rowcount or 0


_last_purge = 0.0


async def process_due(*, force: bool = False, limit: int = 50) -> int:
    """Attempt due jobs. Each job is claimed with FOR UPDATE SKIP LOCKED, so two replicas/workers never send
    the same delivery at once; if a worker dies mid-attempt its lock is released and the job stays pending.
    `force` ignores the retry delay (tests, manual flush)."""
    done = 0
    while done < limit:
        async with get_sessionmaker()() as session:
            q = select(WebhookJob).where(WebhookJob.status == "pending")
            if not force:
                q = q.where(WebhookJob.next_attempt_at <= datetime.now(timezone.utc))
            job = (
                await session.execute(q.order_by(WebhookJob.next_attempt_at).limit(1).with_for_update(skip_locked=True))
            ).scalar_one_or_none()
            if job is None:
                break
            await _run_job(session, job)
            await session.commit()
        done += 1
    global _last_purge
    if time.time() - _last_purge > 3600:  # at most hourly
        _last_purge = time.time()
        try:
            await purge_old()
        except Exception:  # noqa: BLE001 - housekeeping must never stop deliveries
            log.exception("could not purge old webhook payloads")
    return done


async def _fan_out(event: str, data: dict[str, Any]) -> None:
    try:
        if await enqueue(event, data):
            await process_due()  # first attempts go out immediately; retries wait for the worker loop
    except Exception:  # noqa: BLE001 - announcing an event must never break the request that caused it
        log.exception("could not queue webhook event %s", event)


def schedule(event: str, data: dict[str, Any]) -> None:
    """Fire-and-forget. Call AFTER the database commit so rolled-back changes are never announced."""
    try:
        task = asyncio.get_running_loop().create_task(_fan_out(event, data))
    except RuntimeError:
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def profile_payload(p) -> dict[str, Any]:
    base = get_settings().public_base_url
    return {"slug": p.slug, "full_name": p.full_name, "headline": p.headline, "sector": p.sector,
            "state": p.state, "profile_url": f"{base}/p/{p.slug}"}


async def settle() -> None:
    """Wait for in-flight deliveries and flush the outbox, retries included (used by tests)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
    while await process_due(force=True):
        pass
