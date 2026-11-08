"""Webhooks (signed, SSRF-safe, retried) and embeddable badges."""

from __future__ import annotations

import json
import socket
import time
import uuid

import httpx
import pytest
import pytest_asyncio

from app.api.badges import _svg
from app.services import webhooks as svc


@pytest_asyncio.fixture(autouse=True)
async def _no_leftover_hooks(app_instance):
    """Webhooks live in the shared test database; remove them after each test so they can't fire
    during (and slow down) unrelated tests."""
    yield
    from sqlalchemy import delete

    from app.db import get_sessionmaker
    from app.models import Webhook

    # By now the network fakes are gone, so never *wait* for pending deliveries (real DNS, real HTTP,
    # real retry sleeps): cancel them and remove the hooks.
    import asyncio

    pending = list(svc._tasks)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    async with get_sessionmaker()() as s:
        await s.execute(delete(Webhook))
        await s.commit()


@pytest.fixture
def net(monkeypatch):
    """No real network: DNS answers from a table, and the HTTP POST is captured."""
    table = {
        "hooks.example.com": "93.184.216.34", "other.example.com": "93.184.216.35",
        "internal.example.com": "10.0.0.5",
    }
    real_getaddrinfo = socket.getaddrinfo

    def fake_dns(host, port, *a, **kw):
        # Only the test hostnames are faked. The patch is process-wide, so anything else (notably
        # the database pool dialling `localhost`) must keep resolving for real.
        if host in table:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (table[host], port or 443))]
        return real_getaddrinfo(host, port, *a, **kw)

    monkeypatch.setattr(svc.socket, "getaddrinfo", fake_dns)
    calls: list[dict] = []
    behaviour = {"statuses": []}  # pop one status/exception per attempt; empty -> 200

    async def fake_post(url, body, headers):
        calls.append({"url": url, "body": body, "headers": headers})
        nxt = behaviour["statuses"].pop(0) if behaviour["statuses"] else 200
        if isinstance(nxt, Exception):
            raise nxt
        return httpx.Response(nxt)

    monkeypatch.setattr(svc, "_post", fake_post)
    monkeypatch.setattr(svc, "RETRY_DELAYS", (0.0, 0.0))
    return type("Net", (), {"calls": calls, "table": table, "behaviour": behaviour})


def url() -> str:
    return f"https://hooks.example.com/{uuid.uuid4().hex}"


async def _hook(client, headers, events=("certificate.issued", "profile.approved"), u=None):
    r = await client.post("/v1/webhooks", headers=headers, json={"url": u or url(), "events": list(events)})
    assert r.status_code == 201, r.text
    return r.json()


# --------------------------------------------------------------------------- unit: signatures
def test_signature_roundtrip_tamper_and_replay():
    body = b'{"event":"x"}'
    ts = int(time.time())
    header = f"t={ts},v1={svc.sign('whsec_abc', ts, body)}"
    assert svc.verify_signature("whsec_abc", header, body)
    assert not svc.verify_signature("whsec_abc", header, b'{"event":"y"}')  # body changed
    assert not svc.verify_signature("whsec_WRONG", header, body)  # wrong secret
    old = ts - 3600
    assert not svc.verify_signature("whsec_abc", f"t={old},v1={svc.sign('whsec_abc', old, body)}", body)  # replay
    assert not svc.verify_signature("whsec_abc", "garbage", body)


def test_badge_svg_escapes_everything():
    out = _svg('a"><b>', "<script>alert(1)</script>", "ok")
    assert "<script>" not in out and "<b>" not in out
    assert "&lt;script&gt;" in out


# --------------------------------------------------------------------------- creation + SSRF
async def test_ssrf_and_validation(client, make_user, net):
    h, _ = await make_user()
    post = lambda u, ev=("certificate.issued",): client.post(  # noqa: E731
        "/v1/webhooks", headers=h, json={"url": u, "events": list(ev)})
    assert (await post("http://hooks.example.com/x")).status_code == 422  # must be https
    assert (await post("https://internal.example.com/x")).status_code == 422  # resolves to 10.0.0.5
    assert (await post("https://localhost/x")).status_code == 422  # loopback (resolves private in the fake)
    assert (await post("ftp://hooks.example.com/x")).status_code == 422
    assert (await post("https://hooks.example.com/ok", ("nope.event",))).status_code == 422
    assert (await post("https://hooks.example.com/ok", ("review.queued",))).status_code == 403  # admin only
    assert (await post("https://hooks.example.com/ok")).status_code == 201


async def test_secret_shown_once_and_isolated_per_owner(client, make_user, net):
    a, _ = await make_user()
    b, _ = await make_user()
    hook = await _hook(client, a)
    assert hook["secret"].startswith("whsec_")
    listed = (await client.get("/v1/webhooks", headers=a)).json()
    assert listed and all("secret" not in x for x in listed)
    assert (await client.delete(f"/v1/webhooks/{hook['id']}", headers=b)).status_code == 404
    assert (await client.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=b)).status_code == 404
    rotated = (await client.post(f"/v1/webhooks/{hook['id']}/rotate-secret", headers=a)).json()
    assert rotated["secret"] != hook["secret"]


async def test_api_key_needs_webhooks_scope(client, make_user, net):
    h, _ = await make_user()
    key = (await client.post("/v1/api-keys", headers=h, json={"name": "ro", "scopes": ["profiles:read"]})).json()["key"]
    r = await client.get("/v1/webhooks", headers={"X-API-Key": key})
    assert r.status_code == 403


