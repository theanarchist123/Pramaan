"""Agent pipeline tests: offline (mock) LLM + faked Wikipedia, real database."""

from __future__ import annotations

import io
import uuid

import pytest

from app.agents.events import bus, start_run
from app.agents.schemas import ClaimVerdict, FactCheckReport
from app.llm.client import LLM, LLMError, set_llm_override
from app.services import wikipedia
from app.services.wikipedia import Source

PAGE = Source(
    title="Meera Iyer",
    url="https://en.wikipedia.org/wiki/Meera_Iyer",
    text="Meera Iyer is an Indian marine scientist from Kerala. She received the Sagar Samman award in 2024.",
)


@pytest.fixture(autouse=True)
def _reset_llm():
    set_llm_override(None)
    yield
    set_llm_override(None)


@pytest.fixture
def fake_wikipedia(monkeypatch):
    async def fake(name, limit=3):
        return [PAGE] if "meera" in name.lower() else []

    monkeypatch.setattr(wikipedia, "fetch_sources", fake)


async def _start(client, headers, **consents):
    body = {"consent_public_listing": True, "consent_web_research": True, **consents}
    r = await client.post("/v1/onboarding/start", headers=headers, json=body)
    assert r.status_code == 201, r.text
    return r.json()["profile"]


async def _interview(client, headers, pid):
    r = await client.post(f"/v1/onboarding/{pid}/message", headers=headers, json={"text": "My name is Meera Iyer"})
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/v1/onboarding/{pid}/message", headers=headers,
        json={"text": "I am a marine scientist working in Kerala. I received the Sagar Samman award in 2024."},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_interview_builds_profile_without_a_form(client, make_user):
    person, _ = await make_user()
    profile = await _start(client, person)
    assert profile["full_name"] == "New Profile"

    turn1 = (
        await client.post(f"/v1/onboarding/{profile['id']}/message", headers=person,
                          json={"text": "My name is Meera Iyer"})
    ).json()
    assert turn1["profile"]["full_name"] == "Meera Iyer"
    assert "name" not in turn1["missing"]
    assert turn1["profile"]["slug"].startswith("meera-iyer")
    assert turn1["ready_to_submit"] is False

    turn2 = await _interview_second(client, person, profile["id"])
    p = turn2["profile"]
    assert p["sector"] == "Science" and p["state"] == "Kerala"
    assert any(c["field"] == "award" and c["year"] == 2024 for c in p["claims"])
    assert all(c["status"] == "self" for c in p["claims"])  # chat alone never verifies anything
    assert turn2["ready_to_submit"] is True

    history = (await client.get(f"/v1/onboarding/{profile['id']}/messages", headers=person)).json()
    assert [m["role"] for m in history][:2] == ["assistant", "user"]


async def _interview_second(client, person, pid):
    r = await client.post(
        f"/v1/onboarding/{pid}/message", headers=person,
        json={"text": "I am a marine scientist working in Kerala. I received the Sagar Samman award in 2024."},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_web_evidence_verifies_but_never_auto_approves(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])

    r = await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert r.status_code == 202

    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    award = next(c for c in p["claims"] if c["field"] == "award")
    assert award["status"] == "web" and 0.5 <= award["confidence"] <= 0.9
    assert any(e["kind"] == "web" and "Sagar Samman" in e["quote"] for e in award["evidence"])
    # web-only can never reach the 95% bar -> a human decides
    assert p["status"] == "pending_review"


async def test_matching_document_plus_evidence_auto_approves(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])

    doc = b"Type: award letter\nName: Meera Iyer\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\n"
    r = await client.post(
        f"/v1/onboarding/{profile['id']}/documents", headers=person,
        files={"file": ("letter.txt", io.BytesIO(doc), "text/plain")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["flags"] == [] and r.json()["claims_verified_by_document"] == 1

    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert p["status"] == "approved"  # ≥95%, identity confirmed by the document
    assert next(c for c in p["claims"] if c["field"] == "award")["status"] == "document"


async def test_document_for_a_different_person_is_flagged_and_escalated(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])

    forged = b"Name: Someone Else\nTitle: Sagar Samman award\nIssuer: Ministry\nYear: 2024\n"
    r = await client.post(
        f"/v1/onboarding/{profile['id']}/documents", headers=person,
        files={"file": ("x.txt", io.BytesIO(forged), "text/plain")},
    )
    assert r.json()["flags"] == ["identity_mismatch"]
    assert r.json()["claims_verified_by_document"] == 0

    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert p["status"] == "pending_review"
    queue = (await client.get("/v1/admin/review", headers=admin)).json()
    item = next(i for i in queue if i["profile_id"] == profile["id"])
    assert "does not match" in item["reason"] and item["confidence"] <= 0.4


async def test_no_public_evidence_means_human_review(client, make_user, monkeypatch):
    async def nothing(name, limit=3):
        return []

    monkeypatch.setattr(wikipedia, "fetch_sources", nothing)
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert p["status"] == "pending_review"
    assert all(c["status"] == "self" for c in p["claims"])


async def test_fabricated_citation_is_rejected(client, make_user, fake_wikipedia):
    """If the model invents a quote that isn't in the source, the claim must NOT be verified."""

    class LyingLLM(LLM):
        async def structured(self, schema, **kw):
            if schema is FactCheckReport:
                claims = kw["mock_context"]["claims"]
                return FactCheckReport(verdicts=[
                    ClaimVerdict(claim_id=c["id"], verdict="supported", source_index=0,
                                 quote="She was awarded the Padma Vibhushan in 2024 by the President",
                                 confidence=0.99, note="made up")
                    for c in claims
                ])
            return await super().structured(schema, **kw)

    set_llm_override(LyingLLM())
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)

    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert all(c["status"] == "self" for c in p["claims"])
    assert p["status"] == "pending_review"


