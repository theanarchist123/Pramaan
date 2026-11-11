"""Governed settings (spec ADM-12): the safety switches live in the database, change only through a four-eyes approval,
and keep a versioned history. The environment value is the bootstrap default; a database row overrides it.

A change can never weaken a hard floor (for example the auto-approve score cannot go below 0.90), whatever anyone approves.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select

from app.config import get_settings
from app.domain import AUTO_APPROVE_THRESHOLD


@dataclass(frozen=True)
class Spec:
    kind: type
    default: Callable[[], Any]
    description: str
    minimum: float | None = None  # hard floor for numbers
    maximum: float | None = None


GOVERNED: dict[str, Spec] = {
    "human_approval_first_listing": Spec(bool, lambda: get_settings().human_approval_first_listing,
                                         "Every owner's first public listing is approved by a person"),
    "award_claims_need_human": Spec(bool, lambda: get_settings().award_claims_need_human,
                                    "Award claims are confirmed by a human reviewer"),
    "claim_override_four_eyes": Spec(bool, lambda: get_settings().claim_override_four_eyes,
                                     "A second person approves raising a claim to 'confirmed by a reviewer'"),
    "require_email_verification": Spec(bool, lambda: get_settings().require_email_verification,
                                       "Applicants confirm their email with a one-time code before verification"),
    "auto_approve_threshold": Spec(float, lambda: AUTO_APPROVE_THRESHOLD,
                                   "Confidence at or above which Prahari may approve without a person (never below 0.90)",
                                   minimum=0.90, maximum=1.0),
}

_cache: dict[str, tuple[float, Any]] = {}
TTL = 5.0  # seconds: a changed setting takes effect everywhere within this long


def validate(key: str, value: Any) -> Any:
    spec = GOVERNED.get(key)
    if spec is None:
        raise ValueError(f"'{key}' is not a governed setting")
    if spec.kind is bool:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    v = float(value)
    if (spec.minimum is not None and v < spec.minimum) or (spec.maximum is not None and v > spec.maximum):
        raise ValueError(f"{key} must be between {spec.minimum} and {spec.maximum}")
    return v


_MISSING = object()


async def get(key: str) -> Any:
    """Current value: the database override if there is one, else the environment default. Only the DATABASE lookup is cached
    (5 s); the default is always read fresh, so an environment change is never hidden behind the cache."""
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL:
        row_value = hit[1]
    else:
        from app.db import get_sessionmaker
        from app.models import GovernedSetting

        row_value = _MISSING
        try:
            async with get_sessionmaker()() as s:
                row = (await s.execute(select(GovernedSetting).where(GovernedSetting.key == key))).scalar_one_or_none()
                if row is not None:
                    row_value = row.value["v"]
        except Exception:  # noqa: BLE001 - a settings read must never take verification down: fall back to the default
            pass
        _cache[key] = (time.monotonic(), row_value)
    return GOVERNED[key].default() if row_value is _MISSING else row_value


def clear_cache() -> None:
    _cache.clear()


async def snapshot(session) -> list[dict[str, Any]]:
    from app.models import GovernedSetting

    rows = {r.key: r for r in (await session.execute(select(GovernedSetting))).scalars().all()}
    out = []
    for key, spec in GOVERNED.items():
        r = rows.get(key)
        out.append({"key": key, "description": spec.description, "value": r.value["v"] if r else spec.default(),
                    "source": "database" if r else "environment", "version": r.version if r else 0,
                    "minimum": spec.minimum, "maximum": spec.maximum})
    return out
