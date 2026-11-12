"""Doot safeguards (AGT-09), enforced where every email passes: suppression list, frequency cap, consent re-checked at send time, and an unsubscribe
link the SYSTEM appends. The real send() runs; only the SMTP sender is replaced by a recorder (conftest blocks real email in every test)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Consent, EmailSuppression, OutboxMessage, Profile
from app.services import outreach


@pytest.fixture
def smtp(monkeypatch):
    sent: list[tuple] = []
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.example.test")
    monkeypatch.setattr(outreach, "_smtp_send", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


@pytest.fixture(autouse=True)
async def _clean(app_instance):
    async with get_sessionmaker()() as s:
        await s.execute(delete(EmailSuppression))
        await s.commit()
    yield


async def _send(to: str, *, profile_id=None, subject="Hello", body="A short, plain message.", sent_before: list[datetime] | None = None):
    """Create a message (optionally with earlier SENT messages to the same address) and run the real send()."""
    async with get_sessionmaker()() as s:
        for when in sent_before or []:
            s.add(OutboxMessage(profile_id=profile_id, kind="custom", to_email=to, subject="old", body="old", status="sent", sent_at=when))
        msg = OutboxMessage(profile_id=profile_id, kind="custom", to_email=to, subject=subject, body=body, status="draft")
        s.add(msg)
        await s.flush()
        await outreach.send(s, msg)
        await s.commit()
        return msg.status, msg.error


async def test_a_suppressed_address_is_never_emailed_even_if_a_human_approves_the_send(smtp):
    async with get_sessionmaker()() as s:
        await outreach.suppress(s, "Opted.Out@Example.org", reason="asked to stop")
        await s.commit()
    status, error = await _send("opted.out@example.org")  # different casing: still the same person
    assert status == "discarded" and "opted out" in error and smtp == []


async def test_the_frequency_cap_holds_the_fourth_email_in_30_days_for_a_human_to_decide(smtp):
    now = datetime.now(timezone.utc)
    recent = [now - timedelta(days=d) for d in (1, 5, 20)]
    status, error = await _send("busy@example.org", sent_before=recent)
    assert status == "draft" and "cap" in error.lower() and smtp == []  # held, not discarded: a person decides
    # three OLD ones do not count; a different address is unaffected
    assert (await _send("calm@example.org", sent_before=[now - timedelta(days=40)] * 3))[0] == "sent"
    assert (await _send("other@example.org", sent_before=recent[:2]))[0] == "sent"  # two recent: under the cap
    assert len(smtp) == 2


async def test_consent_withdrawn_after_drafting_stops_the_send(client, make_user, smtp):
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "Consent Case", "consent_public_listing": True})).json()
    async with get_sessionmaker()() as s:
        s.add(Consent(profile_id=uuid.UUID(p["id"]), kind="outreach", granted=True))
        await s.flush()
        s.add(Consent(profile_id=uuid.UUID(p["id"]), kind="outreach", granted=False, created_at=datetime.now(timezone.utc) + timedelta(seconds=1)))
        await s.commit()
    status, error = await _send("someone@example.org", profile_id=uuid.UUID(p["id"]))
    assert status == "discarded" and "withdrawn" in error and smtp == []


async def test_every_email_carries_an_unsubscribe_link_that_really_works_and_cannot_be_forged(client, smtp):
    assert (await _send("reader@example.org"))[0] == "sent"
    body = smtp[0][2]
    marker = "/v1/outreach/unsubscribe?token="
    assert marker in body
    token = body.split(marker, 1)[1].split()[0].strip()

    bad = await client.get("/v1/outreach/unsubscribe", params={"token": token[:-3] + "xyz"})
    assert bad.status_code == 400  # a tampered token does nothing
    assert (await client.get("/v1/outreach/unsubscribe", params={"token": token})).status_code == 200
    assert (await client.get("/v1/outreach/unsubscribe", params={"token": token})).status_code == 200  # safe to click twice
    async with get_sessionmaker()() as s:
        assert len((await s.execute(select(EmailSuppression))).scalars().all()) == 1

    smtp.clear()
    status, _ = await _send("reader@example.org")
    assert status == "discarded" and smtp == []  # and it sticks


async def test_the_dry_run_path_obeys_the_same_rules(monkeypatch):
    monkeypatch.setattr(get_settings(), "smtp_host", "")
    async with get_sessionmaker()() as s:
        await outreach.suppress(s, "dry@example.org", reason="x")
        await s.commit()
    status, error = await _send("dry@example.org")
    assert status == "discarded" and "opted out" in error  # a dry run must not pretend to send to someone who opted out


async def test_the_suppression_list_stores_only_a_hash_never_the_address(smtp):
    async with get_sessionmaker()() as s:
        await outreach.suppress(s, "private.person@example.org", reason="asked")
        await s.commit()
        row = (await s.execute(select(EmailSuppression))).scalar_one()
    assert "private" not in row.email_hash and "@" not in row.email_hash and len(row.email_hash) == 64
