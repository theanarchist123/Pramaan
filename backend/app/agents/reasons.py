"""Reason codes (spec 7.5): the enumerated vocabulary shared by backend and UI.

Prahari's human-readable reasons stay as they are (it is an always-human-review file); this module maps each reason text to a
stable code so the review queue can filter, report and measure by code rather than by sentence.
"""

from __future__ import annotations

REASON_CODES = [
    "IDENTITY_NOT_CONFIRMED", "DOC_NAME_MISMATCH", "DOC_SUSPICIOUS", "DOC_UNREADABLE", "DOC_NOT_CREDENTIAL",
    "ISSUER_UNRECOGNISED", "CLAIM_CONTRADICTED", "CLAIM_NO_EVIDENCE", "BIO_UNSUPPORTED", "COMMON_NAME",
    "FIRST_LISTING", "AWARD_CLAIM", "AUTOMATION_ERROR", "MODEL_REFUSAL", "USER_REQUESTED", "APPEAL",
    # decision-side codes: why a person decided what they did
    "EVIDENCE_CHECKED", "EVIDENCE_INSUFFICIENT", "NOT_THE_SAME_PERSON", "FORGERY_SUSPECTED", "OTHER",
]

# (substring of the reason text, code), checked in order
_RULES = [
    ("only partly matches", "DOC_NAME_MISMATCH"), ("does not match the profile name", "DOC_NAME_MISMATCH"),
    ("looks edited", "DOC_SUSPICIOUS"), ("could not be read", "DOC_UNREADABLE"),
    ("article or clipping", "DOC_NOT_CREDENTIAL"), ("issuer is not a recognised", "ISSUER_UNRECOGNISED"),
    ("contradicted", "CLAIM_CONTRADICTED"), ("no supporting evidence", "CLAIM_NO_EVIDENCE"),
    ("unsupported statement", "BIO_UNSUPPORTED"), ("Common name", "COMMON_NAME"), ("First public listing", "FIRST_LISTING"),
    ("Award claims", "AWARD_CLAIM"), ("Identity not confirmed", "IDENTITY_NOT_CONFIRMED"),
    ("declined", "MODEL_REFUSAL"), ("could not finish", "AUTOMATION_ERROR"), ("verification failed", "AUTOMATION_ERROR"),
    ("Edited after approval", "USER_REQUESTED"), ("Submitted for review", "USER_REQUESTED"),
]


def codes_for(reasons: list[str]) -> list[str]:
    out: list[str] = []
    for text in reasons:
        for needle, code in _RULES:
            if needle.lower() in text.lower() and code not in out:
                out.append(code)
                break
    return out
