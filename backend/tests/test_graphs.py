"""The document, dispute and post-approval graphs (AGT-02), driven through Sutradhar. Every failure ends with a person (I-2)."""
import io
import uuid

import pytest
from sqlalchemy import select

from app.agents import sutradhar
from app.db import get_sessionmaker
from app.domain import STATUS_SELF, STATUS_WEB
from app.evidence.base import EvidenceDoc
from app.models import AgentRun, Claim, Document, Evidence, Profile, ReviewItem
from app.services import governed


@pytest.fixture(autouse=True)
def _fresh(client):
    governed.clear_cache()
    yield
    governed.clear_cache()


async def _approved_profile(client, make_user, claim_text="Won the Sahitya Akademi Award in 2019", name="Meera Iyer"):
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": name, "sector": "Literature", "state": "Kerala", "consent_public_listing": True})).json()
    await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": claim_text, "year": 2019})
    async with get_sessionmaker()() as s:
        prof = await s.get(Profile, uuid.UUID(p["id"]))
        prof.status = "approved"
        claim = (await s.execute(select(Claim).where(Claim.profile_id == prof.id))).scalars().first()
        claim.status, claim.confidence = STATUS_WEB, 0.9
        claim.evidence.append(Evidence(kind="web", url="https://en.wikipedia.org/wiki/x", quote=claim_text, source_hash="a" * 64))
        await s.commit()
        return person, p["id"], str(claim.id)


class _FakeAdapter:
    name, reliability = "fake", 0.9

    def __init__(self, text):
        self.text = text

    async def search(self, person):
        return [EvidenceDoc(title=person.name, url="https://en.wikipedia.org/wiki/Fresh", text=self.text, source="fake")]


async def test_a_dispute_that_the_fresh_evidence_does_not_back_demotes_the_claim_and_reaches_a_person(client, make_user, monkeypatch):
    _, pid, cid = await _approved_profile(client, make_user)
    monkeypatch.setattr("app.evidence.default_adapters", lambda: [_FakeAdapter("Meera Iyer is a poet from Kochi who enjoys long walks.")])
    out = await sutradhar.dispatch("claim.disputed", key=f"dispute:{cid}:1", payload={"profile_id": pid, "claim_id": cid, "reason": "I never won this"}, wait=True)
    assert out.status == "done"
    async with get_sessionmaker()() as s:
        claim = await s.get(Claim, uuid.UUID(cid))
        assert claim.status == STATUS_SELF and claim.confidence == 0.0  # cannot be printed on a certificate any more (I-8)
        item = (await s.execute(select(ReviewItem).where(ReviewItem.profile_id == uuid.UUID(pid), ReviewItem.status == "open"))).scalars().first()
        assert item is not None and "Claim disputed" in item.reason and "no longer supported" in item.reason
        assert (await s.get(Profile, uuid.UUID(pid))).status == "approved"  # hiding the profile is a person's decision


async def test_a_dispute_the_evidence_still_backs_is_still_sent_to_a_person(client, make_user, monkeypatch):
    _, pid, cid = await _approved_profile(client, make_user)
    monkeypatch.setattr("app.evidence.default_adapters",
                        lambda: [_FakeAdapter("Biography. Meera Iyer won the Sahitya Akademi Award in 2019 for her poetry. More text.")])
    out = await sutradhar.dispatch("claim.disputed", key=f"dispute:{cid}:2", payload={"profile_id": pid, "claim_id": cid, "reason": "check it"}, wait=True)
    assert out.status == "done"
    async with get_sessionmaker()() as s:
        claim = await s.get(Claim, uuid.UUID(cid))
        assert claim.status == STATUS_WEB
        item = (await s.execute(select(ReviewItem).where(ReviewItem.profile_id == uuid.UUID(pid), ReviewItem.status == "open"))).scalars().first()
        assert item is not None and "still supported" in item.reason  # the machine never closes a dispute on its own


async def test_a_dispute_on_a_claim_of_another_profile_fails_safe_to_a_person(client, make_user):
    _, pid, _ = await _approved_profile(client, make_user)
    out = await sutradhar.dispatch("claim.disputed", key=f"dispute:bad:{pid}", payload={"profile_id": pid, "claim_id": str(uuid.uuid4()), "reason": "x"}, wait=True)
    assert out.status == "failed"
    async with get_sessionmaker()() as s:
        item = (await s.execute(select(ReviewItem).where(ReviewItem.profile_id == uuid.UUID(pid), ReviewItem.status == "open"))).scalars().first()
        assert item is not None and "could not finish" in item.reason


