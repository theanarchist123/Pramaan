"""The canary rule (AGT-13, spec 8.5): given error counts for the current release (baseline) and the new one (canary), promote, wait, or roll back.

Pure arithmetic so it can be tested and reused by whatever runs the deploy. It cannot deploy or roll back anything itself: `scripts/canary_watch.py` reads it and
prints the decision (and exits non-zero on rollback) for the pipeline to act on. When it cannot tell, it rolls back (the safe direction, I-2).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Decision:
    action: str  # promote | wait | rollback
    reason: str


def decide(*, baseline_errors: int, baseline_total: int, canary_errors: int, canary_total: int, min_requests: int = 100,
           waited_minutes: float = 0.0, max_wait_minutes: float = 30.0, tolerance: float = 0.01, ratio: float = 2.0) -> Decision:
    if canary_total < min_requests:
        if waited_minutes >= max_wait_minutes:
            return Decision("rollback", f"Only {canary_total} requests after {int(waited_minutes)} minutes: cannot tell whether it is healthy, so rolling back")
        return Decision("wait", f"{canary_total} of {min_requests} requests seen so far")
    base = baseline_errors / baseline_total if baseline_total else 0.0
    now = canary_errors / canary_total
    if now > base * ratio and now - base > tolerance:
        return Decision("rollback", f"Error rate {now:.1%} against a baseline of {base:.1%}")
    return Decision("promote", f"Error rate {now:.1%} against a baseline of {base:.1%}: no regression")
