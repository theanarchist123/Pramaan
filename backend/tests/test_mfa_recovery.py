"""Recovery codes, the operator reset tool, the governed email gate, and MFA enforcement being off by default."""

from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select, update

from app import cli
from app.config import Settings, get_settings
from app.core import totp
from app.db import get_sessionmaker
from app.models import GovernedSetting, MfaRecoveryCode, User
from app.services import audit, governed


@pytest.fixture(autouse=True)
async def _no_governed_rows_left_behind(app_instance):
    """A governed row overrides the environment (that is its job), so a test that creates one must remove it or it would
    silently change every later test in the shared database."""
    from sqlalchemy import delete

    from app.models import GovernedSetting

    governed.clear_cache()
    yield
    async with get_sessionmaker()() as s:
        await s.execute(delete(GovernedSetting))
        await s.commit()
    governed.clear_cache()


def test_mfa_enforcement_is_off_by_default_so_enabling_it_cannot_lock_anyone_out():
    assert Settings.model_fields["staff_mfa_required"].default is False


async def enrol(client, headers):
    start = (await client.post("/v1/auth/mfa/enroll", headers=headers)).json()
    done = await client.post("/v1/auth/mfa/confirm", headers=headers, json={"code": totp.code_at(start["secret"])})
    assert done.status_code == 200
    return start["secret"], done.json()["recovery_codes"]


async def clear_stepup(email):
    async with get_sessionmaker()() as s:
        await s.execute(update(User).where(User.email == email).values(stepup_until=None))
        await s.commit()


async def test_enrolment_shows_ten_recovery_codes_once_and_stores_only_hashes(client, make_user):
    admin, user = await make_user(promote_to_admin=True)
    _, codes = await enrol(client, admin)
    assert len(codes) == 10 and len(set(codes)) == 10 and all(len(c) == 9 and c[4] == "-" for c in codes)
    async with get_sessionmaker()() as s:
        rows = (await s.execute(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == uuid.UUID(user["id"])))).scalars().all()
    assert len(rows) == 10 and not any(c in r.code_hash for r in rows for c in codes)
    assert "recovery_codes" not in (await client.get("/v1/auth/mfa/status", headers=admin)).json()  # never shown again


async def test_a_recovery_code_works_once_in_place_of_the_authenticator(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "staff_mfa_required", True)
    admin, user = await make_user(promote_to_admin=True)
    _, codes = await enrol(client, admin)
    await clear_stepup(user["email"])
    sensitive = {"profile_id": str(uuid.uuid4()), "reason": "Subject access request ticket 4411"}
    assert (await client.post("/v1/admin/pii/reveal", headers=admin, json=sensitive)).json()["detail"]["code"] == "stepup_required"

    ok = await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": codes[0]})
    assert ok.status_code == 200 and ok.json()["recovery_codes_left"] == 9
    assert (await client.post("/v1/admin/pii/reveal", headers=admin, json=sensitive)).status_code != 403  # step-up satisfied
    await clear_stepup(user["email"])
    again = await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": codes[0]})
    assert again.status_code == 400 and "already used" in again.text  # single use
    assert (await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": "zzzz-zzzz"})).status_code == 400
    assert (await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": codes[1].upper()})).status_code == 200  # case-insensitive


async def test_regenerating_needs_a_fresh_step_up_and_retires_the_old_codes(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "staff_mfa_required", True)
    admin, user = await make_user(promote_to_admin=True)
    secret, old = await enrol(client, admin)
    await clear_stepup(user["email"])
    assert (await client.post("/v1/auth/mfa/recovery-codes", headers=admin)).status_code == 403  # a stolen session cannot mint codes
    await client.post("/v1/auth/mfa/stepup", headers=admin, json={"code": totp.code_at(secret)})
    new = (await client.post("/v1/auth/mfa/recovery-codes", headers=admin)).json()["recovery_codes"]
    assert len(new) == 10 and not set(new) & set(old)
    await clear_stepup(user["email"])
    assert (await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": old[0]})).status_code == 400
    assert (await client.post("/v1/auth/mfa/recover", headers=admin, json={"code": new[0]})).status_code == 200


async def test_recovery_needs_an_enrolled_account(client, make_user):
    plain, _ = await make_user()
    assert (await client.post("/v1/auth/mfa/recover", headers=plain, json={"code": "abcd-efgh"})).status_code == 409


async def test_the_reset_tool_removes_mfa_signs_the_person_out_and_writes_an_audit_entry(client, make_user):
    admin, user = await make_user(promote_to_admin=True)
    await enrol(client, admin)
    assert (await client.get("/v1/auth/me", headers=admin)).status_code == 200
    status = await cli.mfa_status(user["email"])
    assert status == {"email": user["email"], "enrolled": True, "recovery_codes_left": 10}

    with pytest.raises(SystemExit):
        await cli.reset_mfa(user["email"], "short")  # a real reason is required
    with pytest.raises(SystemExit):
        await cli.reset_mfa("nobody@example.com", "Lost phone, identity confirmed by phone call")
    out = await cli.reset_mfa(user["email"], "Lost phone, identity confirmed by phone call", operator="ops-alice")
    assert out["reset"] is True

    assert await cli.mfa_status(user["email"]) == {"email": user["email"], "enrolled": False, "recovery_codes_left": 0}
    assert (await client.get("/v1/auth/me", headers=admin)).status_code == 401  # every session ended
    async with get_sessionmaker()() as s:
        entry = (await s.execute(select(audit.AdminAuditLog).where(audit.AdminAuditLog.action == "mfa.reset")
                                 .order_by(audit.AdminAuditLog.id.desc()).limit(1))).scalar_one()
        assert entry.actor_role == "cli:ops-alice" and entry.target_id == user["id"] and "Lost phone" in entry.reason
        assert (await audit.verify_chain(s))[0] is True


async def test_the_email_gate_follows_the_governed_setting_not_just_the_environment(client, make_user):
    assert get_settings().require_email_verification is False  # the test environment
    person, _ = await make_user()
    profile = (await client.post("/v1/profiles", headers=person, json={"full_name": "Gate Test", "consent_public_listing": True})).json()
    await client.post(f"/v1/profiles/{profile['id']}/claims", headers=person, json={"field": "award", "value": "X Prize"})
    async with get_sessionmaker()() as s:
        s.add(GovernedSetting(key="require_email_verification", value={"v": True}, version=1))
        await s.commit()
    governed.clear_cache()
    try:
        assert (await client.post(f"/v1/profiles/{profile['id']}/submit", headers=person)).status_code == 403
    finally:
        async with get_sessionmaker()() as s:
            await s.execute(update(GovernedSetting).where(GovernedSetting.key == "require_email_verification").values(value={"v": False}))
            await s.commit()
        governed.clear_cache()
    assert (await client.post(f"/v1/profiles/{profile['id']}/submit", headers=person)).status_code == 200


async def test_turning_the_email_gate_off_is_a_four_eyes_change(client, make_user):
    a, _ = await make_user(promote_to_admin=True)
    b, _ = await make_user(promote_to_admin=True)
    filed = await client.post("/v1/admin/settings/require_email_verification", headers=a, json={"value": False, "reason": "Agreed in the weekly risk review"})
    assert filed.status_code == 202
    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=a)).status_code == 403
    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=b)).status_code == 200
    governed.clear_cache()
    try:
        assert await governed.get("require_email_verification") is False
    finally:
        async with get_sessionmaker()() as s:  # restore the shared test database
            await s.execute(update(GovernedSetting).where(GovernedSetting.key == "require_email_verification").values(value={"v": False}))
            await s.commit()
        governed.clear_cache()
