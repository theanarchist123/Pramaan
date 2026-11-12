"""Doot policy (AGT-09): fixed templates, send windows, and auto-send ONLY for approved low-risk kinds. Every safeguard in send() still applies."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.agents import doot
from app.db import get_sessionmaker
from app.models import EmailSuppression, GovernedSetting, OutboxMessage, Profile
from app.services import governed, outreach
from tests.test_api_flow import _approved_profile_with_cert

IST = timezone.utc  # windows are computed in IST inside the module; tests pass aware UTC times


def utc(h, m=0, day=11):
    return datetime(2026, 11, day, h, m, tzinfo=timezone.utc)


def test_the_send_window_is_9_to_6_in_india_and_otherwise_waits_for_the_next_morning():
    # 09:00 IST = 03:30 UTC ; 18:00 IST = 12:30 UTC
    assert outreach.next_send_window(utc(5, 0)) == utc(5, 0)            # 10:30 IST: inside, now
    assert outreach.next_send_window(utc(13, 0)) == utc(3, 30, day=12)  # 18:30 IST: tomorrow 09:00 IST
    assert outreach.next_send_window(utc(1, 0)) == utc(3, 30)           # 06:30 IST: today 09:00 IST


def test_the_fixed_template_is_deterministic_and_has_only_system_links():
    facts = {"first_name": "Asha", "status": "approved", "claims": 2, "verified": 2}
    links = doot.links_for("asha-rao", "PRM-ABC")
    a, b = doot.fixed_message("welcome_share", facts, links), doot.fixed_message("welcome_share", facts, links)
    assert a == b and "Asha" in a[1] and links["verify"] in a[1]
    import re

    found = set(re.findall(r"https?://\S+", a[1]))
    base = links["profile"].rsplit("/p/", 1)[0]
    assert found and all(u.startswith(base) for u in found)  # nothing but our own domain


def test_only_the_welcome_kind_is_low_risk_enough_to_auto_send():
    assert outreach.AUTO_SEND_KINDS == {"welcome_share"}


@pytest.fixture(autouse=True)
async def _clean(client):
    governed.clear_cache()
    async with get_sessionmaker()() as s:
        await s.execute(delete(OutboxMessage))
        await s.execute(delete(EmailSuppression))
        await s.execute(delete(GovernedSetting).where(GovernedSetting.key == "outreach_autosend_welcome"))
        await s.commit()
    yield
    governed.clear_cache()


async def _switch(on: bool):
    async with get_sessionmaker()() as s:
        s.add(GovernedSetting(key="outreach_autosend_welcome", value={"v": on}, version=1))
        await s.commit()
    governed.clear_cache()


async def _profile_with_cert(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    return uuid.UUID(profile["id"])


async def _msgs(pid):
    async with get_sessionmaker()() as s:
        return (await s.execute(select(OutboxMessage).where(OutboxMessage.profile_id == pid))).scalars().all()


async def test_by_default_nothing_is_auto_sent(client, make_user):
    pid = await _profile_with_cert(client, make_user)
    async with get_sessionmaker()() as s:
        await outreach.welcome_if_allowed(s, pid, now=utc(5))
        await s.commit()
    assert await _msgs(pid) == []  # the switch is off: people still approve drafts by hand


async def test_with_the_switch_on_a_fixed_welcome_is_sent_once_inside_the_window(client, make_user):
    pid = await _profile_with_cert(client, make_user)
    await _switch(True)
    async with get_sessionmaker()() as s:
        await outreach.welcome_if_allowed(s, pid, now=utc(5))
        await outreach.welcome_if_allowed(s, pid, now=utc(5))  # again: no second email
        await s.commit()
    msgs = await _msgs(pid)
    assert len(msgs) == 1 and msgs[0].kind == "welcome_share" and msgs[0].status == "sent" and "dry-run" in msgs[0].error  # SMTP is off in tests


async def test_outside_the_window_it_is_scheduled_for_the_next_morning_not_sent(client, make_user):
    pid = await _profile_with_cert(client, make_user)
    await _switch(True)
    async with get_sessionmaker()() as s:
        await outreach.welcome_if_allowed(s, pid, now=utc(20))
        await s.commit()
    (m,) = await _msgs(pid)
    assert m.status == "scheduled" and m.scheduled_for == utc(3, 30, day=12)


async def test_a_suppressed_or_opted_out_person_is_never_auto_emailed(client, make_user):
    pid = await _profile_with_cert(client, make_user)
    await _switch(True)
    async with get_sessionmaker()() as s:
        from app.models import User

        prof = await s.get(Profile, pid)
        owner = await s.get(User, prof.owner_id)
        await outreach.suppress(s, owner.email, "asked to stop")
        await s.commit()
    async with get_sessionmaker()() as s:
        await outreach.welcome_if_allowed(s, pid, now=utc(5))
        await s.commit()
    (m,) = await _msgs(pid)
    assert m.status == "discarded" and "opted out" in m.error


async def test_no_certificate_means_no_welcome(client, make_user):
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "No Cert", "sector": "Science", "consent_public_listing": True})).json()
    await _switch(True)
    async with get_sessionmaker()() as s:
        prof = await s.get(Profile, uuid.UUID(p["id"]))
        prof.status = "approved"
        await s.commit()
        await outreach.welcome_if_allowed(s, prof.id, now=utc(5))
        await s.commit()
    assert await _msgs(uuid.UUID(p["id"])) == []


async def test_send_due_leaves_scheduled_mail_alone_outside_the_window(client, make_user, monkeypatch):
    pid = await _profile_with_cert(client, make_user)
    async with get_sessionmaker()() as s:
        s.add(OutboxMessage(profile_id=pid, kind="welcome_share", to_email="x@example.com", subject="Hello there", body="b" * 50, status="scheduled",
                            scheduled_for=utc(1)))
        await s.commit()
    assert await outreach.send_due(now=utc(14)) == 0     # 19:30 IST: not now
    assert (await _msgs(pid))[0].status == "scheduled"
    assert await outreach.send_due(now=utc(5)) == 1      # 10:30 IST
    assert (await _msgs(pid))[0].status == "sent"


async def test_issuing_a_certificate_triggers_the_welcome_policy(client, make_user):
    await _switch(True)
    pid = await _profile_with_cert(client, make_user)   # issuing happens inside this helper
    msgs = await _msgs(pid)
    assert len(msgs) == 1 and msgs[0].kind == "welcome_share" and msgs[0].status in ("sent", "scheduled")
