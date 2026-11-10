"""Public-source evidence from Wikidata (no API key): structured facts about a person.

Wikidata records awards received (including the Padma awards), occupations, education and birth year for many people
who have no Wikipedia article. It is CROWD-EDITED, not an official registry: Pariksha treats it exactly like
Wikipedia (a citation only counts if the quote is really in this text, and web evidence stays capped below the
document level). Network failures degrade to "no evidence".

NAMESAKES: searching by name can return several people with the same label. So the pipeline never picks one itself:
the applicant is shown the candidates (`candidates`) and confirms their own item; only that QID is then used as
evidence (`fetch_by_qid`). `fetch_sources` (search by name) exists for evals and tooling, not for verification.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.config import get_settings
from app.services.wikipedia import Source, _headers

log = logging.getLogger("pramaan.wikidata")
_API = "https://www.wikidata.org/w/api.php"
QID_RE = re.compile(r"^Q[1-9]\d{0,12}$")

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


async def _entities(qids: list[str]) -> dict:
    """Humans only (P31 = Q5)."""
    ents = (await _get({"action": "wbgetentities", "ids": "|".join(qids), "props": "labels|descriptions|claims", "languages": "en"})).get("entities", {})
    return {q: e for q, e in ents.items() if "Q5" in _ids(e.get("claims", {}), "P31")}


async def candidates(name: str, limit: int = 5) -> list[dict]:
    """People on Wikidata whose label matches `name`, for the applicant to pick from ("Is this you?")."""
    if not get_settings().wikidata_enabled:
        return []
    try:
        found = await _get({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": limit * 2})
        qids = [r["id"] for r in found.get("search", [])]
        if not qids:
            return []
        people = await _entities(qids)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("wikidata candidate lookup failed: %s", exc)
        return []
    out = []
    for qid in qids:  # keep the search ranking
        e = people.get(qid)
        label = e.get("labels", {}).get("en", {}).get("value", "") if e else ""
        if not label:
            continue
        out.append({"qid": qid, "label": label, "description": e.get("descriptions", {}).get("en", {}).get("value", ""),
                    "born": _year(e["claims"]), "url": f"https://www.wikidata.org/wiki/{qid}"})
        if len(out) >= limit:
            break
    return out


async def _sources_for(qids: list[str]) -> list[Source]:
    try:
        people = await _entities(qids)
        wanted = sorted({i for e in people.values() for p in PROPS if p != "P569" for i in _ids(e["claims"], p)})
        labels: dict[str, str] = {}
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
    return sources


async def fetch_by_qid(qid: str) -> list[Source]:
    """Evidence from exactly the item the applicant confirmed. An invalid or missing QID yields nothing."""
    if not get_settings().wikidata_enabled or not QID_RE.match(qid or ""):
        return []
    return await _sources_for([qid])


async def fetch_sources(name: str, limit: int = 3) -> list[Source]:
    """Search by name (evals/tooling). NOT used for verification: see the module docstring."""
    if not get_settings().wikidata_enabled:
        return []
    try:
        found = await _get({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": limit * 2})
        qids = [r["id"] for r in found.get("search", [])]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("wikidata lookup failed: %s", exc)
        return []
    return (await _sources_for(qids))[:limit] if qids else []
