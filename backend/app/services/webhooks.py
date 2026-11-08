"""Webhooks: signed, retried, SSRF-safe delivery of registry events to developers.

Receivers verify with the signing secret (shown once at creation):
    X-Pramaan-Signature: t=<unix>,v1=<hex hmac_sha256(secret, f"{t}.{raw_body}")>
Reject anything older than 5 minutes to stop replays.
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
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import User, Webhook, WebhookDelivery

log = logging.getLogger("pramaan.webhooks")

EVENTS: dict[str, str] = {
    "profile.approved": "A profile was verified and published to the directory.",
    "certificate.issued": "A signed certificate was issued (and logged publicly).",
    "review.queued": "A profile needs human review. Administrators only.",
}
ADMIN_ONLY = {"review.queued"}
RETRY_DELAYS = (1.0, 4.0)  # seconds between attempts -> 3 attempts in total
TIMEOUT = 8.0
_tasks: set[asyncio.Task] = set()  # hold references so background deliveries aren't garbage-collected


class UnsafeURL(ValueError):
    pass


def _is_private(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast


def check_url(url: str) -> str:
    """Reject non-HTTP(S) and private/internal targets. Called at creation AND before every delivery,
    because DNS can change after registration (rebinding)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURL("Webhook URL must be a valid http(s) address")
    allow_private = get_settings().webhook_allow_private
    if parsed.scheme == "http" and not allow_private:
        raise UnsafeURL("Webhook URL must use https")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise UnsafeURL("Webhook host could not be resolved") from exc
    if not allow_private and any(_is_private(i[4][0]) for i in infos):
        raise UnsafeURL("Webhook URL may not point to a private or internal address")
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
    """The one place that touches the network (tests replace it)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
        return await client.post(url, content=body, headers=headers)


async def deliver(webhook_id: uuid.UUID, event: str, data: dict[str, Any], delivery_id: str | None = None) -> bool:
    """Deliver one event with retries; every attempt is recorded. Returns True on success."""
    delivery_id = delivery_id or uuid.uuid4().hex
    async with get_sessionmaker()() as session:
        hook = await session.get(Webhook, webhook_id)
        if hook is None or not hook.active:
            return False
        url, secret = hook.url, hook.secret

    envelope = {
        "id": delivery_id, "event": event, "data": data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False).encode()
    last_attempt = len(RETRY_DELAYS) + 1

    for attempt in range(1, last_attempt + 1):
        ts = int(time.time())
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Pramaan-Webhooks/1.0",
            "X-Pramaan-Event": event,
            "X-Pramaan-Delivery": delivery_id,
            "X-Pramaan-Signature": f"t={ts},v1={sign(secret, ts, body)}",
        }
        started = time.perf_counter()
        status_code: int | None = None
        error = ""
        retryable = True
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
        async with get_sessionmaker()() as session:
            session.add(WebhookDelivery(
                webhook_id=webhook_id, delivery_id=delivery_id, event=event, attempt=attempt,
                status_code=status_code, ok=ok, error=error,
                duration_ms=int((time.perf_counter() - started) * 1000),
            ))
            await session.commit()
        if ok:
            return True
        if not retryable or attempt == last_attempt:
            return False
        await asyncio.sleep(RETRY_DELAYS[attempt - 1])
    return False


async def _fan_out(event: str, data: dict[str, Any]) -> None:
    async with get_sessionmaker()() as session:
        rows = (
            await session.execute(
                select(Webhook, User.role).join(User, User.id == Webhook.owner_id).where(Webhook.active.is_(True))
            )
        ).all()
        targets = [h.id for h, role in rows if event in h.events and (event not in ADMIN_ONLY or role == "admin")]
    await asyncio.gather(*(deliver(t, event, data) for t in targets), return_exceptions=True)


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
    """Wait for in-flight deliveries (used by tests)."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
