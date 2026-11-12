"""Prahari's scoring policy as versioned data (AGT-07). Changing a number here changes behaviour, so it is a reviewed change AND bumps VERSION;
every decision records the version it was made under. `shadow()` re-decides a past case under a candidate policy without acting on it, so a
change can be measured on real cases before it is adopted. The model is never part of this: rules decide (I-1).
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "2026-11-12.1"

# Document flag -> highest score a profile can have while that flag is present.
FLAG_CAPS: dict[str, float] = {
    "identity_mismatch": 0.4,
    "suspicious": 0.5,
    "unreadable": 0.7,
    "partial_match": 0.7,
    "not_a_credential": 0.7,
    "issuer_unrecognised": 0.7,
}
NO_IDENTITY_CAP = 0.9
CONTRADICTED_CAP = 0.4
UNSUPPORTED_BIO_CAP = 0.8


@dataclass(frozen=True)
class Policy:
    version: str = VERSION
    flag_caps: dict | None = None
    threshold: float | None = None  # None = use the governed setting


def decide(score: float, reasons: list[str], threshold: float) -> str:
    """The one place the final call is made: a high enough score AND no reasons for a person to look. Never below 0.90 (see governed settings)."""
    return "auto_approve" if score >= threshold and not reasons else "escalate"


def shadow(score: float, reasons: list[str], live_threshold: float, candidate_threshold: float, actual: str) -> dict:
    """What a candidate threshold would have decided, next to what actually happened. Reports only."""
    would = decide(score, reasons, max(0.90, candidate_threshold))
    return {"actual": actual, "would_be": would, "differs": would != actual, "live_threshold": live_threshold,
            "candidate_threshold": max(0.90, candidate_threshold)}
