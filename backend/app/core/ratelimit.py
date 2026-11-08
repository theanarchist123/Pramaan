"""Tiny in-process sliding-window limiter (per API key). Swap for Redis if scaled out."""

from __future__ import annotations

import time
from collections import defaultdict, deque

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
