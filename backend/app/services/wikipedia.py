"""Public-source evidence from Wikipedia (no API key). Network failures degrade to 'no evidence'."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

log = logging.getLogger("pramaan.wikipedia")
_API = "https://en.wikipedia.org/w/api.php"

def _headers() -> dict[str, str]:
    contact = get_settings().wikimedia_contact.strip()
    suffix = f"; {contact}" if contact else ""
    return {"User-Agent": f"Pramaan/1.0 (student registry project{suffix})"}


@dataclass
class Source:
    title: str
    url: str
    text: str


async def search_pages(name: str, limit: int = 3) -> list[Source]:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": name,
        "gsrlimit": limit, "prop": "extracts|info", "exintro": 1, "explaintext": 1,
        "exchars": 3000, "inprop": "url", "redirects": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=_headers()) as client:
            resp = await client.get(_API, params=params)
            if resp.status_code == 403:
                log.warning(
                    "Wikipedia refused the request (403). Set WIKIMEDIA_CONTACT in .env to an email or "
                    "URL so the User-Agent complies with Wikimedia's bot policy. Continuing with no evidence."
                )
                return []
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("wikipedia lookup failed: %s", exc)
        return []
    ordered = sorted(pages.values(), key=lambda p: p.get("index", 99))
    return [
        Source(title=p["title"], url=p.get("fullurl", ""), text=p.get("extract", ""))
        for p in ordered
        if p.get("extract")
    ]


# Indirection so tests can swap the network out.
fetch_sources = search_pages
