"""Introduction requests: one registered, email-verified person asks another to be introduced.

The message is written by a person, but it is still outward-facing text delivered by us, so it is cleaned by code: any link, e-mail address or
phone number is removed, whitespace collapsed, length capped (the same spirit as invariant I-7). Nobody's contact details are exposed by
asking; they are shared only if the recipient accepts and replies. You cannot ask to be introduced to yourself.
"""
from __future__ import annotations

import re

MAX_LEN = 1000
_URL = re.compile(r"(https?://|www\.)\S+", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


class IntroRejected(ValueError):
    """The message has nothing left once links and contact details are removed."""


def clean_message(text: str, limit: int = MAX_LEN) -> str:
    out = _URL.sub("", text or "")
    out = _EMAIL.sub("", out)
    out = _PHONE.sub("", out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()[:limit].strip()
    if len(out) < 3:
        raise IntroRejected("Write a short note about why you would like to be introduced (links and contact details are removed).")
    return out
