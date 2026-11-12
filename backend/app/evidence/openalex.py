"""OpenAlex adapter: a person's publications and co-authors (open data; keyless basic use is allowed, an optional free key raises the limit).

Terms checked 2026-11-12 at help.openalex.org/api/authentication. No identity guessing: an author is used only when their last known institution
matches one the applicant gave.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.agents.textutil import name_similarity, normalize
from app.config import get_settings
from app.evidence.base import EvidenceDoc

log = logging.getLogger("pramaan.evidence.openalex")
API = "https://api.openalex.org"
_STOP = {"of", "the", "and", "for", "in", "at", "university", "institute", "college", "india", "indian"}


def _sig(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{3,}", normalize(text)) if t not in _STOP}


def institution_matches(wanted: list[str], theirs: list[str]) -> bool:
    for w in wanted:
        a = _sig(w)
        for t in theirs:
            b = _sig(t)
            if a and b and len(a & b) / min(len(a), len(b)) >= 0.5:
                return True
    return False


class OpenAlexAdapter:
    name, reliability = "openalex", 0.8

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        s = get_settings()
        headers = {"User-Agent": f"Pramaan/1.0 (mailto:{s.wikimedia_contact})" if "@" in s.wikimedia_contact else "Pramaan/1.0"}
        if s.openalex_api_key:
            headers["Authorization"] = f"Bearer {s.openalex_api_key}"
        return httpx.AsyncClient(base_url=API, timeout=8.0, headers=headers, transport=self._transport)

    async def search(self, person: Any) -> list[EvidenceDoc]:
        institutions = list(getattr(person, "institutions", None) or [])
        if not institutions:
            return []  # nothing to tell this person from a namesake: do not guess
        try:
            async with self._client() as c:
                r = await c.get("/authors", params={"search": person.name, "per_page": 5})
                r.raise_for_status()
                match = None
                for a in r.json().get("results", []):
                    insts = [i.get("display_name", "") for i in a.get("last_known_institutions") or []]
                    if name_similarity(a.get("display_name", ""), person.name) >= 0.9 and institution_matches(institutions, insts):
                        match = a
                        break
                if match is None:
                    return []
                aid = match["id"].rsplit("/", 1)[-1]
                w = await c.get("/works", params={"filter": f"author.id:{aid}", "sort": "publication_year:desc", "per_page": 8})
                w.raise_for_status()
                works = w.json().get("results", [])
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.warning("openalex lookup failed: %s", type(exc).__name__)
            return []
        docs = []
        for work in works:
            title = (work.get("display_name") or "").strip()
            if not title:
                continue
            authors = [a["author"]["display_name"] for a in work.get("authorships", []) if a.get("author", {}).get("display_name")]
            text = f"{title} ({work.get('publication_year') or 'n.d.'}). Authors: {', '.join(authors[:12])}."
            docs.append(EvidenceDoc(title=match["display_name"], url=work.get("doi") or match["id"], text=text, source=self.name,
                                    reliability=self.reliability, identifiers={"openalex": aid}))
        return docs
