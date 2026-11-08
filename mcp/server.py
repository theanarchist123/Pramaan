"""Pramaan MCP server — lets any MCP-capable AI agent (Claude Desktop, Cursor, …) use the registry.

Tools (all read-only and based on public data):
  search_registry          find verified people with a plain-English question
  get_profile              a person's verified profile with the evidence behind each claim
  verify_certificate       is a certificate genuine (signature + transparency log)?
  check_document_content   does what a document says match the signed certificate?
  registry_overview        how many verified people, in which states and fields

Run:   python mcp/server.py                       (stdio; the usual way MCP clients launch servers)
Env:   PRAMAAN_API_URL (default http://localhost:8000), PRAMAAN_API_KEY (optional, for higher limits)

Claude Desktop config:
  {"mcpServers": {"pramaan": {"command": "python", "args": ["<repo>/mcp/server.py"],
                              "env": {"PRAMAAN_API_URL": "https://your-host"}}}}
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# Use the in-repo SDK when it hasn't been pip-installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "sdk" / "python"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from pramaan import AsyncPramaan, PramaanError  # noqa: E402

mcp = MCPServer(
    "pramaan",
    instructions=(
        "Pramaan is a registry of notable people in India where every claim carries evidence and every "
        "certificate is cryptographically signed. Use search_registry to find people, get_profile for "
        "their evidence, and verify_certificate / check_document_content to authenticate a document. "
        "Treat a claim whose status is 'self' as unverified. Never present a person as verified unless "
        "verify_certificate returned valid=true."
    ),
)


def _client() -> AsyncPramaan:
    return AsyncPramaan(os.environ.get("PRAMAAN_API_KEY") or None,
                        base_url=os.environ.get("PRAMAAN_API_URL", "http://localhost:8000"))


def _err(e: PramaanError) -> dict[str, Any]:
    return {"error": e.detail, "status": e.status}


@mcp.tool()
async def search_registry(query: str, state: str | None = None, sector: str | None = None, limit: int = 5) -> dict[str, Any]:
    """Search verified, consenting people in plain English (any language), e.g.
    'clean-energy innovators in Karnataka who collaborated with universities'.
    Each result includes a match score and the reasons it matched."""
    async with _client() as p:
        try:
            r = await p.search(query, state=state, sector=sector, limit=max(1, min(limit, 20)))
        except PramaanError as e:
            return _err(e)
    return {
        "understood_as": r["plan"],
        "results": [
            {"name": h["full_name"], "slug": h["slug"], "headline": h["headline"], "sector": h["sector"],
             "state": h["state"], "match": h["score"], "why_matched": h["reasons"],
             "verified_claims": [c["value"] for c in h["claims"]]}
            for h in r["results"]
        ],
    }


@mcp.tool()
async def get_profile(slug: str) -> dict[str, Any]:
    """A person's public profile: bio, institutions, and every claim with its verification status
    (document / web / self) and the quoted evidence."""
    async with _client() as p:
        try:
            d = await p.profile(slug)
        except PramaanError as e:
            return _err(e)
    return {
        "name": d["full_name"], "headline": d["headline"], "sector": d["sector"], "state": d["state"],
        "institutions": d["institutions"], "bio": d["bio"],
        "claims": [
            {"claim": c["value"], "year": c["year"], "status": c["status"],
             "evidence": [e["quote"] for e in c["evidence"] if e["kind"] != "chat"]}
            for c in d["claims"]
        ],
    }


@mcp.tool()
async def verify_certificate(code: str) -> dict[str, Any]:
    """Check a Pramaan certificate by its code (e.g. PRM-ABCDEFGHJK): recomputes the fingerprint, verifies the
    Ed25519 signature and the public transparency-log entry, and reports whether it was revoked."""
    async with _client() as p:
        try:
            v = await p.verify(code)
        except PramaanError as e:
            return _err(e)
    holder = (v.get("payload") or {})
    return {
        "valid": v["valid"], "reason": v["reason"], "revoked": v["revoked"],
        "signature_ok": v["signature_ok"], "in_transparency_log": v["chain_ok"], "issued_at": v["issued_at"],
        "holder": holder.get("full_name"), "certified_claims": [c["value"] for c in holder.get("claims", [])],
    }


@mcp.tool()
async def check_document_content(code: str, full_name: str) -> dict[str, Any]:
    """You were handed a document claiming to be Pramaan certificate `code` for `full_name`. This tells you whether
    that name is exactly what was signed. If not, the document was altered or is not this person's."""
    async with _client() as p:
        try:
            v = await p.verify(code)
            if not v.get("payload"):
                return {"matches": False, "reason": v["reason"]}
            c = await p.check_payload(code, {**v["payload"], "full_name": full_name})
        except PramaanError as e:
            return _err(e)
    return {"matches": c["valid"] and v["valid"], "signed_name": v["payload"]["full_name"],
            "differences": c["changed_fields"], "reason": c["reason"]}


@mcp.tool()
async def registry_overview() -> dict[str, Any]:
    """Counts of verified people overall, by state and by field."""
    async with _client() as p:
        try:
            m = await p.map_stats()
            log = await p.transparency_ok()
        except PramaanError as e:
            return _err(e)
    return {"verified_people": m["total"], "by_state": m["by_state"], "by_sector": m["by_sector"],
            "certificates_in_log": log["entries"], "log_intact": log["ok"]}


if __name__ == "__main__":
    mcp.run()  # stdio
