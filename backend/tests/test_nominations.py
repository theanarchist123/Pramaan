"""'Nominate someone' (DR-22). A signed-in member suggests a person; that creates ONE DRAFT invitation for staff to look at. Nothing is emailed by the nomination itself,
no profile exists until the nominee joins and agrees (I-5), and no link or address the nominator typed ever reaches the nominee (I-7)."""
from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import OutboxMessage, Profile

BODY = {"name": "Dr. Kavita Rao", "email": "kavita.rao@example.org", "note": "She built the Pune solar grid. See http://evil.example/x or mail bad@evil.example or call +91 98765 43210"}


async def _drafts(email):
    async with get_sessionmaker()() as s:
        return (await s.execute(select(OutboxMessage).where(OutboxMessage.to_email == email, OutboxMessage.kind == "nomination"))).scalars().all()


async def test_a_nomination_creates_one_draft_and_sends_nothing(client, make_user):
    me, _ = await make_user()
    r = await client.post("/v1/nominations", headers=me, json=BODY)
    assert r.status_code == 202 and r.json() == {"status": "received"}
    (m,) = await _drafts(BODY["email"])
    assert m.status == "draft" and m.sent_at is None                       # a person looks first
    assert "/onboard" in m.body and "Kavita Rao" in m.body                 # our link, their name
    assert "evil.example" not in m.body and "98765" not in m.body          # I-7: nothing the nominator typed that could take the nominee elsewhere
    async with get_sessionmaker()() as s:
        assert (await s.execute(select(Profile).where(Profile.full_name == "Dr. Kavita Rao"))).first() is None  # I-5: no profile until she joins and agrees


async def test_the_same_person_nominated_twice_is_one_draft(client, make_user):
    a, _ = await make_user()
    b, _ = await make_user()
    body = {**BODY, "email": "twice.nominated@example.org"}
    assert (await client.post("/v1/nominations", headers=a, json=body)).status_code == 202
    assert (await client.post("/v1/nominations", headers=b, json=body)).status_code == 202   # the answer never reveals that someone else already did
    assert len(await _drafts(body["email"])) == 1


async def test_the_answer_does_not_reveal_who_already_has_an_account(client, make_user):
    me, _ = await make_user()
    _, other = await make_user()
    r = await client.post("/v1/nominations", headers=me, json={**BODY, "email": other["email"]})
    assert r.status_code == 202 and r.json() == {"status": "received"}
    assert await _drafts(other["email"]) == []                                               # but nothing is drafted for an existing member


async def test_opted_out_addresses_get_nothing(client, make_user):
    from app.services import outreach

    me, _ = await make_user()
    async with get_sessionmaker()() as s:
        await outreach.suppress(s, "optout@example.org", "asked to stop")
        await s.commit()
    assert (await client.post("/v1/nominations", headers=me, json={**BODY, "email": "optout@example.org"})).status_code == 202
    assert await _drafts("optout@example.org") == []


async def test_only_signed_in_members_can_nominate_and_it_is_rate_limited(client, make_user):
    assert (await client.post("/v1/nominations", json=BODY)).status_code == 401
    me, _ = await make_user()
    codes = [(await client.post("/v1/nominations", headers=me, json={**BODY, "email": f"n{i}@example.org"})).status_code for i in range(5)]
    assert codes[:3] == [202, 202, 202] and 429 in codes[3:]
