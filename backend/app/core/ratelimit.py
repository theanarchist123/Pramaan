"""Tiny in-process sliding-window limiter (per API key). Swap for Redis if scaled out."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, limit_per_min: int) -> tuple[bool, int]:
    """Returns (allowed, remaining)."""
    now = time.monotonic()
    window = _hits[key]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit_per_min:
        return False, 0
    window.append(now)
    return True, limit_per_min - len(window)


def reset() -> None:
    _hits.clear()


def ip_limit(scope: str, limit_per_min: int):
    """FastAPI dependency: per-client-IP limit for unauthenticated endpoints (login, register, search)."""
    async def _dep(request: Request) -> None:
        if not get_settings().ip_rate_limits:
            return
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[-1].strip() if fwd else (request.client.host if request.client else "?")
        ok, _ = check_rate_limit(f"ip:{scope}:{ip}", limit_per_min)
        if not ok:
            raise HTTPException(429, "Too many requests - slow down", headers={"Retry-After": "60"})

    return _dep


_failures: dict[str, deque[float]] = defaultdict(deque)
LOCKOUT_FAILS, LOCKOUT_SECONDS = 5, 15 * 60


def login_locked(identity: str) -> bool:
    now = time.monotonic()
    q = _failures[identity]
    while q and now - q[0] > LOCKOUT_SECONDS:
        q.popleft()
    return len(q) >= LOCKOUT_FAILS


def login_failed(identity: str) -> None:
    _failures[identity].append(time.monotonic())


def login_ok(identity: str) -> None:
    _failures.pop(identity, None)
