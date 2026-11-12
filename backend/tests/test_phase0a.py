"""Phase 0a - integrity hotfix (spec findings P-16 .. P-21, invariants I-8, I-9, I-10).

The headline regression reproduces the screen that broke the product's promise: a profile the agents ESCALATED
(0 claims verified, document holder match 75%) was shown as "Verified" with claims badged "Document-verified 97%".
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy import select, text

from app.agents.events import start_run
from app.config import get_settings
from app.db import get_sessionmaker
from app.models import Claim, Document, Evidence
from tests.test_agents import PAGE, _interview, _start, fake_wikipedia  # noqa: F401
from tests.test_api_flow import _approved_profile_with_cert

REASON = {"reason": "Checked against the published honours list", "evidence_ref": "https://example.org/honours"}


def setting(monkeypatch, **values):
    for k, v in values.items():
        monkeypatch.setattr(get_settings(), k, v)


async def _escalated_profile(client, person):
    """The state in the screenshots: agents ran, nothing was proven, a 75% holder match was NOT accepted."""
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    near = b"Type: award letter\nName: Meera Iyer Rao\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\n"
    r = await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person,
                          files={"file": ("l.txt", io.BytesIO(near), "text/plain")})
    assert r.status_code == 201, r.text
    assert 0.6 <= r.json()["match_score"] < 0.85 and r.json()["claims_verified_by_document"] == 0
    return profile


async def test_screenshot_6_an_escalated_profile_is_never_certified_as_document_verified(client, make_user, monkeypatch):
    """P-16: agents say 'with a reviewer'; the certificate must not say 'Document-verified' on the same data."""
    from app import services  # noqa: F401
    from app.services import wikipedia

    async def nothing(name, limit=3):  # "No public sources match this name"
        return []

    monkeypatch.setattr(wikipedia, "fetch_sources", nothing)
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _escalated_profile(client, person)
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)

    mine = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert mine["status"] == "pending_review" and mine["decision_basis"] == ""  # escalated, not "verified"
    assert all(c["status"] == "self" for c in mine["claims"])

    # Reproduce what a flag flip used to do: approve and stamp a claim "document" at 97% with NO evidence behind it.
    assert (await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "approved"})).status_code == 200
    async with get_sessionmaker()() as s:
        claim = (await s.execute(select(Claim).where(Claim.profile_id == uuid.UUID(profile["id"])))).scalars().first()
        claim.status, claim.confidence = "document", 0.97
        await s.commit()

    r = await client.post(f"/v1/profiles/{profile['id']}/certificate", headers=person)
    assert r.status_code == 409 and "backed by evidence" in r.text  # no certificate at all


async def test_a_document_that_matched_below_the_threshold_cannot_back_a_document_status(client, make_user, monkeypatch):
    from app.services import wikipedia

    async def nothing(name, limit=3):
        return []

    monkeypatch.setattr(wikipedia, "fetch_sources", nothing)
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _escalated_profile(client, person)
    await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "approved"})
    async with get_sessionmaker()() as s:
        doc = (await s.execute(select(Document).where(Document.profile_id == uuid.UUID(profile["id"])))).scalars().first()
        claim = (await s.execute(select(Claim).where(Claim.profile_id == uuid.UUID(profile["id"]), Claim.field == "award"))).scalars().first()
        claim.status, claim.confidence = "document", 0.97
        claim.evidence.append(Evidence(kind="document", quote="Sagar Samman", source_hash=doc.extracted["sha256"]))  # real file, weak match
        await s.commit()
    assert (await client.post(f"/v1/profiles/{profile['id']}/certificate", headers=person)).status_code == 409


async def test_a_certificate_only_prints_statuses_its_evidence_supports(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    claims = (await client.get(f"/v1/certificates/{cert['code']}")).json()["payload"]["claims"]
    assert claims and all(c["status"] == "human" for c in claims)  # a reviewer vouched; it says so, nothing stronger


# ---------------------------------------------------------------------------------- the override (7.7)
async def test_override_needs_a_reason_and_evidence_and_cannot_mint_web_or_document(client, make_user):
    person, admin, profile, _ = await _approved_profile_with_cert(client, make_user)
    cid = profile["claims"][0]["id"] if profile.get("claims") else (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"][0]["id"]
    url = f"/v1/admin/claims/{cid}/verify"
    assert (await client.post(url, headers=admin, json={})).status_code == 422
    assert (await client.post(url, headers=admin, json={"reason": "short"})).status_code == 422
    for status in ("document", "web"):
        assert (await client.post(url, headers=admin, json={**REASON, "status": status})).status_code == 422
    ok = await client.post(url, headers=admin, json={**REASON, "confidence": 1.0})
    assert ok.status_code == 200 and ok.json()["status"] == "human" and ok.json()["confidence"] <= 0.9
    assert any(e["kind"] == "human" and "honours" in e["quote"] for e in ok.json()["evidence"])


async def test_nobody_reviews_their_own_profile(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    profile = (await client.post("/v1/profiles", headers=admin, json={"full_name": "Admin Person", "consent_public_listing": True})).json()
    claim = (await client.post(f"/v1/profiles/{profile['id']}/claims", headers=admin, json={"field": "award", "value": "X Prize"})).json()
    assert (await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "approved"})).status_code == 403
    assert (await client.post(f"/v1/admin/claims/{claim['id']}/verify", headers=admin, json=REASON)).status_code == 403
    await client.post(f"/v1/profiles/{profile['id']}/submit", headers=admin)
    items = (await client.get("/v1/admin/review", headers=admin)).json()
    mine = next(i for i in items if i["profile_id"] == profile["id"])
    assert (await client.post(f"/v1/admin/review/{mine['id']}/resolve", headers=admin, json={})).status_code == 403
    other, _ = await make_user(promote_to_admin=True)
    assert (await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=other, json={"status": "approved"})).status_code == 200


# ---------------------------------------------------------------------------------- the UI's server-side enum (I-9)
async def test_the_basis_of_an_approval_comes_from_the_server(client, make_user, fake_wikipedia):  # noqa: F811
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    doc = b"Type: award letter\nName: Meera Iyer\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\n"
    await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("l.txt", io.BytesIO(doc), "text/plain")})
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert p["status"] == "approved" and p["decision_basis"] == "automation"  # checks passed, no person involved

    r = await client.patch(f"/v1/profiles/{profile['id']}", headers=person, json={"bio": "An edit that needs a fresh look"})
    assert r.json()["status"] == "pending_review" and r.json()["decision_basis"] == ""  # no stale "verified"
    r = await client.post(f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "approved"})
    assert r.json()["decision_basis"] == "reviewer"


# ---------------------------------------------------------------------------------- P-17: year / number guard
def test_every_number_in_a_claim_must_be_in_the_quote():
    from app.agents.textutil import claim_specifics_in_quote as ok

    quote = "She received the Sagar Samman award in 2024."
    assert ok("Sagar Samman award", 2024, quote)
    assert not ok("Sagar Samman award 2021", None, quote)  # a real sentence about a DIFFERENT year
    assert not ok("Sagar Samman award", 2021, quote)
    assert not ok("Led 4 hackathon teams", None, quote)
    assert ok("सागर सम्मान 2024", None, "उन्हें २०२४ में सागर सम्मान मिला")  # Devanagari digits
    assert ok("Raised Rs 1,50,000", None, "She raised Rs 150000 in total")  # thousands commas ignored


async def test_a_real_quote_about_the_wrong_year_does_not_verify_a_claim(client, make_user, fake_wikipedia):  # noqa: F811
    person, _ = await make_user()
    r = await client.post("/v1/profiles", headers=person, json={"full_name": "Meera Iyer", "state": "Kerala", "consent_public_listing": True})
    pid = r.json()["id"]
    await client.post(f"/v1/profiles/{pid}/claims", headers=person, json={"field": "award", "value": "Sagar Samman award", "year": 2021})
    await client.post(f"/v1/onboarding/{pid}/verify", headers=person)
    claim = (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"][0]
    assert claim["status"] == "self"  # the page says 2024; the claim says 2021


# ---------------------------------------------------------------------------------- P-18: the applicant picks their Wikidata item
@pytest.fixture
def fake_wikidata(monkeypatch):
    from app.services import wikidata

    monkeypatch.setattr(get_settings(), "wikidata_enabled", True)
    claim = lambda v: {"mainsnak": {"datavalue": {"value": v}}}  # noqa: E731

    async def _get(params):
        if params["action"] == "wbsearchentities":
            return {"search": [{"id": "Q111"}, {"id": "Q222"}]}
        if "labels|descriptions|claims" in params["props"]:
            return {"entities": {
                "Q111": {"labels": {"en": {"value": "Meera Iyer"}}, "descriptions": {"en": {"value": "marine scientist"}},
                         "claims": {"P31": [claim({"id": "Q5"})], "P569": [claim({"time": "+1975-01-01T00:00:00Z"})]}},
                "Q222": {"labels": {"en": {"value": "Meera Iyer"}}, "descriptions": {"en": {"value": "politician"}},
                         "claims": {"P31": [claim({"id": "Q5"})]}}}}
        return {"entities": {}}

    monkeypatch.setattr(wikidata, "_get", _get)


async def test_only_the_item_the_applicant_confirmed_is_ever_used_as_evidence(client, make_user, fake_wikidata, monkeypatch):
    from app.services import wikidata, wikipedia

    used = []
    real = wikidata.fetch_by_qid

    async def spy(qid):
        used.append(qid)
        return await real(qid)

    async def no_wiki(name, limit=3):
        return []

    monkeypatch.setattr(wikidata, "fetch_by_qid", spy)
    monkeypatch.setattr(wikipedia, "fetch_sources", no_wiki)
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    pid = profile["id"]

    cands = (await client.get(f"/v1/onboarding/{pid}/wikidata-candidates", headers=person)).json()
    assert {c["qid"] for c in cands["candidates"]} == {"Q111", "Q222"} and cands["confirmed_qid"] is None
    assert next(c for c in cands["candidates"] if c["qid"] == "Q111")["born"] == "1975"

    assert (await client.post(f"/v1/onboarding/{pid}/wikidata-confirm", headers=person, json={"qid": "Q999"})).status_code == 409  # not offered
    assert (await client.post(f"/v1/onboarding/{pid}/wikidata-confirm", headers=person, json={"qid": "x; drop"})).status_code == 422
    ok = await client.post(f"/v1/onboarding/{pid}/wikidata-confirm", headers=person, json={"qid": "Q111"})
    assert ok.status_code == 200 and ok.json()["wikidata_qid"] == "Q111"
    cleared = await client.post(f"/v1/onboarding/{pid}/wikidata-confirm", headers=person, json={"qid": None})
    assert cleared.json()["wikidata_qid"] == ""

    await client.post(f"/v1/onboarding/{pid}/verify", headers=person)
    assert used == []  # nothing confirmed: Wikidata contributes nothing (a namesake can't vouch for them)

    other = await _start(client, person)  # a second profile, this time the applicant picks their item first
    await _interview(client, person, other["id"])
    await client.post(f"/v1/onboarding/{other['id']}/wikidata-confirm", headers=person, json={"qid": "Q111"})
    await client.post(f"/v1/onboarding/{other['id']}/verify", headers=person)
    assert used == ["Q111"]  # exactly the confirmed item, never Q222


# ---------------------------------------------------------------------------------- P-21: idempotent verification
async def test_a_running_verification_is_returned_not_started_twice(client, make_user, fake_wikipedia):  # noqa: F811
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    running = await start_run("verify_profile", uuid.UUID(profile["id"]))  # a run that has not finished
    r = await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert r.status_code == 202 and r.json() == {"run_id": str(running.run_id), "status": "already_running"}
    async with get_sessionmaker()() as s:
        n = (await s.execute(text("SELECT count(*) FROM agent_runs WHERE profile_id = :p AND workflow = 'verify_profile'"), {"p": uuid.UUID(profile["id"])})).scalar_one()
    assert n == 1


# ---------------------------------------------------------------------------------- CRT-01 / P-19: render guard
def test_a_certificate_render_may_only_talk_to_our_own_origins(monkeypatch):
    from app.services import render

    setting(monkeypatch, public_base_url="https://pramaan.example.org", api_base_url="https://api.pramaan.example.org", render_base_url="")
    origins = render.allowed_origins()
    assert render.request_allowed("https://pramaan.example.org/certificate-photos/x.jpg", origins)
    assert render.request_allowed("https://api.pramaan.example.org/v1/certificates/PRM-X/qr.svg", origins)
    assert render.request_allowed("data:image/svg+xml;base64,AAAA", origins)
    for evil in ("https://images.unsplash.com/photo-1", "https://fonts.googleapis.com/css", "http://pramaan.example.org/x",
                 "https://pramaan.example.org.evil.test/x", "https://169.254.169.254/latest/meta-data"):
        assert not render.request_allowed(evil, origins), evil


# ---------------------------------------------------------------------------------- TRU-00 (g): audit of existing certificates
async def test_the_audit_script_finds_certificates_whose_evidence_is_gone(client, make_user):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("audit_certificates", Path(__file__).resolve().parent.parent / "scripts" / "audit_certificates.py")
    audit_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit_mod)

    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    mine = lambda found: [b for b in found if b["code"] == cert["code"]]  # noqa: E731 - other tests' certificates share the DB
    assert not mine(await audit_mod.audit(revoke=False))  # backed: clean

    async with get_sessionmaker()() as s:  # the old bug: a status with nothing behind it
        await s.execute(text("DELETE FROM evidence WHERE kind = 'human' AND claim_id IN (SELECT id FROM claims WHERE profile_id = :p)"), {"p": uuid.UUID(profile["id"])})
        await s.commit()
    found = mine(await audit_mod.audit(revoke=False))
    assert found and found[0]["unbacked"]
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True  # report-only changed nothing

    await audit_mod.audit(revoke=True)
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["revoked"] is True


async def test_an_older_certificate_says_it_has_been_replaced_but_stays_genuine(client, make_user):
    person, admin, profile, first = await _approved_profile_with_cert(client, make_user)
    assert (await client.get(f"/v1/verify/{first['code']}")).json()["superseded_by"] == ""
    await client.post(f"/v1/profiles/{profile['id']}/claims", headers=person, json={"field": "education", "value": "Studied at Cochin University"})
    cid = next(c for c in (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"] if c["field"] == "education")["id"]
    await client.post(f"/v1/admin/claims/{cid}/verify", headers=admin, json=REASON)
    second = await client.post(f"/v1/profiles/{profile['id']}/certificate", headers=person)
    assert second.status_code == 201
    old = (await client.get(f"/v1/verify/{first['code']}")).json()
    assert old["valid"] is True and old["superseded_by"] == second.json()["code"] and "replaced" in old["reason"]
    assert (await client.get(f"/v1/verify/{second.json()['code']}")).json()["superseded_by"] == ""


async def test_the_merkle_endpoints_prove_a_real_certificate_is_in_the_signed_log(client, make_user):
    """TRU-09 end to end: issue real certificates, then verify the inclusion proof and the signed checkpoint independently."""
    import hashlib

    from app.api.verify import checkpoint_text
    from app.core import merkle
    from app.core.signing import verify_signature

    _, _, _, cert1 = await _approved_profile_with_cert(client, make_user)
    _, _, _, cert2 = await _approved_profile_with_cert(client, make_user)
    cp = (await client.get("/v1/transparency/checkpoint")).json()
    assert cp["text"] == checkpoint_text(cp["size"], cp["root"])
    keys = (await client.get("/.well-known/pramaan-keys.json")).json()
    pub = next(k for k in keys["keys"] if k["kid"] == cp["key_id"])["x"]
    assert verify_signature(hashlib.sha256(cp["text"].encode()).hexdigest(), cp["signature"], pub)

    pr = (await client.get(f"/v1/transparency/proof/{cert2['code']}")).json()
    leaf = merkle.leaf_hash(bytes.fromhex(pr["entry_hash"]))
    assert merkle.verify_inclusion(leaf, pr["index"], pr["size"], [bytes.fromhex(x) for x in pr["proof"]], bytes.fromhex(pr["root"]))

    cs = (await client.get("/v1/transparency/consistency", params={"first": max(1, pr["size"] - 1)})).json()
    assert merkle.verify_consistency(cs["first"], cs["second"], bytes.fromhex(cs["first_root"]), bytes.fromhex(cs["second_root"]), [bytes.fromhex(x) for x in cs["proof"]])
    assert (await client.get("/v1/transparency/proof/PRM-NOSUCHCODE")).status_code == 404
    assert cert1["code"] != cert2["code"]


# ---------------------------------------------------------------------------------- claim override as four-eyes (ADM-07)
async def _profile_with_one_self_claim(client, make_user):
    person, _ = await make_user()
    profile = (await client.post("/v1/profiles", headers=person, json={"full_name": "Four Eyes Person", "consent_public_listing": True})).json()
    claim = (await client.post(f"/v1/profiles/{profile['id']}/claims", headers=person, json={"field": "award", "value": "Test Prize"})).json()
    return person, profile, claim


async def test_with_four_eyes_on_a_reviewer_cannot_raise_a_claim_alone(client, make_user, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "claim_override_four_eyes", True)
    owner, profile, claim = await _profile_with_one_self_claim(client, make_user)
    a, _ = await make_user(promote_to_admin=True)
    b, _ = await make_user(promote_to_admin=True)
    mine = lambda: client.get("/v1/profiles/mine", headers=owner)  # noqa: E731

    filed = await client.post(f"/v1/admin/claims/{claim['id']}/verify", headers=a, json=REASON)
    assert filed.status_code == 202 and filed.json()["status"] == "pending"
    still = (await mine()).json()[0]["claims"][0]
    assert still["status"] == "self"  # nothing changed yet

    assert (await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=a)).status_code == 403  # not by the requester
    done = await client.post(f"/v1/admin/approvals/{filed.json()['approval_id']}/approve", headers=b)
    assert done.status_code == 200, done.text
    now = (await mine()).json()[0]["claims"][0]
    assert now["status"] == "human" and any(e["kind"] == "human" for e in now["evidence"])


async def test_lowering_a_claim_is_always_immediate_and_the_default_is_unchanged(client, make_user, monkeypatch):
    from app.config import get_settings

    _, profile, claim = await _profile_with_one_self_claim(client, make_user)
    a, _ = await make_user(promote_to_admin=True)
    assert (await client.post(f"/v1/admin/claims/{claim['id']}/verify", headers=a, json=REASON)).status_code == 200  # setting off: as before
    monkeypatch.setattr(get_settings(), "claim_override_four_eyes", True)
    down = await client.post(f"/v1/admin/claims/{claim['id']}/verify", headers=a, json={**REASON, "status": "self"})
    assert down.status_code == 200 and down.json()["status"] == "self"  # the safe direction needs no second person


async def test_the_profile_owner_cannot_approve_the_request_for_their_own_claim(client, make_user, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "claim_override_four_eyes", True)
    owner, profile, claim = await _profile_with_one_self_claim(client, make_user)
    a, _ = await make_user(promote_to_admin=True)
    filed = (await client.post(f"/v1/admin/claims/{claim['id']}/verify", headers=a, json=REASON)).json()
    # the owner becomes staff (legacy admin) and tries to decide on their own profile (I-10)
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import User

    async with get_sessionmaker()() as s:
        me = (await client.get("/v1/auth/me", headers=owner)).json()
        await s.execute(update(User).where(User.id == uuid.UUID(me["id"])).values(role="admin"))
        await s.commit()
    assert (await client.post(f"/v1/admin/approvals/{filed['approval_id']}/approve", headers=owner)).status_code == 403
