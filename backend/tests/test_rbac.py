"""Phase 2 backend core: staff roles, four-eyes approvals, and the append-only hash-chained audit log."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db import get_sessionmaker
from app.models import UserRole
from tests.test_api_flow import _approved_profile_with_cert

REASON = "Confirmed with the issuing body by phone"


async def grant(user_id: str, role: str) -> None:
    async with get_sessionmaker()() as s:
        s.add(UserRole(user_id=uuid.UUID(user_id), role_key=role))
        await s.commit()


async def staff(make_user, role: str):
    headers, user = await make_user()
    await grant(user["id"], role)
    return headers, user


async def test_permissions_follow_roles_and_the_legacy_admin_keeps_everything(client, make_user):
    plain, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    reviewer, _ = await staff(make_user, "reviewer")
    assert (await client.get("/v1/admin/me/permissions", headers=plain)).status_code == 403
    everything = (await client.get("/v1/admin/me/permissions", headers=admin)).json()
    assert everything["legacy_admin"] and {"claim.override", "certificate.revoke", "audit.read"} <= set(everything["permissions"])
    mine = (await client.get("/v1/admin/me/permissions", headers=reviewer)).json()
    assert mine["roles"] == ["reviewer"] and "review.decide" in mine["permissions"]
    assert not {"claim.override", "certificate.revoke", "role.assign", "audit.read", "settings.write"} & set(mine["permissions"])


async def test_a_reviewer_can_review_but_cannot_override_revoke_assign_or_read_the_audit_log(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    reviewer, rev_user = await staff(make_user, "reviewer")
    assert (await client.get("/v1/admin/review", headers=reviewer)).status_code == 200  # staff, so the queue is theirs
    claim_id = (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"][0]["id"]
    body = {"reason": REASON, "evidence_ref": "https://example.org/honours"}
    assert (await client.post(f"/v1/admin/claims/{claim_id}/verify", headers=reviewer, json=body)).status_code == 403
    assert (await client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=reviewer, json={"reason": REASON})).status_code == 403
    assert (await client.post(f"/v1/admin/staff/{rev_user['id']}/roles", headers=reviewer, json={"role": "super_admin", "reason": REASON})).status_code == 403
    assert (await client.get("/v1/admin/audit", headers=reviewer)).status_code == 403
    assert (await client.get("/v1/admin/system", headers=reviewer)).status_code == 403
    senior, _ = await staff(make_user, "senior_verifier")  # the role that may override
    assert (await client.post(f"/v1/admin/claims/{claim_id}/verify", headers=senior, json=body)).status_code == 200


async def test_revoking_a_certificate_needs_two_different_people(client, make_user):
    person, admin_a, profile, cert = await _approved_profile_with_cert(client, make_user)
    admin_b, _ = await make_user(promote_to_admin=True)
    filed = await client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=admin_a, json={"reason": REASON})
    assert filed.status_code == 202
    aid = filed.json()["approval_id"]
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True  # nothing happens on one person's say-so

    own = await client.post(f"/v1/admin/approvals/{aid}/approve", headers=admin_a)
    assert own.status_code == 403 and "second person" in own.text
    registry, _ = await staff(make_user, "registry_manager")
    reviewer, _ = await staff(make_user, "reviewer")
    assert (await client.post(f"/v1/admin/approvals/{aid}/approve", headers=reviewer)).status_code == 403  # lacks the permission

    done = await client.post(f"/v1/admin/approvals/{aid}/approve", headers=registry)
    assert done.status_code == 200 and done.json()["status"] == "approved"
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["revoked"] is True
    assert (await client.post(f"/v1/admin/approvals/{aid}/approve", headers=admin_b)).status_code == 409  # already decided
    assert (await client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=admin_b, json={"reason": REASON})).status_code == 409
    assert (await client.post("/v1/admin/certificates/PRM-NOPE/revoke", headers=admin_b, json={"reason": REASON})).status_code == 404


async def test_a_rejected_request_changes_nothing(client, make_user):
    person, admin_a, profile, cert = await _approved_profile_with_cert(client, make_user)
    admin_b, _ = await make_user(promote_to_admin=True)
    aid = (await client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=admin_a, json={"reason": REASON})).json()["approval_id"]
    no = await client.post(f"/v1/admin/approvals/{aid}/reject", headers=admin_b, json={"note": "Not enough evidence"})
    assert no.status_code == 200 and no.json()["status"] == "rejected"
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True


async def test_granting_a_role_is_four_eyes_too(client, make_user):
    admin_a, _ = await make_user(promote_to_admin=True)
    admin_b, _ = await make_user(promote_to_admin=True)
    newbie, newbie_user = await make_user()
    assert (await client.get("/v1/admin/me/permissions", headers=newbie)).status_code == 403
    assert (await client.post(f"/v1/admin/staff/{newbie_user['id']}/roles", headers=admin_a, json={"role": "wizard", "reason": REASON})).status_code == 422
    filed = await client.post(f"/v1/admin/staff/{newbie_user['id']}/roles", headers=admin_a, json={"role": "auditor", "reason": REASON})
    assert filed.status_code == 202
    assert (await client.get("/v1/admin/me/permissions", headers=newbie)).status_code == 403  # still nothing
    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=admin_a)).status_code == 403
    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=admin_b)).status_code == 200
    got = (await client.get("/v1/admin/me/permissions", headers=newbie)).json()
    assert got["roles"] == ["auditor"] and "audit.read" in got["permissions"]
    listed = (await client.get("/v1/admin/staff", headers=admin_a)).json()
    assert any(u["id"] == newbie_user["id"] and u["roles"] == ["auditor"] for u in listed)


async def test_every_staff_action_lands_in_a_verifiable_chain_that_cannot_be_edited(client, make_user):
    person, admin_a, profile, cert = await _approved_profile_with_cert(client, make_user)
    admin_b, _ = await make_user(promote_to_admin=True)
    aid = (await client.post(f"/v1/admin/certificates/{cert['code']}/revoke", headers=admin_a, json={"reason": REASON})).json()["approval_id"]
    await client.post(f"/v1/admin/approvals/{aid}/approve", headers=admin_b)

    entries = (await client.get("/v1/admin/audit", headers=admin_a, params={"limit": 500})).json()
    actions = {e["action"] for e in entries}
    assert {"profile.status", "claim.override", "certificate.revoke.requested", "certificate.revoke.approved", "http.POST"} <= actions
    approved = next(e for e in entries if e["action"] == "certificate.revoke.approved" and e["target_id"] == aid)
    assert approved["actor_id"] and approved["reason"] == REASON
    assert (await client.get("/v1/admin/audit/verify", headers=admin_a)).json()["valid"] is True

    async with get_sessionmaker()() as s:  # the database itself refuses to rewrite or erase history
        for stmt in ("UPDATE admin_audit_log SET reason = 'edited'", "DELETE FROM admin_audit_log"):
            with pytest.raises(Exception, match="append-only"):
                await s.execute(text(stmt))
            await s.rollback()


async def test_verification_detects_a_tampered_entry_even_if_someone_disables_the_trigger():
    from app.services import audit

    async with get_sessionmaker()() as s:
        await audit.record(s, actor_id=None, actor_role="test", action="t.one", reason="first")
        await audit.record(s, actor_id=None, actor_role="test", action="t.two", reason="second")
        assert (await audit.verify_chain(s))[0] is True
        await s.execute(text("ALTER TABLE admin_audit_log DISABLE TRIGGER admin_audit_log_no_change"))
        await s.execute(text("UPDATE admin_audit_log SET reason = 'rewritten' WHERE action = 't.one'"))
        ok, bad, _ = await audit.verify_chain(s)
        assert ok is False and bad is not None  # the chain notices
        await s.rollback()  # DDL and the edit are transactional: everything is put back
        assert (await audit.verify_chain(s))[0] is True


def test_permission_tables_are_consistent():
    from app.core.rbac import ACTION_PERMISSION, ALL_PERMISSIONS, ROLE_PERMISSIONS

    assert set(ACTION_PERMISSION.values()) <= ALL_PERMISSIONS
    assert "claim.override" not in ROLE_PERMISSIONS["reviewer"]  # the spec's "reviewer cannot override"
    assert "role.assign" in ROLE_PERMISSIONS["super_admin"] and "role.assign" not in ROLE_PERMISSIONS["senior_verifier"]
