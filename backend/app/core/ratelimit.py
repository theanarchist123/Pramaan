"""Rate limits and login lockout.

Shared across replicas through Redis when it is configured and reachable; otherwise a per-process sliding window
(with an alert if Redis was expected, see core/redis.py). All entry points are async because Redis is.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings
from app.core import redis as rd

# --------------------------------------------------------------------------- sliding window
# KEYS[1]=zset  ARGV[1]=now  ARGV[2]=window seconds  ARGV[3]=limit  ARGV[4]=unique member
# Atomic: trim old hits, refuse if full, otherwise record this hit. Returns {allowed, remaining}.
_LUA_WINDOW = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, ARGV[1] - ARGV[2])
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[3]) then return {0, 0} end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], math.ceil(ARGV[2]) + 1)
return {1, tonumber(ARGV[3]) - n - 1}
"""

_hits: dict[str, deque[float]] = defaultdict(deque)
_seq = 0


def _local_window(key: str, limit: int, window: float = 60.0) -> tuple[bool, int]:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return False, 0
    q.append(now)
    return True, limit - len(q)


async def check_rate_limit(key: str, limit_per_min: int) -> tuple[bool, int]:
    """Returns (allowed, remaining)."""
    global _seq
    _seq += 1
    member = f"{time.time_ns()}-{_seq}"

    async def shared(r):
        allowed, remaining = await r.eval(_LUA_WINDOW, 1, f"rl:{key}", time.time(), 60, limit_per_min, member)
        return bool(allowed), int(remaining)

    return await rd.call(shared, lambda: _local_window(key, limit_per_min))


def ip_limit(scope: str, limit_per_min: int):
    """FastAPI dependency: per-client-IP limit for unauthenticated endpoints (login, register, search)."""

    async def _dep(request: Request) -> None:
        if not get_settings().ip_rate_limits:
            return
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[-1].strip() if fwd else (request.client.host if request.client else "?")
        ok, remaining = await check_rate_limit(f"ip:{scope}:{ip}", limit_per_min)
        request.state.rate_limit = (limit_per_min, remaining)
        if not ok:
            raise HTTPException(429, "Too many requests - slow down", headers={"Retry-After": "60"})

    return _dep


# --------------------------------------------------------------------------- login lockout
LOCKOUT_FAILS, LOCKOUT_SECONDS = 5, 15 * 60
_failures: dict[str, deque[float]] = defaultdict(deque)


def _local_failures(identity: str) -> int:
    now = time.monotonic()
    q = _failures[identity]
    while q and now - q[0] > LOCKOUT_SECONDS:
        q.popleft()
    return len(q)


async def login_locked(identity: str) -> bool:
    async def shared(r):
        return int(await r.get(f"lf:{identity}") or 0) >= LOCKOUT_FAILS

    return await rd.call(shared, lambda: _local_failures(identity) >= LOCKOUT_FAILS)


async def login_failed(identity: str) -> None:
    async def shared(r):
        n = await r.incr(f"lf:{identity}")
        if n == 1:
            await r.expire(f"lf:{identity}", LOCKOUT_SECONDS)

    await rd.call(shared, lambda: _failures[identity].append(time.monotonic()))


async def login_ok(identity: str) -> None:
    async def shared(r):
        await r.delete(f"lf:{identity}")

    await rd.call(shared, lambda: _failures.pop(identity, None))


def reset() -> None:
    """Tests: forget all in-process counters (Redis keys expire on their own)."""
    _hits.clear()
    _failures.clear()
