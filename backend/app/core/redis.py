"""Redis, used ONLY for things that are fine to lose and need speed or sharing across replicas:
rate-limit counters, short locks, small caches and live-event fan-out. It is never the source of truth: durable state
(jobs, runs, reviews) lives in Postgres.

If Redis is not configured (REDIS_URL empty) everything works in-process. If it is configured but DOWN, calls fall
back to in-process behaviour and an ALERT is logged (at most once a minute), because per-process limits are weaker
than shared ones and someone should know.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.config import get_settings

log = logging.getLogger("pramaan.redis")
T = TypeVar("T")

_client: Any = None
_client_url = ""
_down_since: float | None = None
_last_alert = 0.0
ALERT_EVERY = 60.0


def get_redis():
    """The shared async client, or None when Redis is not configured."""
    global _client, _client_url
    url = get_settings().redis_url.strip()
    if not url:
        return None
    if _client is None or _client_url != url:
        import redis.asyncio as aioredis

        # Short timeouts: a slow Redis must never make requests slow; we would rather fall back.
        _client = aioredis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25, decode_responses=True)
        _client_url = url
    return _client


def _mark_down(exc: Exception) -> None:
    global _down_since, _last_alert
    now = time.monotonic()
    if _down_since is None:
        _down_since = now
    if now - _last_alert >= ALERT_EVERY:
        _last_alert = now
        log.error(
            "ALERT: Redis is unreachable (%s). Rate limits and locks are falling back to per-process memory "
            "(weaker with more than one replica). Down for %.0fs.", type(exc).__name__, now - _down_since,
        )


def _mark_up() -> None:
    global _down_since
    if _down_since is not None:
        log.warning("Redis is reachable again")
        _down_since = None


async def call(op: Callable[[Any], Awaitable[T]], fallback: Callable[[], Awaitable[T] | T]) -> T:
    """Run `op(redis)`; on any Redis failure (or when Redis is not configured) run `fallback()` instead."""
    r = get_redis()
    if r is not None:
        try:
            out = await op(r)
            _mark_up()
            return out
        except Exception as exc:  # noqa: BLE001 - connection, timeout, response errors: all mean "use the fallback"
            _mark_down(exc)
    result = fallback()
    if hasattr(result, "__await__"):
        return await result  # type: ignore[no-any-return]
    return result  # type: ignore[return-value]


def status() -> dict[str, Any]:
    """For the admin status page."""
    configured = bool(get_settings().redis_url.strip())
    return {
        "configured": configured,
        "state": "disabled" if not configured else ("down" if _down_since is not None else "up"),
        "fallback_active": configured and _down_since is not None,
    }


async def close() -> None:
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except Exception:  # noqa: BLE001
            pass
    _client = None
