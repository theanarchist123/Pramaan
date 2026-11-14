"""Invitations: staff invite a specific notable person by email. It becomes a DRAFT that a person sends (nothing goes out automatically),
the link is added by our code (never taken from the staff note), and the usual safeguards apply: no existing members, no opted-out addresses.
Needs Postgres (docker compose up -d db)."""
import os

from app.db import get_sessionmaker
from app.services import outreach
from app.services.outreach import suppress


async def _invite(client, admin, **kw):
    body = {"name": "Dr. Meera Iyer", "email": f"meera-{os.urandom(3).hex()}@example.org", "note": "I admired your talk on coral reefs."}
    body.update(kw)
    return await client.post("/v1/admin/outreach/invite", headers=admin, json=body)


async def test_an_invitation_is_a_draft_with_a_link_made_by_our_code(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    r = await _invite(client, admin, note="Great work! See https://evil.example/pay now or mail x@evil.example.")
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["kind"] == "invite" and m["status"] == "draft" and m["profile_id"] is None
    assert "evil" not in m["body"] and "x@" not in m["body"]
    assert "/onboard" in m["body"] and "Meera" in m["body"]
    assert "Great work" in m["body"]  # the staff member's own words are kept


async def test_it_is_only_sent_when_a_person_sends_it_and_honours_the_safeguards(client, make_user, monkeypatch):
    sent = []
    monkeypatch.setattr(outreach, "_smtp_send", lambda to, subject, body: sent.append((to, body)))
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings

    get_settings.cache_clear()
    admin, _ = await make_user(promote_to_admin=True)
    m = (await _invite(client, admin)).json()
    assert sent == []  # drafting sent nothing
    ok = await client.post(f"/v1/admin/outbox/{m['id']}/send", headers=admin)
    assert ok.status_code == 200
    get_settings.cache_clear()


async def test_members_and_opted_out_addresses_and_bad_input_are_refused(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    _, member = await make_user()
    assert (await _invite(client, admin, email=member["email"])).status_code == 409  # already has an account
    optout = f"stop-{os.urandom(3).hex()}@example.org"
    async with get_sessionmaker()() as s:
        await suppress(s, optout, "asked to stop")
        await s.commit()
    assert (await _invite(client, admin, email=optout)).status_code == 409
    assert (await _invite(client, admin, email="not-an-email")).status_code == 422
    assert (await _invite(client, admin, name="")).status_code == 422


async def test_only_staff_can_invite(client, make_user):
    member, _ = await make_user()
    assert (await _invite(client, member)).status_code in (401, 403)