async def test_the_post_approval_graph_indexes_connects_and_never_issues_a_certificate(client, make_user):
    _, pid, _ = await _approved_profile(client, make_user)
    out = await sutradhar.dispatch("profile.approved", key=f"approved:{pid}", payload={"profile_id": pid}, wait=True)
    assert out.status == "done"
    async with get_sessionmaker()() as s:
        run = (await s.execute(select(AgentRun).where(AgentRun.idempotency_key == f"approved:{pid}"))).scalar_one()
        assert "index: ok" in run.summary and "connect: ok" in run.summary and run.status == "done"
        from app.models import Certificate

        assert (await s.execute(select(Certificate).where(Certificate.profile_id == uuid.UUID(pid)))).first() is None  # only the person asks for one (I-5)


async def test_the_document_graph_rereads_a_stored_document_and_flags_a_doubtful_one(client, make_user):
    person, _ = await make_user()
    p = (await client.post("/v1/onboarding/start", headers=person, json={"consent_public_listing": True, "consent_web_research": True})).json()["profile"]
    await client.post(f"/v1/onboarding/{p['id']}/message", headers=person, json={"text": "My name is Meera Iyer, a poet from Kerala"})
    text = b"Certificate of Honour\nAwarded to Someone Else Entirely\nfor poetry in 2019\nIssued by the Sahitya Akademi"
    up = await client.post(f"/v1/onboarding/{p['id']}/documents", headers=person, files={"file": ("a.txt", io.BytesIO(text), "text/plain")})
    assert up.status_code == 201
    async with get_sessionmaker()() as s:
        doc = (await s.execute(select(Document).where(Document.profile_id == uuid.UUID(p["id"])))).scalars().first()
        did = str(doc.id)
    out = await sutradhar.dispatch("document.added", key=f"doc:{did}:recheck", payload={"profile_id": p["id"], "document_id": did}, wait=True)
    assert out.status == "done"
    async with get_sessionmaker()() as s:
        item = (await s.execute(select(ReviewItem).where(ReviewItem.profile_id == uuid.UUID(p["id"]), ReviewItem.status == "open"))).scalars().first()
        assert item is not None  # a name that does not match goes to a person


async def test_a_switched_off_reader_leaves_the_upload_for_a_person(client, make_user):
    from app.models import GovernedSetting

    person, _ = await make_user()
    p = (await client.post("/v1/onboarding/start", headers=person, json={"consent_public_listing": True, "consent_web_research": True})).json()["profile"]
    async with get_sessionmaker()() as s:
        s.add(GovernedSetting(key="agent_lipik_enabled", value={"v": False}, version=1))
        await s.commit()
    governed.clear_cache()
    try:
        r = await client.post(f"/v1/onboarding/{p['id']}/documents", headers=person, files={"file": ("a.txt", io.BytesIO(b"Certificate"), "text/plain")})
        assert r.status_code == 201 and r.json()["sent_to_review"] is True and r.json()["claims_verified_by_document"] == 0
    finally:
        async with get_sessionmaker()() as s:
            row = await s.get(GovernedSetting, "agent_lipik_enabled")
            await s.delete(row)
            await s.commit()
        governed.clear_cache()


async def test_submitting_for_verification_goes_through_sutradhar_and_accepts_an_idempotency_key(client, make_user):
    person, _ = await make_user()
    p = (await client.post("/v1/onboarding/start", headers=person, json={"consent_public_listing": True, "consent_web_research": True})).json()["profile"]
    await client.post(f"/v1/onboarding/{p['id']}/message", headers=person, json={"text": "My name is Meera Iyer, a physicist from Kerala. I won the National Science Award in 2024."})
    a = await client.post(f"/v1/onboarding/{p['id']}/verify", headers={**person, "Idempotency-Key": "abc123"})
    assert a.status_code == 202
    async with get_sessionmaker()() as s:
        runs = (await s.execute(select(AgentRun).where(AgentRun.profile_id == uuid.UUID(p["id"]), AgentRun.idempotency_key.is_not(None)))).scalars().all()
        assert len(runs) == 1 and runs[0].idempotency_key.endswith("abc123") and runs[0].versions.get("policy")


async def test_a_reviewer_can_dispute_a_claim_but_not_on_their_own_profile(client, make_user, monkeypatch):

    owner, pid, cid = await _approved_profile(client, make_user)
    reviewer, _ = await make_user(promote_to_admin=True)
    monkeypatch.setattr("app.evidence.default_adapters", lambda: [_FakeAdapter("Nothing relevant.")])
    r = await client.post(f"/v1/admin/claims/{cid}/dispute", headers=reviewer, json={"reason": "The award year looks wrong to me"})
    assert r.status_code == 202 and r.json()["run_id"]
    assert (await client.post(f"/v1/admin/claims/{cid}/dispute", headers=owner, json={"reason": "I want this gone please"})).status_code == 403
    assert (await client.post(f"/v1/admin/claims/{cid}/dispute", headers=reviewer, json={"reason": "short"})).status_code == 422
