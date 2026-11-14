"""Guest-first onboarding: a visitor can talk to Saathi without an account, but can never be listed or certified as a guest (I-5),
and creating an account keeps their work. Needs Postgres (docker compose up -d db)."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import get_sessionmaker
from app.models import Profile, User
from app.services.guests import is_guest_email, purge_stale_guests


def test_guest_addresses_are_recognised_and_cannot_be_real_addresses():
    assert is_guest_email("guest-abc@guest.invalid")
    assert not is_guest_email("someone@example.com")
    assert not is_guest_email("guest-abc@guest.invalid.example.com")


async def _start_guest(client):
    r = await client.post("/v1/auth/guest")
    assert r.status_code == 201, r.text
    return r.json()


async def test_a_guest_can_start_a_profile_but_cannot_ask_for_verification(client):
    g = await _start_guest(client)
    h = {"Authorization": f"Bearer {g['access_token']}"}
    assert g["user"]["is_guest"] is True
    s = await client.post("/v1/onboarding/start", headers=h, json={"full_name": "Asha Rao", "consent_public_listing": True, "consent_web_research": False})
    assert s.status_code == 201, s.text
    pid = s.json()["profile"]["id"]
    blocked = await client.post(f"/v1/onboarding/{pid}/verify", headers=h)
    assert blocked.status_code == 403 and "account" in blocked.json()["detail"].lower()
    # a guest also cannot log in with a password (it has none)
    assert (await client.post("/v1/auth/login", json={"email": g["user"]["email"], "password": "anything12"})).status_code == 401


async def test_creating_an_account_keeps_the_guests_profile(client):
    g = await _start_guest(client)
    h = {"Authorization": f"Bearer {g['access_token']}"}
    pid = (await client.post("/v1/onboarding/start", headers=h, json={"full_name": "Asha Rao", "consent_public_listing": True, "consent_web_research": False})).json()["profile"]["id"]
    email = f"up-{uuid.uuid4().hex[:8]}@example.com"
    up = await client.post("/v1/auth/upgrade", headers=h, json={"email": email, "password": "password123", "name": "Asha Rao"})
    assert up.status_code == 200, up.text
    assert up.json()["user"]["is_guest"] is False and up.json()["user"]["email"] == email
    login = await client.post("/v1/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    mine = await client.get("/v1/profiles/mine", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert [p["id"] for p in mine.json()] == [pid]


async def test_upgrade_refuses_a_taken_address_and_non_guests(client, make_user):
    g = await _start_guest(client)
    gh = {"Authorization": f"Bearer {g['access_token']}"}
    _, existing = await make_user()
    taken = await client.post("/v1/auth/upgrade", headers=gh, json={"email": existing["email"], "password": "password123", "name": "X"})
    assert taken.status_code == 409
    member, _ = await make_user()
    assert (await client.post("/v1/auth/upgrade", headers=member, json={"email": f"n-{uuid.uuid4().hex[:6]}@example.com", "password": "password123", "name": "X"})).status_code == 400


async def test_stale_guests_and_their_drafts_are_purged_but_recent_ones_and_real_accounts_are_kept(client, make_user):
    old = await _start_guest(client)
    new = await _start_guest(client)
    oh = {"Authorization": f"Bearer {old['access_token']}"}
    await client.post("/v1/onboarding/start", headers=oh, json={"full_name": "Old Guest", "consent_public_listing": True, "consent_web_research": False})
    _, real = await make_user()
    async with get_sessionmaker()() as s:
        await s.execute(update(User).where(User.id == uuid.UUID(old["user"]["id"])).values(created_at=datetime.now(timezone.utc) - timedelta(days=30)))
        await s.execute(update(User).where(User.id == uuid.UUID(real["id"])).values(created_at=datetime.now(timezone.utc) - timedelta(days=30)))
        await s.commit()
    async with get_sessionmaker()() as s:
        n = await purge_stale_guests(s, days=14)
        await s.commit()
    assert n >= 1
    async with get_sessionmaker()() as s:
        assert await s.get(User, uuid.UUID(old["user"]["id"])) is None
        assert await s.get(User, uuid.UUID(new["user"]["id"])) is not None
        assert await s.get(User, uuid.UUID(real["id"])) is not None
        gone = (await s.execute(select(Profile).where(Profile.full_name == "Old Guest"))).scalars().all()
        assert gone == []
