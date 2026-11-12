"""Pramaan Python SDK — a small, typed-by-docstring client for the public API.

    from pramaan import Pramaan
    p = Pramaan()                                   # public endpoints need no key
    p.verify("PRM-ABCDEFGHJK")                      # {'valid': True, ...}
    p.search("clean-energy innovators in Karnataka")

    p = Pramaan(api_key="pk_live_...")              # writes, webhooks, higher limits
    from pramaan import AsyncPramaan                # same methods, awaitable

The sync and async clients share ONE set of method definitions (`_Methods`): every method builds a
request description and hands it to `self._call`, which either sends it or returns a coroutine.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"


class PramaanError(Exception):
    """The API answered with an error. `.status` is the HTTP status, `.detail` the server's message."""

    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status, self.detail = status, detail


class RateLimited(PramaanError):
    """HTTP 429. `.retry_after` is how many seconds to wait."""

    def __init__(self, detail: str, retry_after: int):
        super().__init__(429, detail)
        self.retry_after = retry_after


@dataclass
class _Req:
    method: str
    path: str
    params: dict[str, Any] | None = None
    json: Any = None
    raw: bool = False  # return the Response body as text/bytes (badges, PDFs) instead of JSON
    headers: dict[str, str] = field(default_factory=dict)


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _raise(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:  # noqa: BLE001
        detail = resp.text
    if resp.status_code == 429:
        raise RateLimited(str(detail), int(resp.headers.get("retry-after", "60")))
    raise PramaanError(resp.status_code, detail if isinstance(detail, str) else str(detail))


def verify_webhook(secret: str, signature_header: str, body: bytes, tolerance: int = 300) -> bool:
    """Check an incoming webhook. Pass the RAW request body bytes (not re-serialised JSON) and the
    `X-Pramaan-Signature` header. Rejects tampered bodies, wrong secrets and replays older than
    `tolerance` seconds."""
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        ts = int(parts["t"])
        expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
        return abs(time.time() - ts) <= tolerance and hmac.compare_digest(expected, parts["v1"])
    except (KeyError, ValueError):
        return False


class _Methods:
    """Every API operation, defined once. `self._call` is provided by the sync/async subclasses."""

    base_url: str

    def _call(self, req: _Req) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    # ---- public (no key needed) -------------------------------------------------------
    def verify(self, code: str):
        """Is this certificate genuine? Returns validity, signature/log evidence and the signed content."""
        return self._call(_Req("GET", f"/v1/verify/{code.strip().upper()}"))

    def check_payload(self, code: str, payload: dict[str, Any]):
        """Would this (possibly edited) content still match the certificate's signature?
        When it doesn't, `changed_fields` names exactly what was altered."""
        return self._call(_Req("POST", "/v1/verify/check", json={"code": code, "payload": payload}))

    def certificate(self, code: str):
        return self._call(_Req("GET", f"/v1/certificates/{code.strip().upper()}"))

    def verify_batch(self, codes: list[str]):
        """Check up to 50 certificates in one call; each answer is what `verify` would say."""
        return self._call(_Req("POST", "/v1/verify/batch", json={"codes": [c.strip().upper() for c in codes]}))

    def credential(self, code: str):
        """The certificate as a W3C Verifiable Credential 2.0 (eddsa-jcs-2022 proof)."""
        return self._call(_Req("GET", f"/v1/certificates/{code.strip().upper()}/vc"))

    def revocation_list(self, list_id: int = 1):
        """The signed Bitstring Status List: a set bit means that certificate is revoked."""
        return self._call(_Req("GET", f"/v1/status/revocation/{list_id}"))

    def log_checkpoint(self):
        """A signed Merkle root and size of the public log."""
        return self._call(_Req("GET", "/v1/transparency/checkpoint"))

    def log_proof(self, code: str):
        """Inclusion proof for one certificate in the public log (RFC 9162)."""
        return self._call(_Req("GET", f"/v1/transparency/proof/{code.strip().upper()}"))

    def search(self, query: str, *, state: str | None = None, sector: str | None = None, limit: int = 12):
        """Plain-English (any language) search of verified, consenting people. Each hit says why it matched."""
        return self._call(_Req("POST", "/v1/search", json=_clean(
            {"query": query, "state": state, "sector": sector, "limit": limit})))

    def profile(self, slug: str):
        return self._call(_Req("GET", f"/v1/profiles/{slug}"))

    def list_profiles(self, *, q: str | None = None, sector: str | None = None, state: str | None = None,
                      limit: int = 24, offset: int = 0):
        return self._call(_Req("GET", "/v1/profiles", params=_clean(
            {"q": q, "sector": sector, "state": state, "limit": limit, "offset": offset})))

    def graph(self):
        """Nodes (people) and links (shared institution / city / field) of the whole registry."""
        return self._call(_Req("GET", "/v1/graph"))

    def map_stats(self):
        return self._call(_Req("GET", "/v1/stats/map"))

    def transparency_log(self, limit: int = 50):
        return self._call(_Req("GET", "/v1/transparency", params={"limit": limit}))

    def transparency_ok(self):
        """Server-side audit of the whole hash chain."""
        return self._call(_Req("GET", "/v1/transparency/verify"))

    def public_keys(self):
        """The Ed25519 key(s) certificates are signed with, for offline verification."""
        return self._call(_Req("GET", "/.well-known/pramaan-keys.json"))

    def badge_url(self, code: str) -> str:
        """URL of a live 'Verified by Pramaan' SVG badge you can embed with <img>."""
        return f"{self.base_url}/v1/badge/certificate/{code.strip().upper()}.svg"

    def certificate_pdf(self, code: str):
        """Bytes of the certificate PDF."""
        return self._call(_Req("GET", f"/v1/certificates/{code.strip().upper()}/pdf", raw=True))

    # ---- authenticated ----------------------------------------------------------------
    def my_profiles(self):
        return self._call(_Req("GET", "/v1/profiles/mine"))

    def create_webhook(self, url: str, events: list[str]):
        """Subscribe to events. The response contains the signing `secret` — shown only once."""
        return self._call(_Req("POST", "/v1/webhooks", json={"url": url, "events": events}))

    def list_webhooks(self):
        return self._call(_Req("GET", "/v1/webhooks"))

    def delete_webhook(self, webhook_id: str):
        return self._call(_Req("DELETE", f"/v1/webhooks/{webhook_id}"))

    def test_webhook(self, webhook_id: str):
        return self._call(_Req("POST", f"/v1/webhooks/{webhook_id}/test"))

    def replay_webhook_delivery(self, webhook_id: str, delivery_id: str):
        """Send a past delivery to your endpoint again (same event, data and delivery id; header X-Pramaan-Replay: 1). Payloads are kept 30 days."""
        return self._call(_Req("POST", f"/v1/webhooks/{webhook_id}/deliveries/{delivery_id}/replay"))

    def webhook_deliveries(self, webhook_id: str):
        return self._call(_Req("GET", f"/v1/webhooks/{webhook_id}/deliveries"))

    verify_webhook = staticmethod(verify_webhook)


class _Base(_Methods):
    def __init__(self, api_key: str | None = None, *, base_url: str = DEFAULT_BASE_URL, token: str | None = None,
                 timeout: float = 30.0, http_client: Any = None):
        self.base_url = base_url.rstrip("/")
        self._headers = {"User-Agent": "pramaan-python/1.0"}
        if api_key:
            self._headers["X-API-Key"] = api_key
        elif token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._timeout = timeout
        self._client = http_client

    def _args(self, req: _Req) -> dict[str, Any]:
        return dict(method=req.method, url=self.base_url + req.path, params=req.params, json=req.json,
                    headers={**self._headers, **req.headers})

    @staticmethod
    def _parse(req: _Req, resp: httpx.Response):
        _raise(resp)
        if req.raw:
            return resp.content
        return None if resp.status_code == 204 else resp.json()


class Pramaan(_Base):
    """Synchronous client."""

    def __init__(self, *a: Any, **kw: Any):
        super().__init__(*a, **kw)
        self._client = self._client or httpx.Client(timeout=self._timeout)

    def _call(self, req: _Req):
        return self._parse(req, self._client.request(**self._args(req)))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Pramaan":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class AsyncPramaan(_Base):
    """Asynchronous client — every method returns an awaitable."""

    def __init__(self, *a: Any, **kw: Any):
        super().__init__(*a, **kw)
        self._client = self._client or httpx.AsyncClient(timeout=self._timeout)

    async def _call(self, req: _Req):  # type: ignore[override]
        return self._parse(req, await self._client.request(**self._args(req)))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "AsyncPramaan":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()
