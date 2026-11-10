"""Staff MFA (TOTP) and step-up authentication."""

from __future__ import annotations

import base64
import time
import uuid

import pytest

from app.config import get_settings
from app.core import totp
from app.db import get_sessionmaker
from app.models import UserRole
from tests.test_api_flow import _approved_profile_with_cert

REASON = "Confirmed with the issuing body by phone"


def test_totp_matches_the_rfc_6238_test_vectors():
    # RFC 6238 appendix B, SHA-1, secret "12345678901234567890", 8 digits there; we use the last 6 of the same HOTP value.
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert totp.code_at(secret, at=59) == "287082"  # 94287082 -> 287082
    assert totp.code_at(secret, at=1111111109) == "081804"  # 07081804
    assert totp.code_at(secret, at=1234567890) == "005924"  # 89005924


def test_codes_are_checked_with_a_small_window_and_garbage_is_refused():
    secret = totp.new_secret()
    now = time.time()
    assert totp.verify(secret, totp.code_at(secret, now))
    assert totp.verify(secret, totp.code_at(secret, now - 30))  # one step of clock drift
    assert not totp.verify(secret, totp.code_at(secret, now - 300))
    for bad in ("", "12345", "abcdef", "1234567"):
        assert not totp.verify(secret, bad)


def test_the_secret_is_encrypted_at_rest():
    secret = totp.new_secret()
    sealed = totp.seal(secret)
    assert secret not in sealed and totp.unseal(sealed) == secret and totp.unseal("garbage") is None


@pytest.fixture
def mfa_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "staff_mfa_required", True)


async def enrol(client, headers):
    start = (await client.post("/v1/auth/mfa/enroll", headers=headers)).json()
    assert (await client.post("/v1/auth/mfa/confirm", headers=headers, json={"code": totp.code_at(start["secret"])})).status_code == 200
    return start["secret"]


async def test_staff_without_mfa_are_locked_out_until_they_enrol(client, make_user, mfa_on):
    admin, _ = await make_user(promote_to_admin=True)
    blocked = await client.get("/v1/admin/review", headers=admin)
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "mfa_required"
    assert (await client.get("/v1/auth/mfa/status", headers=admin)).json()["enrolled"] is False  # enrolment itself still works
    start = await client.post("/v1/auth/mfa/enroll", headers=admin)
    assert start.status_code == 200 and start.json()["otpauth_uri"].startswith("otpauth://totp/Pramaan:")
    wrong = "000000" if totp.code_at(start.json()["secret"]) != "000000" else "111111"
    assert (await client.post("/v1/auth/mfa/confirm", headers=admin, json={"code": wrong})).status_code == 400
    assert (await client.post("/v1/auth/mfa/confirm", headers=admin, json={"code": totp.code_at(start.json()["secret"])})).status_code == 200
    assert (await client.get("/v1/admin/review", headers=admin)).status_code == 200
    assert (await client.post("/v1/auth/mfa/enroll", headers=admin)).status_code == 409  # cannot be silently replaced


async def test_sensitive_actions_need_a_fresh_code_and_it_expires(client, make_user, monkeypatch):
    person, admin_a, profile, cert = await _approved_profile_with_cert(client, make_user)  # set up with MFA off...
    monkeypatch.setattr(get_settings(), "staff_mfa_required", True)  # ...then switch it on
    secret = await enrol(client, admin_a)
    from sqlalchemy import update

    from app.models import User

    async with get_sessionmaker()() as s:  # enrolment grants a step-up window; start from "no recent code"
        await s.execute(update(User).where(User.email == (await client.get("/v1/auth/me", headers=admin_a)).json()["email"]).values(stepup_until=None))
        await s.commit()
    revoke = f"/v1/admin/certificates/{cert['code']}/revoke"
    refused = await client.post(revoke, headers=admin_a, json={"reason": REASON})
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "stepup_required"

    assert (await client.post("/v1/auth/mfa/stepup", headers=admin_a, json={"code": "000000" if totp.code_at(secret) != "000000" else "111111"})).status_code == 400
    assert (await client.post("/v1/auth/mfa/stepup", headers=admin_a, json={"code": totp.code_at(secret)})).status_code == 200
    assert (await client.post(revoke, headers=admin_a, json={"reason": REASON})).status_code == 202

    async with get_sessionmaker()() as s:  # a stale window is the same as none
        from datetime import datetime, timedelta, timezone

        await s.execute(update(User).where(User.email == (await client.get("/v1/auth/me", headers=admin_a)).json()["email"]).values(stepup_until=datetime.now(timezone.utc) - timedelta(minutes=1)))
        await s.commit()
    assert (await client.post(revoke, headers=admin_a, json={"reason": REASON})).status_code == 403


async def test_ordinary_members_are_not_asked_for_mfa(client, make_user, mfa_on):
    person, _ = await make_user()
    assert (await client.get("/v1/profiles/mine", headers=person)).status_code == 200
    assert (await client.get("/v1/auth/mfa/status", headers=person)).json()["required"] is True
