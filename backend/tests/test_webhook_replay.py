"""Webhook replay (API-05): a developer can re-send a past delivery to their own endpoint. The same event and data, the same delivery id (so an idempotent
consumer can recognise it), marked as a replay. Stored payloads are public profile fields only and are purged after 30 days."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Webhook, WebhookJob
from app.services import webhooks as svc


@pytest.fixture
def net(monkeypatch):
    seen = []

    async def fake_post(url, body, headers):
        seen.append({"url": url, "body": body, "headers": headers})
        return httpx.Response(200)

    monkeypatch.setattr(svc, "_post", fake_post)
    monkeypatch.setattr(svc, "check_url", lambda u: u)
    return seen


async def _hook(client, make_user):
    dev, me = await make_user()
    async with get_sessionmaker()() as s:
        row = Webhook(owner_id=uuid.UUID(me["id"]), url=f"https://hooks.example.com/{uuid.uuid4().hex}",
                      events=["certificate.issued"], secret="s" * 32)
        s.add(row)
        await s.commit()
        return dev, row.id


async def _delivered_job(hook_id):
    async with get_sessionmaker()() as s:
        job = WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="certificate.issued", data={"slug": "meera-iyer", "full_name": "Meera Iyer"},
                         status="done", attempt=1)
        s.add(job)
        await s.commit()
        return job.delivery_id


async def test_replay_resends_the_same_event_with_the_same_delivery_id_and_marks_it(client, make_user, net):
    dev, hook_id = await _hook(client, make_user)
    did = await _delivered_job(hook_id)
    r = await client.post(f"/v1/webhooks/{hook_id}/deliveries/{did}/replay", headers=dev)
    assert r.status_code == 202 and r.json()["delivery_id"] == did
    await svc.settle()
    assert net, "nothing was sent"
    sent = net[-1]
    assert sent["headers"]["X-Pramaan-Delivery"] == did and sent["headers"]["X-Pramaan-Replay"] == "1"
    assert b'"slug":"meera-iyer"' in sent["body"] and sent["headers"]["X-Pramaan-Signature"].startswith("t=")


async def test_you_can_only_replay_your_own_deliveries(client, make_user, net):
    dev, hook_id = await _hook(client, make_user)
    other, _ = await make_user()
    did = await _delivered_job(hook_id)
    assert (await client.post(f"/v1/webhooks/{hook_id}/deliveries/{did}/replay", headers=other)).status_code == 404
    assert (await client.post(f"/v1/webhooks/{hook_id}/deliveries/{'0' * 32}/replay", headers=dev)).status_code == 404


async def test_a_purged_delivery_cannot_be_replayed_and_old_payloads_are_deleted(client, make_user, net):
    dev, hook_id = await _hook(client, make_user)
    async with get_sessionmaker()() as s:
        old = WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="certificate.issued", data={"slug": "x"}, status="done", attempt=1,
                         created_at=datetime.now(timezone.utc) - timedelta(days=40))
        fresh = WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="certificate.issued", data={"slug": "y"}, status="done", attempt=1)
        s.add_all([old, fresh])
        await s.commit()
        old_id, fresh_id = old.delivery_id, fresh.delivery_id
    removed = await svc.purge_old(days=30)
    assert removed >= 1
    async with get_sessionmaker()() as s:
        left = {j.delivery_id for j in (await s.execute(select(WebhookJob).where(WebhookJob.webhook_id == hook_id))).scalars()}
    assert old_id not in left and fresh_id in left
    assert (await client.post(f"/v1/webhooks/{hook_id}/deliveries/{old_id}/replay", headers=dev)).status_code == 404


async def test_a_replay_of_a_pending_delivery_is_refused_and_the_owner_must_be_signed_in_with_the_scope(client, make_user, net):
    dev, hook_id = await _hook(client, make_user)
    async with get_sessionmaker()() as s:
        job = WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="ping", data={}, status="pending")
        s.add(job)
        await s.commit()
        did = job.delivery_id
    assert (await client.post(f"/v1/webhooks/{hook_id}/deliveries/{did}/replay", headers=dev)).status_code == 409  # still being delivered
    assert (await client.post(f"/v1/webhooks/{hook_id}/deliveries/{did}/replay")).status_code == 401


def test_the_payload_headers_mark_replays():
    assert svc.REPLAY_HEADER == "X-Pramaan-Replay"


async def test_erasing_a_person_deletes_stored_webhook_payloads_that_name_them(client, make_user, net):
    dev, hook_id = await _hook(client, make_user)
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "Erase Me", "sector": "Science", "consent_public_listing": True})).json()
    async with get_sessionmaker()() as s:
        s.add_all([WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="profile.approved", data={"slug": p["slug"], "full_name": "Erase Me"}, status="done"),
                   WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="certificate.issued", data={"profile": {"slug": p["slug"]}}, status="done"),
                   WebhookJob(webhook_id=hook_id, delivery_id=uuid.uuid4().hex, event="profile.approved", data={"slug": "someone-else"}, status="done")])
        await s.commit()
    assert (await client.delete(f"/v1/profiles/{p['id']}", headers=person)).status_code == 204
    async with get_sessionmaker()() as s:
        left = [j.data for j in (await s.execute(select(WebhookJob).where(WebhookJob.webhook_id == hook_id))).scalars()]
    assert left == [{"slug": "someone-else"}]
