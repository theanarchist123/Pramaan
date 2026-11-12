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


_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def numbers_in(text: str) -> set[str]:
    """Every number in the text (years included), with Devanagari digits normalised and thousands commas ignored."""
    return set(re.findall(r"\d+", text.translate(_DEVANAGARI_DIGITS).replace(",", "")))


def claim_specifics_in_quote(claim_text: str, claim_year: int | None, quote: str) -> bool:
    """A quote can be real and still not support THIS claim: "award 2021" is not supported by a sentence about 2024.
    Every number and year the claim states must appear in the cited quote. Deterministic; it never trusts the model
    to have been careful (finding P-17)."""
    wanted = numbers_in(claim_text) | ({str(claim_year)} if claim_year else set())
    return wanted <= numbers_in(quote)


_GENERIC = {"the", "and", "for", "from", "with", "award", "prize", "awarded", "winner", "received", "won", "university", "institute", "national",
            "india", "indian", "dr", "prof", "shri", "smt", "sir", "state", "government", "of", "in", "at", "by", "medal", "member", "fellow"}


def distinctive_names(claim_text: str, own_name: str = "") -> set[str]:
    """Capitalised words in a claim that name something specific (an organisation, a place, a title), minus the person's own name and generic words."""
    own = {t for t in normalize(own_name).split()}
    out = set()
    for w in re.findall(r"\b[A-Z][A-Za-zऀ-ॿ]{2,}\b", claim_text):
        n = normalize(w)
        if n and n not in _GENERIC and n not in own:
            out.add(n)
    return out


def claim_names_in_quote(claim_text: str, quote: str, own_name: str = "", minimum: float = 0.6) -> bool:
    """A real quote can still be about something else ("won the Padma Shri" is not backed by a sentence about the Sahitya Akademi).
    At least `minimum` of the claim's distinctive names must appear in the quote. A miss only sends the claim to a person; it never approves anything."""
    wanted = distinctive_names(claim_text, own_name)
    if not wanted:
        return True
    have = set(normalize(quote).split())
    return len(wanted & have) / len(wanted) >= minimum
