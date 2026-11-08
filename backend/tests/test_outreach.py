"""Doot: drafts follow-ups; a human approves everything; links and recipients can't be hijacked."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.agents.schemas import OutreachDraft
from app.config import get_settings
from app.db import get_sessionmaker
from app.llm.client import LLM, LLMError, set_llm_override
from app.models import Consent, OutboxMessage, Profile, ReviewItem
from app.services import outreach
from tests.test_api_flow import _approved_profile_with_cert


@pytest.fixture(autouse=True)
def _llm():
    set_llm_override(None)
    yield
    set_llm_override(None)


async def suggest(client, admin, **kw):
    r = await client.post("/v1/admin/outreach/suggest", headers=admin, json=kw)
    assert r.status_code == 200, r.text
    return r.json()


def mine(msgs, profile_id):
    return [m for m in msgs if m["profile_id"] == profile_id]


async def test_a_verified_person_gets_a_welcome_draft_with_real_links(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    msgs = mine(await suggest(client, admin), profile["id"])
    assert len(msgs) == 1
    m = msgs[0]
    assert m["kind"] == "welcome_share" and m["status"] == "draft" and m["sent_at"] is None
    base = get_settings().public_base_url
    assert f"{base}/verify/{cert['code']}" in m["body"] and f"{base}/p/{profile['slug']}" in m["body"]
    assert "@example.com" in m["to_email"] and "Reply to stop" in m["body"]


async def test_suggesting_twice_never_duplicates(client, make_user):
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    first = mine(await suggest(client, admin), profile["id"])
    second = mine(await suggest(client, admin), profile["id"])
    assert len(first) == 1 and second == []
    # a discarded draft is a decision a human made — don't resurrect it either? (it may be re-drafted)
    await client.post(f"/v1/admin/outbox/{first[0]['id']}/discard", headers=admin)
    assert mine(await suggest(client, admin), profile["id"])  # discarded -> eligible again


async def test_model_text_cannot_smuggle_links_or_addresses(client, make_user):
    class Phisher(LLM):
        async def structured(self, schema, **kw):
            if schema is OutreachDraft:
                return OutreachDraft(
                    subject="Verified!\nBcc: attacker@evil.example",
                    body=("Congratulations on being verified. Please confirm your bank details at "
                          "http://evil.example/phish or www.evil.example/x or mail bad@evil.example right away "
                          "so that we can complete your listing today."),
                )
            return await super().structured(schema, **kw)

    set_llm_override(Phisher())
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]
    assert "evil" not in m["body"] and "evil" not in m["subject"]
    assert "\n" not in m["subject"] and "Bcc" not in m["subject"].split(":")[0] or "attacker" not in m["subject"]
    assert get_settings().public_base_url in m["body"]  # the legitimate links are still there


async def test_when_the_model_is_down_standard_wording_is_used(client, make_user):
    class Down(LLM):
        async def structured(self, schema, **kw):
            raise LLMError("offline")

    set_llm_override(Down())
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]
    assert m["subject"].startswith("You're verified") and "Congratulations" in m["body"]


async def _make_profile(client, make_user, status_setup=None):
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "Nudge Target", "consent_public_listing": True})).json()
    await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": "Some award"})
    return person, p


async def test_stuck_review_and_idle_drafts_are_nudged_only_after_the_wait(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    _, stuck = await _make_profile(client, make_user)
    person2, idle = await _make_profile(client, make_user)
    await client.post(f"/v1/profiles/{stuck['id']}/submit", headers=(await make_user())[0])  # not the owner: no effect
    owner_headers = person2  # idle one stays a draft

    # make `stuck` a pending review that is about documents
    stuck_owner = (await client.get("/v1/admin/profiles", headers=admin)).json()
    async with get_sessionmaker()() as s:
        await s.execute(update(Profile).where(Profile.id == stuck["id"]).values(status="pending_review"))
        s.add(ReviewItem(profile_id=stuck["id"], reason="Identity not confirmed by a matching document", confidence=0.5))
        await s.commit()

    # defaults: nothing is old enough yet
    default = await suggest(client, admin)
    assert not mine(default, stuck["id"]) and not mine(default, idle["id"])

    zero = await suggest(client, admin, review_after_hours=0, idle_after_hours=0)
    s_msg, i_msg = mine(zero, stuck["id"]), mine(zero, idle["id"])
    assert s_msg and s_msg[0]["kind"] == "needs_document" and "document" in s_msg[0]["body"].lower()
    assert i_msg and i_msg[0]["kind"] == "finish_profile"
    assert get_settings().public_base_url + "/onboard" in s_msg[0]["body"]


async def test_demo_profiles_and_opted_out_people_are_never_contacted(client, make_user):
    person, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    async with get_sessionmaker()() as s:
        s.add(Consent(profile_id=profile["id"], kind="outreach", granted=False, text="no thanks"))
        await s.commit()
    assert mine(await suggest(client, admin), profile["id"]) == []
    # demo profiles have no owner at all
    async with get_sessionmaker()() as s:
        demo = (await s.execute(update(Profile).where(Profile.is_demo.is_(True)).values(slug=Profile.slug).returning(Profile.id))).all()
        await s.rollback()
    assert all(m["profile_id"] not in {str(d[0]) for d in demo} for m in await suggest(client, admin))


async def test_nothing_is_sent_until_a_human_acts(client, make_user):
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]
    assert await outreach.send_due() >= 0  # the scheduler tick…
    got = (await client.get("/v1/admin/outbox", headers=admin)).json()
    assert next(x for x in got if x["id"] == m["id"])["status"] == "draft"  # …never touches drafts


async def test_edit_then_send_is_a_recorded_dry_run_without_smtp(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]

    e = await client.patch(f"/v1/admin/outbox/{m['id']}", headers=admin,
                           json={"subject": "Hello\r\nBcc: x@y.z", "body": "A personal note from the team, edited by hand."})
    assert e.status_code == 200 and "\n" not in e.json()["subject"] and "\r" not in e.json()["subject"]
    sent = (await client.post(f"/v1/admin/outbox/{m['id']}/send", headers=admin)).json()
    assert sent["status"] == "sent" and sent["sent_at"] and "dry-run" in sent["error"]
    assert (await client.post(f"/v1/admin/outbox/{m['id']}/send", headers=admin)).status_code == 409  # not twice
    assert (await client.patch(f"/v1/admin/outbox/{m['id']}", headers=admin, json={"body": "too late to edit"})).status_code == 409
    assert (await client.post(f"/v1/admin/outbox/{m['id']}/discard", headers=admin)).status_code == 409


async def test_real_smtp_path_and_failure_returns_to_draft(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.example.com")
    calls = []
    monkeypatch.setattr(outreach, "_smtp_send", lambda to, subject, body: calls.append((to, subject, body)))
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]
    sent = (await client.post(f"/v1/admin/outbox/{m['id']}/send", headers=admin)).json()
    assert sent["status"] == "sent" and sent["error"] == "" and calls[0][0] == m["to_email"]

    def boom(*a):
        raise ConnectionRefusedError("nope")

    monkeypatch.setattr(outreach, "_smtp_send", boom)
    _, admin2, profile2, _ = await _approved_profile_with_cert(client, make_user)
    m2 = mine(await suggest(client, admin2), profile2["id"])[0]
    failed = (await client.post(f"/v1/admin/outbox/{m2['id']}/send", headers=admin2)).json()
    assert failed["status"] == "draft" and "ConnectionRefusedError" in failed["error"]  # a human decides what next


async def test_scheduling_sends_only_when_due(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    _, admin2, profile2, _ = await _approved_profile_with_cert(client, make_user)
    drafted = await suggest(client, admin)  # one call drafts for everyone who is eligible
    m1, m2 = mine(drafted, profile["id"])[0], mine(drafted, profile2["id"])[0]
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert (await client.post(f"/v1/admin/outbox/{m1['id']}/schedule", headers=admin, json={"at": past})).json()["status"] == "scheduled"
    await client.post(f"/v1/admin/outbox/{m2['id']}/schedule", headers=admin, json={"at": future})
    assert await outreach.send_due() >= 1
    status = {x["id"]: x["status"] for x in (await client.get("/v1/admin/outbox", headers=admin)).json()}
    assert status[m1["id"]] == "sent" and status[m2["id"]] == "scheduled"


async def test_a_bad_recipient_address_is_never_mailed(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.example.com")
    calls = []
    monkeypatch.setattr(outreach, "_smtp_send", lambda *a: calls.append(a))
    _, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    m = mine(await suggest(client, admin), profile["id"])[0]
    async with get_sessionmaker()() as s:
        await s.execute(update(OutboxMessage).where(OutboxMessage.id == m["id"]).values(to_email="a@b.c\nBcc: evil@x.y"))
        await s.commit()
    r = (await client.post(f"/v1/admin/outbox/{m['id']}/send", headers=admin)).json()
    assert r["status"] == "draft" and "invalid recipient" in r["error"] and not calls


async def test_outreach_is_admin_only(client, make_user):
    person, _ = await make_user()
    for method, path in (("post", "/v1/admin/outreach/suggest"), ("get", "/v1/admin/outbox")):
        assert (await getattr(client, method)(path, headers=person)).status_code == 403
        assert (await getattr(client, method)(path)).status_code == 401
