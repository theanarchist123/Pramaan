"""Registry and compliance: suspend/restore a profile, and a read-only view of consents (ADM-16)."""

from __future__ import annotations

from tests.test_api_flow import _approved_profile_with_cert
from tests.test_review_workbench import staff

WHY = {"reason": "Credible report that the biography contains false statements"}


async def test_suspending_hides_a_profile_everywhere_public_and_restoring_brings_it_back(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    manager, _ = await staff(make_user, "registry_manager")
    slug = profile["slug"]
    assert (await client.get(f"/v1/profiles/{slug}")).status_code == 200

    sus = await client.post(f"/v1/admin/registry/profiles/{profile['id']}/suspend", headers=manager, json=WHY)
    assert sus.status_code == 200 and sus.json()["status"] == "suspended"
    assert (await client.get(f"/v1/profiles/{slug}")).status_code == 404  # anonymous visitors no longer see it
    listed = (await client.get("/v1/profiles?limit=100")).json()
    assert profile["id"] not in [p["id"] for p in listed]
    assert (await client.get("/v1/profiles/mine", headers=person)).json()[0]["status"] == "suspended"  # the owner still sees it, and why

    assert (await client.post(f"/v1/profiles/{profile['id']}/submit", headers=person)).status_code in (200, 409)
    assert (await client.get("/v1/profiles/mine", headers=person)).json()[0]["status"] == "suspended"  # cannot resubmit its way out

    back = await client.post(f"/v1/admin/registry/profiles/{profile['id']}/restore", headers=manager, json=WHY)
    assert back.status_code == 200 and back.json()["status"] == "approved"
    assert (await client.get(f"/v1/profiles/{slug}")).status_code == 200


async def test_suspending_needs_the_right_role_a_reason_and_not_your_own_profile(client, make_user):
    person, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    reviewer, _ = await staff(make_user, "reviewer")
    manager, _ = await staff(make_user, "registry_manager")
    url = f"/v1/admin/registry/profiles/{profile['id']}/suspend"
    assert (await client.post(url, headers=reviewer, json=WHY)).status_code == 403  # a reviewer cannot
    assert (await client.post(url, headers=manager, json={"reason": "short"})).status_code == 422  # a real reason is required
    assert (await client.post(url, headers=person, json=WHY)).status_code in (401, 403)  # nor can the owner

    # a registry manager who owns a profile cannot suspend it either (I-10)
    own_headers, own_user = await staff(make_user, "registry_manager")
    mine = (await client.post("/v1/profiles", headers=own_headers, json={"full_name": "Own Profile", "consent_public_listing": True})).json()
    assert (await client.post(f"/v1/admin/registry/profiles/{mine['id']}/suspend", headers=own_headers, json=WHY)).status_code == 403


async def test_suspension_and_restoration_are_in_the_audit_log_and_only_apply_to_the_right_state(client, make_user):
    person, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    manager, _ = await staff(make_user, "registry_manager")
    assert (await client.post(f"/v1/admin/registry/profiles/{profile['id']}/restore", headers=manager, json=WHY)).status_code == 409  # not suspended
    await client.post(f"/v1/admin/registry/profiles/{profile['id']}/suspend", headers=manager, json=WHY)
    assert (await client.post(f"/v1/admin/registry/profiles/{profile['id']}/suspend", headers=manager, json=WHY)).status_code == 409  # already
    auditor, _ = await staff(make_user, "auditor")
    log = (await client.get("/v1/admin/audit?limit=20", headers=auditor)).json()
    assert any(e["action"] == "profile.suspend" and e["target_id"] == profile["id"] for e in log)


async def test_the_consent_view_is_read_only_and_needs_the_consent_permission(client, make_user):
    person, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    compliance, _ = await staff(make_user, "compliance")
    rows = (await client.get(f"/v1/admin/consents?profile_id={profile['id']}", headers=compliance)).json()
    assert rows and {"kind", "granted", "created_at"} <= set(rows[0]) and rows[0]["kind"] == "public_listing"
    reviewer, _ = await staff(make_user, "reviewer")
    assert (await client.get(f"/v1/admin/consents?profile_id={profile['id']}", headers=reviewer)).status_code == 403
