"""Who qualifies for a public listing, as plain rules.

A Who's Who needs a stated bar. The bar here is checkable and deterministic: it counts only claims backed by evidence
(document, issuer, reviewer or a public source), never self-declared ones, and a model has no say (invariant I-1).
Meeting the bar does not approve anyone: Prahari and the human reviewers still decide. This only tells a person, in the
onboarding screen, what is still missing.
"""
from __future__ import annotations

from typing import Iterable

from app.domain import STATUS_DOCUMENT, STATUS_HUMAN, STATUS_ISSUER, STATUS_WEB

BACKED = {STATUS_DOCUMENT, STATUS_ISSUER, STATUS_HUMAN, STATUS_WEB}
MIN_MET = 2  # of the three criteria below

CRITERIA = [
    ("recognition", "Recognised by others", "A backed award, honour or membership.", {"award", "membership"}),
    ("standing", "Standing in your field", "A backed position, publication or major achievement.", {"position", "publication", "achievement"}),
    ("depth", "More than one backed claim", "At least two claims that are backed by evidence, not just stated.", None),
]


def assess(claims: Iterable) -> dict:
    """claims: anything with .field and .status (database rows or simple objects)."""
    backed = [c for c in claims if c.status in BACKED]
    out = []
    for cid, label, how, fields in CRITERIA:
        met = len(backed) >= 2 if fields is None else any(c.field in fields for c in backed)
        out.append({"id": cid, "label": label, "how": how, "met": met})
    met_count = sum(1 for c in out if c["met"])
    return {"criteria": out, "met_count": met_count, "needed": MIN_MET, "eligible": met_count >= MIN_MET}