async def test_pipeline_failure_fails_safe_never_approves(client, make_user, fake_wikipedia):
    class BrokenLLM(LLM):
        async def structured(self, schema, **kw):
            if schema is FactCheckReport:
                raise LLMError("upstream exploded")
            return await super().structured(schema, **kw)

    set_llm_override(BrokenLLM())
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)

    p = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert p["status"] == "pending_review"
    runs = (await client.get("/v1/agents/runs", headers=admin)).json()
    run = next(r for r in runs if r["workflow"] == "verify_profile" and r["profile_id"] == profile["id"])
    assert run["status"] == "failed"


async def test_discovery_confirmation_enters_as_unverified(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    profile = await _start(client, person)
    found = (await client.post("/v1/onboarding/discover", headers=person, json={"name": "Meera Iyer"})).json()
    assert found["found"] is True and found["source_title"] == "Meera Iyer"
    assert found["draft"]["claims"], "expected at least one suggested claim"

    r = await client.post(
        f"/v1/onboarding/{profile['id']}/apply-discovery", headers=person,
        json={"draft": found["draft"], "source_url": found["source_url"]},
    )
    assert r.status_code == 200, r.text
    assert all(c["status"] == "self" for c in r.json()["claims"])  # suggestion != proof

    miss = (await client.post("/v1/onboarding/discover", headers=person, json={"name": "Zzyzx Nobody"})).json()
    assert miss["found"] is False


async def test_discovery_requires_web_research_consent(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    profile = await _start(client, person, consent_web_research=False)
    found = (await client.post("/v1/onboarding/discover", headers=person, json={"name": "Meera Iyer"})).json()
    r = await client.post(
        f"/v1/onboarding/{profile['id']}/apply-discovery", headers=person,
        json={"draft": found["draft"], "source_url": found["source_url"]},
    )
    assert r.status_code == 409


async def test_unreadable_image_document_is_rejected(client, make_user):
    person, _ = await make_user()
    profile = await _start(client, person)
    r = await client.post(
        f"/v1/onboarding/{profile['id']}/documents", headers=person,
        files={"file": ("fake.png", io.BytesIO(b"this is not an image"), "image/png")},
    )
    assert r.status_code == 422
    r = await client.post(
        f"/v1/onboarding/{profile['id']}/documents", headers=person,
        files={"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert r.status_code == 415


async def test_only_owner_can_use_the_interview(client, make_user):
    owner, _ = await make_user()
    stranger, _ = await make_user()
    profile = await _start(client, owner)
    r = await client.post(f"/v1/onboarding/{profile['id']}/message", headers=stranger, json={"text": "hi"})
    assert r.status_code == 404


async def test_chat_locked_while_under_review(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    r = await client.post(f"/v1/onboarding/{profile['id']}/message", headers=person, json={"text": "I also won X"})
    assert r.status_code == 409


async def test_event_stream_auth_and_bus(client, make_user):
    assert (await client.get("/v1/agents/stream")).status_code == 401  # a session is required
    assert (await client.get("/v1/agents/stream", headers={"Authorization": "Bearer bad"})).status_code == 401
    # a token in the URL is never accepted (it would end up in logs and browser history)
    person, _ = await make_user()
    token = person["Authorization"].split()[1]
    assert (await client.get("/v1/agents/stream", params={"token": token})).status_code == 401
    # a non-admin can't open the global firehose
    assert (await client.get("/v1/agents/stream", headers=person)).status_code == 401

    q = bus.subscribe()
    ctx = await start_run("unit_test")
    await ctx.emit("Saathi", "thought", "hello")
    event = q.get_nowait()
    bus.unsubscribe(q)
    assert event["agent"] == "Saathi" and event["message"] == "hello"


async def test_agent_catalog_is_public(client):
    cat = (await client.get("/v1/agents/catalog")).json()
    assert {"Saathi", "Pariksha", "Prahari", "Lipik"} <= {a["name"] for a in cat}


async def test_flagged_document_on_a_published_profile_reaches_the_admin_queue(client, make_user, fake_wikipedia):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    # Unique per run: byte-identical files on two profiles are (rightly) flagged as duplicates by TRU-03.
    good = b"Type: award letter\nName: Meera Iyer\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\nReference: " + uuid.uuid4().hex.encode() + b"\n"
    await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("a.txt", io.BytesIO(good), "text/plain")})
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    assert (await client.get("/v1/profiles/mine", headers=person)).json()[0]["status"] == "approved"

    def mine(queue):
        return [i for i in queue if i["profile_id"] == profile["id"]]

    assert mine((await client.get("/v1/admin/review", headers=admin)).json()) == []

    # a second, mismatching document arrives AFTER publication
    bad = b"Name: Someone Else\nTitle: Padma award\nIssuer: Ministry\nYear: 2020\n"
    r = await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("b.txt", io.BytesIO(bad), "text/plain")})
    assert r.status_code == 201 and r.json()["sent_to_review"] is True
    # uploading again refreshes the same item instead of duplicating it
    await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("c.txt", io.BytesIO(bad), "text/plain")})
    items = mine((await client.get("/v1/admin/review", headers=admin)).json())
    assert len(items) == 1 and items[0]["details"]["kind"] == "document"
    assert "Document needs attention" in items[0]["reason"] and "identity_mismatch" in items[0]["details"]["flags"]

    # the reviewer resolves it; the published profile stays published
    assert (await client.post(f"/v1/admin/review/{items[0]['id']}/resolve", headers=admin, json={"note": "checked"})).status_code == 200
    assert mine((await client.get("/v1/admin/review", headers=admin)).json()) == []
    assert (await client.get("/v1/profiles/mine", headers=person)).json()[0]["status"] == "approved"
    assert (await client.post(f"/v1/admin/review/{items[0]['id']}/resolve", headers=admin, json={})).status_code == 409
    # people cannot resolve their own items
    assert (await client.post(f"/v1/admin/review/{items[0]['id']}/resolve", headers=person, json={})).status_code == 403


