"""The Python SDK, exercised against the real application (no mocks of our own API)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "sdk" / "python"))
from pramaan import AsyncPramaan, Pramaan, PramaanError, RateLimited, verify_webhook  # noqa: E402
from tests.test_api_flow import _approved_profile_with_cert  # noqa: E402


@pytest.fixture
def sdk(app_instance):
    transport = httpx.ASGITransport(app=app_instance)
    def make(**kw):
        return AsyncPramaan(base_url="http://test", http_client=httpx.AsyncClient(transport=transport), **kw)
    return make


async def test_public_endpoints_through_the_sdk(sdk, client, make_user):
    _, _, profile, cert = await _approved_profile_with_cert(client, make_user)
    p = sdk()

    v = await p.verify(cert["code"].lower())  # case-insensitive
    assert v["valid"] is True and v["signature_ok"] is True

    forged = {**v["payload"], "full_name": "Someone Else"}
    c = await p.check_payload(cert["code"], forged)
    assert c["valid"] is False and "full_name" in c["changed_fields"]

    assert (await p.certificate(cert["code"]))["profile"]["slug"] == profile["slug"]
    assert (await p.profile(profile["slug"]))["full_name"] == "Meera Iyer"
    assert (await p.list_profiles(q="Meera"))
    assert "nodes" in await p.graph() and "by_state" in await p.map_stats()
    assert (await p.transparency_ok())["ok"] is True
    assert (await p.public_keys())["keys"][0]["crv"] == "Ed25519"
    found = await p.search("marine scientist Kerala")
    assert found["embedder"] in ("hash", "fastembed") and "results" in found
    assert p.badge_url("prm-abc") == "http://test/v1/badge/certificate/PRM-ABC.svg"


async def test_errors_are_typed(sdk, client):
    p = sdk()
    with pytest.raises(PramaanError) as e:
        await p.profile("no-such-profile")
    assert e.value.status == 404 and "not found" in e.value.detail.lower()
    with pytest.raises(PramaanError) as e:
        await p.my_profiles()  # needs a key
    assert e.value.status == 401


async def test_api_key_flow_and_rate_limit(sdk, client, make_user):
    from app.core import ratelimit

    ratelimit.reset()
    h, _ = await make_user()
    key = (await client.post("/v1/api-keys", headers=h, json={
        "name": "sdk", "scopes": ["profiles:read", "webhooks:manage"], "rate_limit_per_min": 3})).json()["key"]
    p = sdk(api_key=key)
    assert await p.my_profiles() == []
    with pytest.raises(RateLimited) as e:
        for _ in range(6):
            await p.my_profiles()
    assert e.value.retry_after >= 1 and e.value.status == 429


def test_sync_client_and_error_mapping():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/verify/PRM-OK":
            assert request.headers["x-api-key"] == "pk_live_x"
            return httpx.Response(200, json={"valid": True})
        if request.url.path == "/v1/webhooks/abc":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": "nope"})

    p = Pramaan("pk_live_x", base_url="http://x/", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.verify("prm-ok") == {"valid": True}  # path is upper-cased, base_url trailing slash tolerated
    assert p.delete_webhook("abc") is None
    with pytest.raises(PramaanError) as e:
        p.profile("x")
    assert (e.value.status, e.value.detail) == (404, "nope")


def test_sdk_webhook_verifier_matches_the_server_signer():
    from app.services import webhooks as server

    body = b'{"id":"1","event":"certificate.issued"}'
    ts = int(time.time())
    header = f"t={ts},v1={server.sign('whsec_k', ts, body)}"
    assert verify_webhook("whsec_k", header, body)  # SDK accepts what the server signs
    assert not verify_webhook("whsec_k", header, body + b" ")
    assert not verify_webhook("whsec_k", f"t={ts - 999},v1={server.sign('whsec_k', ts - 999, body)}", body)
