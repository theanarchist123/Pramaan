"""The separate staff session: its own cookie, short, strict, and never interchangeable with the member session."""

from __future__ import annotations

import uuid

from sqlalchemy import update

from app import deps
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import User

ORIGIN = {"Origin": "http://localhost:3001"}
PASSWORD = "password123"


async def register(client, *, staff: bool):
    email = f"s-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/v1/auth/register", json={"email": email, "password": PASSWORD, "name": "S"})
    assert r.status_code == 201
    if staff:
        async with get_sessionmaker()() as s:
            await s.execute(update(User).where(User.email == email).values(role="admin"))
            await s.commit()
    client.cookies.clear()  # the member cookie from registering is not what these tests are about
    return email


async def test_admin_login_sets_a_strict_httponly_cookie_that_only_works_on_staff_endpoints(cookie_client):
    email = await register(cookie_client, staff=True)
    r = await cookie_client.post("/v1/admin/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200 and r.json()["session_minutes"] == get_settings().admin_session_minutes
    cookie = r.headers["set-cookie"].lower()
    assert "pramaan_admin=" in cookie and "httponly" in cookie and "samesite=strict" in cookie
    assert f"max-age={get_settings().admin_session_minutes * 60}" in cookie  # short-lived

    assert (await cookie_client.get("/v1/admin/me/permissions")).status_code == 200
    assert (await cookie_client.get("/v1/auth/me")).status_code == 401  # the staff session does not log you into the member site


async def test_a_member_session_is_useless_on_the_staff_api(cookie_client):
    email = await register(cookie_client, staff=False)
    await cookie_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})  # the MEMBER login
    assert (await cookie_client.get("/v1/auth/me")).status_code == 200
    assert (await cookie_client.get("/v1/admin/me/permissions")).status_code == 401  # a stolen member cookie gets nothing here


async def test_staff_accounts_cannot_sign_in_as_members(cookie_client):
    """Staff sign in at the staff console only: the member login refuses them and issues no session, whether they are a legacy admin or hold a granted role."""
    email = await register(cookie_client, staff=True)
    r = await cookie_client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 403 and "staff console" in r.json()["detail"]
    assert "set-cookie" not in r.headers and "access_token" not in r.text
    assert (await cookie_client.get("/v1/auth/me")).status_code == 401
    wrong = await cookie_client.post("/v1/auth/login", json={"email": email, "password": "nope-nope-nope"})
    assert wrong.status_code == 401  # a wrong password still looks like any other: nothing about staff is revealed without the password

    from sqlalchemy import select, update

    from app.db import get_sessionmaker
    from app.models import User, UserRole

    member = await register(cookie_client, staff=False)
    assert (await cookie_client.post("/v1/auth/login", json={"email": member, "password": PASSWORD})).status_code == 200  # ordinary members are unaffected
    async with get_sessionmaker()() as s:  # role-based staff: an ordinary account that was granted a staff role
        uid = (await s.execute(select(User.id).where(User.email == member))).scalar_one()
        s.add(UserRole(user_id=uid, role_key="reviewer"))
        await s.commit()
    assert (await cookie_client.post("/v1/auth/login", json={"email": member, "password": PASSWORD})).status_code == 403


async def test_only_staff_can_sign_in_and_every_failure_looks_the_same(cookie_client):
    member = await register(cookie_client, staff=False)
    staff = await register(cookie_client, staff=True)
    not_staff = await cookie_client.post("/v1/admin/auth/login", json={"email": member, "password": PASSWORD})
    wrong_pw = await cookie_client.post("/v1/admin/auth/login", json={"email": staff, "password": "nope-nope-nope"})
    nobody = await cookie_client.post("/v1/admin/auth/login", json={"email": "ghost@example.com", "password": PASSWORD})
    assert {not_staff.status_code, wrong_pw.status_code, nobody.status_code} == {401}
    assert not_staff.json() == wrong_pw.json() == nobody.json()  # the form cannot reveal who is staff


async def test_staff_writes_with_the_cookie_must_come_from_the_admin_origin(cookie_client, monkeypatch):
    email = await register(cookie_client, staff=True)
    await cookie_client.post("/v1/admin/auth/login", json={"email": email, "password": PASSWORD})
    body = {"role": "auditor", "reason": "Agreed in the weekly risk review"}
    uid = (await cookie_client.get("/v1/admin/me/permissions")).status_code  # warm: cookie works
    assert uid == 200
    evil = await cookie_client.post(f"/v1/admin/staff/{uuid.uuid4()}/roles", json=body, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403 and "Cross-site" in evil.text
    assert (await cookie_client.post(f"/v1/admin/staff/{uuid.uuid4()}/roles", json=body)).status_code == 403  # no Origin at all
    assert (await cookie_client.post(f"/v1/admin/staff/{uuid.uuid4()}/roles", json=body, headers=ORIGIN)).status_code == 404  # reached the handler


def test_in_production_the_admin_origin_and_the_public_origin_are_not_interchangeable(monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    monkeypatch.setattr(get_settings(), "public_base_url", "https://pramaan.example.org")
    monkeypatch.setattr(get_settings(), "admin_base_url", "https://admin.pramaan.example.org")
    assert deps._origin_allowed("https://admin.pramaan.example.org", admin=True)
    assert not deps._origin_allowed("https://pramaan.example.org", admin=True)  # the public site cannot drive staff writes
    assert not deps._origin_allowed("https://admin.pramaan.example.org", admin=False)
    assert deps.admin_cookie_name() == "__Host-pramaan_admin"


async def test_logout_clears_the_staff_cookie(cookie_client):
    email = await register(cookie_client, staff=True)
    await cookie_client.post("/v1/admin/auth/login", json={"email": email, "password": PASSWORD})
    assert (await cookie_client.post("/v1/admin/auth/logout", headers=ORIGIN)).status_code == 204
    assert (await cookie_client.get("/v1/admin/me/permissions")).status_code == 401
