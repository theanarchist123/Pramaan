"""Small text helpers shared by agents (anti-hallucination checks live here)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def quote_in_source(quote: str, source_text: str) -> bool:
    """A quote is only evidence if it appears verbatim (modulo case/punctuation/whitespace)
    in the source we actually fetched. This blocks invented citations."""
    q = normalize(quote)
    return len(q) >= 12 and q in normalize(source_text)


def name_similarity(a: str, b: str) -> float:
    strip = lambda s: re.sub(r"\(.*?\)", "", s)  # noqa: E731 - drop "(scientist)" suffixes
    return SequenceMatcher(None, normalize(strip(a)), normalize(strip(b))).ratio()


def token_overlap(a: str, b: str) -> float:
    """Share of a's meaningful tokens that appear in b."""
    stop = {"the", "of", "in", "for", "and", "a", "an", "to", "at", "by", "from", "with"}
    ta = {t for t in re.findall(r"\w+", a.lower()) if t not in stop and len(t) > 1}
    tb = set(re.findall(r"\w+", b.lower()))
    return len(ta & tb) / len(ta) if ta else 0.0