async def test_applicant_can_request_a_manual_review(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    profile = await _start(client, person)
    r = await client.post(f"/v1/onboarding/{profile['id']}/request-review", headers=person)
    assert r.status_code == 201 and r.json()["status"] == "queued"
    assert (await client.post(f"/v1/onboarding/{profile['id']}/request-review", headers=person)).json()["status"] == "already_in_queue"
    queue = (await client.get("/v1/admin/review", headers=admin)).json()
    assert sum(1 for i in queue if i["profile_id"] == profile["id"]) == 1


async def test_the_same_file_on_two_profiles_is_flagged_and_not_upgraded(client, make_user, fake_wikipedia):
    """TRU-03: a credential file already attached to someone else is never auto-accepted; a person looks at it."""
    doc = b"Type: award letter\nName: Meera Iyer\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\nReference: " + uuid.uuid4().hex.encode() + b"\n"
    out = []
    for _ in range(2):
        person, _ = await make_user()
        profile = await _start(client, person)
        await _interview(client, person, profile["id"])
        r = await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("a.txt", io.BytesIO(doc), "text/plain")})
        out.append(r.text)
    assert "duplicate_document" not in out[0]
    assert "duplicate_document" in out[1]


# ---------------------------------------------------------------------------------- public Agent Floor replay (spec 6.7)
async def _verify_run(client, make_user, *, demo: bool):
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Profile

    person, _ = await make_user()
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    if demo:
        async with get_sessionmaker()() as s:
            await s.execute(update(Profile).where(Profile.id == uuid.UUID(profile["id"])).values(is_demo=True))
            await s.commit()
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    return profile


async def test_the_public_replay_only_ever_shows_a_demo_profiles_run_and_carries_no_identifiers(client, make_user, fake_wikipedia):
    from sqlalchemy import select

    from app.db import get_sessionmaker
    from app.models import AgentRun, Profile

    real = await _verify_run(client, make_user, demo=False)
    demo = await _verify_run(client, make_user, demo=True)

    r = await client.get("/v1/agents/replay")  # no sign-in needed
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["events"] and {"agent", "kind", "message", "t_ms"} <= set(body["events"][0])
    assert body["demo"] is True and body["outcome"] in ("sealed", "with_reviewer", "stopped")
    assert {e["agent"] for e in body["events"]} & {"Pariksha", "Prahari"}

    # the run really belongs to a fictional demo profile, never to the real one
    async with get_sessionmaker()() as s:
        run = (await s.execute(select(AgentRun).where(AgentRun.id == uuid.UUID(body["run_id"])))).scalar_one()
        assert (await s.get(Profile, run.profile_id)).is_demo is True
        assert str(run.profile_id) == demo["id"] and str(run.profile_id) != real["id"]
    # nothing that identifies a profile, a user or an owner is in the payload
    flat = r.text
    assert demo["id"] not in flat and real["id"] not in flat and "profile_id" not in flat and "owner" not in flat
    # times are offsets from the start of the run, in order
    ts = [e["t_ms"] for e in body["events"]]
    assert ts == sorted(ts) and ts[0] == 0


async def test_with_no_demo_run_the_replay_says_so_rather_than_showing_a_real_person(client, make_user, fake_wikipedia):
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Profile

    await _verify_run(client, make_user, demo=False)
    async with get_sessionmaker()() as s:
        await s.execute(update(Profile).values(is_demo=False))  # no demo profile anywhere
        await s.commit()
    r = await client.get("/v1/agents/replay")
    assert r.status_code == 200 and r.json() == {"available": False}
