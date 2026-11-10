"""Short-lived locks ("only one of these at a time"), shared across replicas through Redis when available.

Used to close check-then-act races, for example two simultaneous "verify" requests both seeing no run in progress.
They are advisory and expire on their own: the durable guard is still the database state the caller checks inside the
lock. Without Redis (or when it is down) the lock works within this process only.
"""

from __future__ import annotations

import asyncio
import contextlib
import secrets
from collections.abc import AsyncIterator

from app.core import redis as rd

_local: dict[str, asyncio.Lock] = {}


class LockBusy(Exception):
    pass


@contextlib.asynccontextmanager
async def short_lock(name: str, ttl_seconds: float = 30.0, wait_seconds: float = 5.0) -> AsyncIterator[None]:
    token = secrets.token_hex(8)
    key = f"lock:{name}"
    held_in_redis = False

    async def acquire(r) -> bool:
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while True:
            if await r.set(key, token, nx=True, px=int(ttl_seconds * 1000)):
                return True
            if asyncio.get_running_loop().time() >= deadline:
                return False
            await asyncio.sleep(0.05)

    async def local_acquire() -> None:
        return None

    got = await rd.call(acquire, local_acquire)
    if got is False:
        raise LockBusy(name)
    held_in_redis = got is True
    lock = None
    if not held_in_redis:  # Redis not configured / down: serialise within this process
        lock = _local.setdefault(name, asyncio.Lock())
        try:
            await asyncio.wait_for(lock.acquire(), wait_seconds)
        except asyncio.TimeoutError as exc:
            raise LockBusy(name) from exc
    try:
        yield
    finally:
        if lock is not None:
            lock.release()
        elif held_in_redis:
            # Release only our own lock (it may have expired and been taken by someone else).
            async def release(r):
                if await r.get(key) == token:
                    await r.delete(key)

            async def noop():
                return None

            await rd.call(release, noop)
