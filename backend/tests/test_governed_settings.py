"""Governed settings, PII reveal, and the 'a Reviewer cannot ...' matrix."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import UserRole
from app.services import governed
from tests.test_api_flow import _approved_profile_with_cert

REASON = "Agreed in the weekly risk review"


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


async def staff(make_user, role):
    headers, user = await make_user()
    async with get_sessionmaker()() as s:
        s.add(UserRole(user_id=uuid.UUID(user["id"]), role_key=role))
        await s.commit()
    return headers, user


def test_validation_enforces_types_and_the_hard_floor():
    assert governed.validate("award_claims_need_human", False) is False
    assert governed.validate("auto_approve_threshold", 0.97) == 0.97
    for key, bad in [("auto_approve_threshold", 0.5), ("auto_approve_threshold", 1.5), ("auto_approve_threshold", True),
                     ("award_claims_need_human", "no"), ("nonsense", True)]:
        with pytest.raises(ValueError):
            governed.validate(key, bad)


async def test_a_setting_changes_only_after_a_second_person_approves_and_the_history_is_kept(client, make_user):
    admin_a, _ = await make_user(promote_to_admin=True)
    admin_b, _ = await make_user(promote_to_admin=True)
    before = {s["key"]: s for s in (await client.get("/v1/admin/settings", headers=admin_a)).json()}
    assert before["auto_approve_threshold"]["value"] == 0.95 and before["auto_approve_threshold"]["source"] == "environment"

    assert (await client.post("/v1/admin/settings/auto_approve_threshold", headers=admin_a, json={"value": 0.5, "reason": REASON})).status_code == 422
    filed = await client.post("/v1/admin/settings/auto_approve_threshold", headers=admin_a, json={"value": 0.98, "reason": REASON})
    assert filed.status_code == 202
    assert await governed.get("auto_approve_threshold") == 0.95  # nothing changes on one person's say-so
    aid = filed.json()["approval_id"]
    assert (await client.post(f"/v1/admin/approvals/{aid}/approve", headers=admin_a)).status_code == 403
    assert (await client.post(f"/v1/admin/approvals/{aid}/approve", headers=admin_b)).status_code == 200

    governed.clear_cache()
    now = {s["key"]: s for s in (await client.get("/v1/admin/settings", headers=admin_a)).json()}["auto_approve_threshold"]
    assert now["value"] == 0.98 and now["source"] == "database" and now["version"] == 1
    again = await client.post("/v1/admin/settings/auto_approve_threshold", headers=admin_a, json={"value": 0.96, "reason": REASON})
    await client.post(f"/v1/admin/approvals/{again.json()['approval_id']}/approve", headers=admin_b)
    governed.clear_cache()
    assert (await governed.get("auto_approve_threshold")) == 0.96

    from sqlalchemy import select

    from app.models import GovernedSettingChange

    async with get_sessionmaker()() as s:
        changes = (await s.execute(select(GovernedSettingChange).where(GovernedSettingChange.key == "auto_approve_threshold")
                                   .order_by(GovernedSettingChange.at))).scalars().all()
    assert [(c.old["v"], c.new["v"]) for c in changes][-2:] == [(0.95, 0.98), (0.98, 0.96)]
    assert all(c.approval_request_id for c in changes)
    # put the shared test database back
    reset = await client.post("/v1/admin/settings/auto_approve_threshold", headers=admin_a, json={"value": 0.95, "reason": REASON})
    await client.post(f"/v1/admin/approvals/{reset.json()['approval_id']}/approve", headers=admin_b)


async def test_a_database_value_overrides_the_environment_default(client, make_user):
    """The lookup Prahari uses prefers the governed row over the environment (the 5 s cache is cleared here)."""
    from sqlalchemy import update

    from app.models import GovernedSetting

    assert get_settings().award_claims_need_human is False  # the environment default in tests
    async with get_sessionmaker()() as s:
        s.add(GovernedSetting(key="award_claims_need_human", value={"v": True}, version=1))
        await s.commit()
    governed.clear_cache()
    try:
        assert await governed.get("award_claims_need_human") is True
    finally:
        async with get_sessionmaker()() as s:
            await s.execute(update(GovernedSetting).where(GovernedSetting.key == "award_claims_need_human").values(value={"v": False}))
            await s.commit()
        governed.clear_cache()
    assert await governed.get("award_claims_need_human") is False


async def test_pii_reveal_needs_the_permission_a_reason_a_fresh_code_and_is_logged(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    compliance, _ = await staff(make_user, "compliance")
    body = {"profile_id": profile["id"], "reason": "Subject access request ticket 4411"}
    assert (await client.post("/v1/admin/pii/reveal", headers=compliance, json={**body, "reason": "short"})).status_code == 422
    ok = await client.post("/v1/admin/pii/reveal", headers=compliance, json=body)
    assert ok.status_code == 200 and "@" in ok.json()["email"]
    log = (await client.get("/v1/admin/audit", headers=admin, params={"action": "pii.reveal"})).json()
    assert log and log[0]["reason"] == body["reason"] and log[0]["target_id"] == profile["id"]


async def test_a_reviewer_gets_403_on_override_revoke_settings_and_pii_reveal(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    reviewer, rev_user = await staff(make_user, "reviewer")
    claim_id = (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"][0]["id"]
    attempts = {
        "override": client.post(f"/v1/admin/claims/{claim_id}/verify", headers=reviewer,
                                json={"reason": "I looked at it myself", "evidence_ref": "https://example.org/x"}),
        "revoke": client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=reviewer, json={"reason": REASON}),
        "settings": client.post("/v1/admin/settings/award_claims_need_human", headers=reviewer, json={"value": False, "reason": REASON}),
        "pii reveal": client.post("/v1/admin/pii/reveal", headers=reviewer, json={"profile_id": profile["id"], "reason": REASON}),
        "role grant": client.post(f"/v1/admin/staff/{rev_user['id']}/roles", headers=reviewer, json={"role": "super_admin", "reason": REASON}),
        "audit log": client.get("/v1/admin/audit", headers=reviewer),
    }
    for name, call in attempts.items():
        assert (await call).status_code == 403, name
    assert (await client.get("/v1/admin/review", headers=reviewer)).status_code == 200  # what a reviewer CAN do


async def test_a_reviewer_cannot_approve_a_settings_request_either(client, make_user):
    admin_a, _ = await make_user(promote_to_admin=True)
    reviewer, _ = await staff(make_user, "reviewer")
    filed = await client.post("/v1/admin/settings/award_claims_need_human", headers=admin_a, json={"value": False, "reason": REASON})
    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=reviewer)).status_code == 403


def test_a_first_listing_no_longer_needs_a_person_by_default_but_award_claims_still_do():
    """Owner decision 2026-11-19 (docs/adr/0018-fewer-routine-reviews.md): a person is not sent every first listing any more (a matching document already has to prove
    identity). Award claims keep a person until issuers are checked at the source."""
    from app.config import Settings

    # The test environment overrides both through environment variables (conftest), so read the declared defaults, not a live Settings().
    assert Settings.model_fields["human_approval_first_listing"].default is False
    assert Settings.model_fields["award_claims_need_human"].default is True
