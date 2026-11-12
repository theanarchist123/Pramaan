"""Pluggable evidence adapters (AGT-05, spec 10.1).

An adapter turns "who is this person" into EvidenceDocs: public text with where it came from, when it was fetched, a hash of exactly that text,
and a reliability prior. Pariksha then applies its fixed guards (verbatim quote, numbers, names, namesake defence, entailment) to those docs; an
adapter never decides anything. A failing, slow or flapping adapter is skipped, so verification degrades to "less evidence", never to an error or an approval.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Protocol

from app.services.wikipedia import Source

log = logging.getLogger("pramaan.evidence")


@dataclass
class EvidenceDoc(Source):
    """A Source plus provenance. Plain data (strings and numbers only) so it survives the workflow checkpoint."""

    source: str = ""            # adapter name
    retrieved_at: str = ""      # ISO 8601 UTC
    content_hash: str = ""      # SHA-256 of `text`
    reliability: float = 0.9    # prior weight in (0, 1]; confidence from this source never exceeds it
    identifiers: dict = field(default_factory=dict)  # e.g. {"qid": "Q123", "openalex": "A1"}

    def stamped(self) -> "EvidenceDoc":
        return replace(self, retrieved_at=self.retrieved_at or datetime.now(timezone.utc).isoformat(),
                       content_hash=hashlib.sha256(self.text.encode()).hexdigest())


class EvidenceAdapter(Protocol):
    name: str
    reliability: float

    async def search(self, person: Any) -> list[EvidenceDoc]: ...


class CircuitBreaker:
    """After `threshold` failures in a row an adapter is skipped for `cooldown` seconds, so one broken source cannot slow every verification."""

    def __init__(self, threshold: int = 3, cooldown: float = 60.0):
        self.threshold, self.cooldown = threshold, cooldown
        self._fails: dict[str, int] = {}
        self._opened: dict[str, float] = {}

    def allow(self, name: str) -> bool:
        opened = self._opened.get(name)
        if opened is None:
            return True
        if time.monotonic() - opened >= self.cooldown:
            self._opened.pop(name, None)
            self._fails[name] = 0
            return True
        return False

    def ok(self, name: str) -> None:
        self._fails[name] = 0

    def fail(self, name: str) -> None:
        self._fails[name] = self._fails.get(name, 0) + 1
        if self._fails[name] >= self.threshold:
            self._opened[name] = time.monotonic()


_BREAKER = CircuitBreaker()


async def gather(person: Any, adapters: list[EvidenceAdapter], *, breaker: CircuitBreaker | None = None, timeout: float = 10.0,
                 max_docs: int = 12) -> list[EvidenceDoc]:
    br = breaker or _BREAKER

    async def one(a: EvidenceAdapter) -> list[EvidenceDoc]:
        if not br.allow(a.name):
            return []
        try:
            docs = await asyncio.wait_for(a.search(person), timeout)
        except Exception as exc:  # noqa: BLE001 - any failure of one source means "no evidence from it"
            br.fail(a.name)
            log.warning("evidence adapter %s failed: %s", a.name, type(exc).__name__)
            return []
        br.ok(a.name)
        return [d.stamped() for d in docs]

    results = await asyncio.gather(*(one(a) for a in adapters))
    seen: set[str] = set()
    out: list[EvidenceDoc] = []
    for docs in results:
        for d in docs:
            key = d.url or d.content_hash
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
    return out[:max_docs]


class WikipediaAdapter:
    name, reliability = "wikipedia", 0.9

    async def search(self, person: Any) -> list[EvidenceDoc]:
        from app.services import wikipedia

        return [EvidenceDoc(title=s.title, url=s.url, text=s.text, source=self.name, reliability=self.reliability)
                for s in await wikipedia.fetch_sources(person.name, limit=3)]


class WikidataAdapter:
    """Only the item the applicant confirmed is them (never the first same-named person)."""

    name, reliability = "wikidata", 0.9

    async def search(self, person: Any) -> list[EvidenceDoc]:
        from app.services import wikidata

        if not getattr(person, "qid", None):
            return []
        return [EvidenceDoc(title=s.title, url=s.url, text=s.text, source=self.name, reliability=self.reliability,
                            identifiers={"qid": person.qid}) for s in await wikidata.fetch_by_qid(person.qid)]


def default_adapters() -> list[EvidenceAdapter]:
    from app.config import get_settings
    from app.evidence.openalex import OpenAlexAdapter

    adapters: list[EvidenceAdapter] = [WikipediaAdapter(), WikidataAdapter()]
    if get_settings().openalex_enabled:
        adapters.append(OpenAlexAdapter())
    return adapters
