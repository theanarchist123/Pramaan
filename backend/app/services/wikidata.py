"""Public-source evidence from Wikidata (no API key): structured facts about a person.

Wikidata records awards received (including the Padma awards), occupations, education and birth year for many people
who have no Wikipedia article. It is CROWD-EDITED, not an official registry: Pariksha treats it exactly like
Wikipedia (a citation only counts if the quote is really in this text, and web evidence stays capped below the
document level). Network failures degrade to "no evidence".
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings
from app.services.wikipedia import Source, _headers

log = logging.getLogger("pramaan.wikidata")
_API = "https://www.wikidata.org/w/api.php"

# property -> label used in the evidence text
PROPS = {
    "P569": "Born", "P106": "Occupation", "P166": "Awards", "P69": "Educated at", "P27": "Citizenship",
    "P19": "Place of birth", "P108": "Employer", "P463": "Member of", "P39": "Position held",
}


async def _get(params: dict) -> dict:
    """The one place that touches the network (tests replace it)."""
    async with httpx.AsyncClient(timeout=8.0, headers=_headers()) as client:
        resp = await client.get(_API, params={"format": "json", **params})
        resp.raise_for_status()
        return resp.json()


def _ids(claims: dict, prop: str) -> list[str]:
    out = []
    for c in claims.get(prop, []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and "id" in v:
            out.append(v["id"])
    return out


def _year(claims: dict) -> str:
    for c in claims.get("P569", []):
        v = (c.get("mainsnak", {}).get("datavalue") or {}).get("value")
        if isinstance(v, dict) and v.get("time", "").startswith("+"):
            return v["time"][1:5]
    return ""


async def fetch_sources(name: str, limit: int = 3) -> list[Source]:
    if not get_settings().wikidata_enabled:
        return []
    try:
        found = await _get({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": limit * 2})
        qids = [r["id"] for r in found.get("search", [])]
        if not qids:
            return []
        ents = (await _get({"action": "wbgetentities", "ids": "|".join(qids), "props": "labels|descriptions|claims", "languages": "en"})).get("entities", {})
        people = {q: e for q, e in ents.items() if "Q5" in _ids(e.get("claims", {}), "P31")}  # humans only
        wanted = sorted({i for e in people.values() for p in PROPS if p != "P569" for i in _ids(e["claims"], p)})
        labels: dict[str, str] = {}
        if wanted:
            for start in range(0, len(wanted), 50):
                chunk = wanted[start:start + 50]
                got = (await _get({"action": "wbgetentities", "ids": "|".join(chunk), "props": "labels", "languages": "en"})).get("entities", {})
                labels.update({q: v.get("labels", {}).get("en", {}).get("value", "") for q, v in got.items()})
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("wikidata lookup failed: %s", exc)
        return []

    sources: list[Source] = []
    for qid, e in people.items():
        label = e.get("labels", {}).get("en", {}).get("value", "")
        if not label:
            continue
        lines = [f"{label}: {e.get('descriptions', {}).get('en', {}).get('value', 'person')}."]
        if year := _year(e["claims"]):
            lines.append(f"Born: {year}.")
        for prop, title in PROPS.items():
            if prop == "P569":
                continue
            names = [labels.get(i, "") for i in _ids(e["claims"], prop)]
            names = [n for n in dict.fromkeys(names) if n]
            if names:
                lines.append(f"{title}: {'; '.join(names[:15])}.")
        sources.append(Source(title=label, url=f"https://www.wikidata.org/wiki/{qid}", text="\n".join(lines)))
        if len(sources) >= limit:
            break
    return sources
