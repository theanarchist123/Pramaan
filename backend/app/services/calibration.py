"""Calibration from human decisions (TRU-07): a REPORT, never a control.

The auto-approve threshold is a governed setting (floor 0.90, changed only by two people) and deterministic rules decide approvals (I-1).
This module only answers, from history: how did people actually decide each kind of escalated case, and what WOULD a lower threshold have
done to the cases we already have? Nothing here changes a setting or a decision.
"""
from __future__ import annotations

from dataclasses import dataclass

FLOOR = 0.90
MIN_CASES = 30  # below this the numbers are anecdotes; the report says so instead of implying a pattern
CANDIDATES = (0.90, 0.92, 0.93, 0.94, 0.95)


@dataclass(frozen=True)
class Case:
    confidence: float
    outcome: str  # "approved" | "rejected": what the person decided
    reason_codes: list[str]


def calibrate(cases: list[Case], *, current_threshold: float) -> dict:
    approved = sum(1 for c in cases if c.outcome == "approved")
    by: dict[str, list[int]] = {}
    for c in cases:
        for code in c.reason_codes or ["(none recorded)"]:
            row = by.setdefault(code, [0, 0])
            row[0 if c.outcome == "approved" else 1] += 1
    by_reason = [
        {"reason_code": code, "cases": a + r, "approved": a, "rejected": r, "approval_rate": round(a / (a + r), 3)}
        for code, (a, r) in sorted(by.items(), key=lambda kv: -(kv[1][0] + kv[1][1]))
    ]
    shadow = []
    for t in sorted({x for x in CANDIDATES if FLOOR <= x <= current_threshold}):
        # Escalated cases whose confidence sits at or above the candidate but below today's threshold: a lower threshold would have let
        # them through without a person.
        moved = [c for c in cases if t <= c.confidence < current_threshold]
        rejected = sum(1 for c in moved if c.outcome == "rejected")
        shadow.append({
            "threshold": t, "would_auto_approve": len(moved), "humans_rejected": rejected,
            "humans_rejected_share": round(rejected / len(moved), 3) if moved else 0.0,
        })
    enough = len(cases) >= MIN_CASES
    return {
        "cases": len(cases), "approved": approved, "rejected": len(cases) - approved, "enough_history": enough,
        "by_reason_code": by_reason, "shadow": shadow, "current_threshold": current_threshold, "floor": FLOOR,
        "note": (
            "This is a report. It applies nothing: the threshold is a governed setting that two people change, never below "
            f"{FLOOR:.2f}. " + ("" if enough else f"There are fewer than {MIN_CASES} closed cases, so treat these numbers as anecdotes, not a pattern.")
        ).strip(),
    }