# --------------------------------------------------------------------------- delivery
async def test_events_are_delivered_signed_and_only_to_subscribers(client, make_user, net):
    from tests.test_api_flow import _approved_profile_with_cert  # reuse the full approval flow

    dev, _ = await make_user()
    mine = url()
    hook = await _hook(client, dev, u=mine)
    other = await _hook(client, dev, events=("profile.approved",), u=url())

    await _approved_profile_with_cert(client, make_user)
    await svc.settle()

    mine_calls = [c for c in net.calls if c["url"] == mine]
    events = [json.loads(c["body"])["event"] for c in mine_calls]
    assert "certificate.issued" in events and "profile.approved" in events

    cert_call = next(c for c in mine_calls if json.loads(c["body"])["event"] == "certificate.issued")
    assert svc.verify_signature(hook["secret"], cert_call["headers"]["X-Pramaan-Signature"], cert_call["body"])
    assert not svc.verify_signature(other["secret"], cert_call["headers"]["X-Pramaan-Signature"], cert_call["body"])
    env = json.loads(cert_call["body"])
    assert env["data"]["code"].startswith("PRM-") and env["data"]["profile"]["slug"]
    assert cert_call["headers"]["X-Pramaan-Delivery"] == env["id"]
    # public payload only: no internal ids/emails leak into webhooks
    assert "email" not in cert_call["body"].decode() and "owner" not in cert_call["body"].decode()
    # the second hook only subscribed to profile.approved
    assert all(json.loads(c["body"])["event"] == "profile.approved" for c in net.calls if c["url"] == other["url"])


async def test_admin_only_events_never_reach_non_admins(client, make_user, net):
    dev, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    dev_hook = await _hook(client, dev, events=("profile.approved",), u=url())
    admin_hook = await _hook(client, admin, events=("review.queued",), u=url())
    svc.schedule("review.queued", {"profile_id": "x", "reasons": ["r"]})
    await svc.settle()
    assert [c for c in net.calls if c["url"] == admin_hook["url"]]
    assert not [c for c in net.calls if c["url"] == dev_hook["url"]]


async def test_retries_then_succeeds_and_every_attempt_is_logged(client, make_user, net):
    dev, _ = await make_user()
    hook = await _hook(client, dev, u=url())
    net.behaviour["statuses"] = [500, httpx.ConnectError("boom"), 200]
    ok = await svc.deliver(uuid.UUID(hook["id"]), "certificate.issued", {"x": 1})
    assert ok is True
    log = (await client.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=dev)).json()
    attempts = sorted(log, key=lambda d: d["attempt"])
    assert [a["attempt"] for a in attempts] == [1, 2, 3]
    assert [a["ok"] for a in attempts] == [False, False, True]
    assert attempts[0]["status_code"] == 500 and attempts[1]["error"] == "ConnectError"
    assert len({a["delivery_id"] for a in attempts}) == 1  # same delivery id across retries


async def test_gives_up_after_three_attempts(client, make_user, net):
    dev, _ = await make_user()
    hook = await _hook(client, dev, u=url())
    net.behaviour["statuses"] = [503, 503, 503, 200]
    assert await svc.deliver(uuid.UUID(hook["id"]), "certificate.issued", {}) is False
    log = (await client.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=dev)).json()
    assert len(log) == 3 and not any(d["ok"] for d in log)


async def test_dns_rebinding_to_a_private_address_is_blocked_at_delivery(client, make_user, net):
    dev, _ = await make_user()
    u = "https://other.example.com/hook"
    hook = await _hook(client, dev, u=u)
    net.table["other.example.com"] = "169.254.169.254"  # attacker re-points DNS at cloud metadata
    assert await svc.deliver(uuid.UUID(hook["id"]), "certificate.issued", {}) is False
    assert not [c for c in net.calls if c["url"] == u]  # nothing was ever sent
    log = (await client.get(f"/v1/webhooks/{hook['id']}/deliveries", headers=dev)).json()
    assert len(log) == 1 and "private" in log[0]["error"]  # not retried


async def test_test_endpoint_and_inactive_hooks(client, make_user, net):
    dev, _ = await make_user()
    hook = await _hook(client, dev, u=url())
    r = (await client.post(f"/v1/webhooks/{hook['id']}/test", headers=dev)).json()
    assert r["ok"] is True and r["status_code"] == 200
    assert json.loads(net.calls[-1]["body"])["event"] == "ping"

    await client.patch(f"/v1/webhooks/{hook['id']}", headers=dev, json={"active": False})
    mine = lambda: [c for c in net.calls if c["url"] == hook["url"]]  # noqa: E731 - other tests' hooks share the DB
    before = len(mine())
    svc.schedule("certificate.issued", {})
    await svc.settle()
    assert len(mine()) == before  # a paused hook receives nothing


async def test_events_catalogue_is_public(client):
    names = {e["name"] for e in (await client.get("/v1/webhooks/events")).json()}
    assert {"profile.approved", "certificate.issued", "review.queued"} <= names


# --------------------------------------------------------------------------- badges
async def test_badges(client, make_user):
    from tests.test_api_flow import _approved_profile_with_cert

    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    r = await client.get(f"/v1/badge/certificate/{cert['code']}.svg")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert "verified" in r.text and cert["code"] in r.text
    assert "default-src 'none'" in r.headers["content-security-policy"]

    pr = await client.get(f"/v1/badge/profile/{profile['slug']}.svg")
    assert pr.status_code == 200 and "verified" in pr.text

    missing = await client.get('/v1/badge/certificate/PRM-NOPE.svg')
    assert missing.status_code == 404 and "not found" in missing.text

    await client.delete(f"/v1/profiles/{profile['id']}", headers=person)  # erasure revokes the certificate
    revoked = await client.get(f"/v1/badge/certificate/{cert['code']}.svg")
    assert "revoked" in revoked.text and "verified ·" not in revoked.text
    assert (await client.get(f"/v1/badge/profile/{profile['slug']}.svg")).status_code == 404
