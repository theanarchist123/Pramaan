"""Review workbench: case locking, per-claim decisions, reason codes (spec 7.5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db import get_sessionmaker
from app.models import ReviewItem, UserRole
from tests.test_agents import _interview, _start

OK_NOTE = "Checked the original letter against the honours list"
REF = "https://example.org/honours"


async def staff(make_user, role):
    headers, user = await make_user()
    async with get_sessionmaker()() as s:
        s.add(UserRole(user_id=uuid.UUID(user["id"]), role_key=role))
        await s.commit()
    return headers, user


async def no_wikipedia(monkeypatch):
    from app.services import wikipedia

    async def nothing(name, limit=3):
        return []

    monkeypatch.setattr(wikipedia, "fetch_sources", nothing)


async def escalated_case(client, make_user, monkeypatch, owner=None):
    await no_wikipedia(monkeypatch)
    person = owner or (await make_user())[0]
    profile = await _start(client, person)
    await _interview(client, person, profile["id"])
    await client.post(f"/v1/profiles/{profile['id']}/claims", headers=person,
                      json={"field": "education", "value": "Studied marine biology at Cochin University"})
    await client.post(f"/v1/onboarding/{profile['id']}/verify", headers=person)
    admin, _ = await make_user(promote_to_admin=True)
    item = next(i for i in (await client.get("/v1/admin/review", headers=admin)).json() if i["profile_id"] == profile["id"])
    return person, profile, item


async def test_reason_codes_are_attached_to_escalations_and_listed(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    reviewer, _ = await staff(make_user, "reviewer")
    codes = (await client.get("/v1/admin/review/reason-codes", headers=reviewer)).json()
    assert item["details"]["reason_codes"] and set(item["details"]["reason_codes"]) <= set(codes)
    assert "IDENTITY_NOT_CONFIRMED" in codes and item["sla_due_at"] is not None


async def test_only_one_person_holds_a_case_and_decisions_need_the_lock(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    a, _ = await staff(make_user, "reviewer")
    b, _ = await staff(make_user, "reviewer")
    body = {"outcome": "hold", "reason_code": "EVIDENCE_INSUFFICIENT"}
    assert (await client.post(f"/v1/admin/review/{item['id']}/decide", headers=a, json=body)).status_code == 409  # no lock yet
    assert (await client.post(f"/v1/admin/review/{item['id']}/claim", headers=a)).status_code == 200
    taken = await client.post(f"/v1/admin/review/{item['id']}/claim", headers=b)
    assert taken.status_code == 409 and "Being reviewed by" in taken.text
    assert (await client.post(f"/v1/admin/review/{item['id']}/decide", headers=b, json=body)).status_code == 409
    assert (await client.post(f"/v1/admin/review/{item['id']}/decide", headers=a, json=body)).status_code == 200
    await client.post(f"/v1/admin/review/{item['id']}/release", headers=a)
    assert (await client.post(f"/v1/admin/review/{item['id']}/claim", headers=b)).status_code == 200  # free again


async def test_an_expired_lock_can_be_taken_over(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    a, _ = await staff(make_user, "reviewer")
    b, _ = await staff(make_user, "reviewer")
    await client.post(f"/v1/admin/review/{item['id']}/claim", headers=a)
    async with get_sessionmaker()() as s:
        row = await s.get(ReviewItem, uuid.UUID(item["id"]))
        row.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        await s.commit()
    assert (await client.post(f"/v1/admin/review/{item['id']}/claim", headers=b)).status_code == 200


async def test_decisions_are_per_claim_with_codes_notes_and_evidence(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    reviewer, _ = await staff(make_user, "reviewer")
    await client.post(f"/v1/admin/review/{item['id']}/claim", headers=reviewer)
    claims = (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"]
    plain = next(c for c in claims if c["field"] != "award")
    url = f"/v1/admin/review/{item['id']}/decide"

    def post(**kw):
        return client.post(url, headers=reviewer, json={"outcome": "hold", "reason_code": "EVIDENCE_CHECKED", **kw})

    assert (await post(reason_code="MADE_UP")).status_code == 422
    thin = {"claim_id": plain["id"], "decision": "verify", "reason_code": "EVIDENCE_CHECKED", "note": "ok"}
    assert (await post(claims=[thin])).status_code == 422  # a verification needs a real note and an evidence reference
    good = {**thin, "note": OK_NOTE, "evidence_ref": REF}
    ok = await post(claims=[good])
    assert ok.status_code == 200 and ok.json()["decisions"] == 2  # the claim and the case

    now = {c["id"]: c for c in (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"]}
    assert now[plain["id"]]["status"] == "human"  # never "document"
    log = (await client.get(f"/v1/admin/review/{item['id']}/decisions", headers=reviewer)).json()
    assert {d["decision"] for d in log} == {"verify", "hold"} and all(d["reason_code"] for d in log)


async def test_awards_need_a_senior_verifier_and_approval_closes_the_case(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    reviewer, _ = await staff(make_user, "reviewer")
    senior, _ = await staff(make_user, "senior_verifier")
    claims = (await client.get("/v1/profiles/mine", headers=person)).json()[0]["claims"]
    award = next(c for c in claims if c["field"] == "award")
    verify = {"claim_id": award["id"], "decision": "verify", "reason_code": "EVIDENCE_CHECKED", "note": OK_NOTE, "evidence_ref": REF}
    url = f"/v1/admin/review/{item['id']}/decide"
    await client.post(f"/v1/admin/review/{item['id']}/claim", headers=reviewer)
    held = await client.post(url, headers=reviewer, json={"claims": [verify], "outcome": "hold", "reason_code": "EVIDENCE_CHECKED"})
    assert held.status_code == 403
    await client.post(f"/v1/admin/review/{item['id']}/release", headers=reviewer)

    await client.post(f"/v1/admin/review/{item['id']}/claim", headers=senior)
    done = await client.post(url, headers=senior, json={"claims": [verify], "outcome": "approve", "reason_code": "EVIDENCE_CHECKED", "note": OK_NOTE})
    assert done.status_code == 200 and done.json()["case_status"] == "approved"
    mine = (await client.get("/v1/profiles/mine", headers=person)).json()[0]
    assert mine["status"] == "approved" and mine["decision_basis"] == "reviewer"
    assert (await client.post(url, headers=senior, json={"outcome": "hold", "reason_code": "OTHER"})).status_code == 409  # closed


async def test_nobody_decides_their_own_case(client, make_user, monkeypatch):
    me, me_user = await make_user()
    async with get_sessionmaker()() as s:
        s.add(UserRole(user_id=uuid.UUID(me_user["id"]), role_key="reviewer"))
        await s.commit()
    person, profile, item = await escalated_case(client, make_user, monkeypatch, owner=me)
    assert (await client.post(f"/v1/admin/review/{item['id']}/claim", headers=me)).status_code == 403


# ---------------------------------------------------------------------------------- case detail for the workbench page
async def test_the_case_detail_shows_claims_evidence_and_document_flags_but_never_file_contents(client, make_user, monkeypatch):
    import io

    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    doc = b"Type: award letter\nName: Meera Iyer\nTitle: Sagar Samman award\nIssuer: Ministry of Earth Sciences\nYear: 2024\n"
    await client.post(f"/v1/onboarding/{profile['id']}/documents", headers=person, files={"file": ("letter.txt", io.BytesIO(doc), "text/plain")})
    reviewer, _ = await staff(make_user, "reviewer")
    r = await client.get(f"/v1/admin/review/{item['id']}", headers=reviewer)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["item"]["id"] == item["id"] and d["profile"]["full_name"] and d["profile"]["claims"]
    assert d["documents"] and d["documents"][0]["filename"] == "letter.txt"
    assert {"match_score", "flags", "flag_notes"} <= set(d["documents"][0])
    assert "path" not in d["documents"][0] and "sha256" not in d["documents"][0]  # no storage path, no raw hash
    assert d["permissions"]["can_decide"] is False  # a reviewer with the lock is needed; the page greys the form out until it is taken
    assert (await client.get(f"/v1/admin/review/{uuid.uuid4()}", headers=reviewer)).status_code == 404
    member, _ = await make_user()
    assert (await client.get(f"/v1/admin/review/{item['id']}", headers=member)).status_code in (401, 403)


async def test_the_namesake_panel_lists_wikidata_candidates_next_to_the_confirmed_item(client, make_user, monkeypatch):
    from app.services import wikidata

    async def fake(name, limit=5):
        return [{"qid": "Q1", "label": name, "description": "a different person"}]

    monkeypatch.setattr(wikidata, "candidates", fake)
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    reviewer, _ = await staff(make_user, "reviewer")
    r = (await client.get(f"/v1/admin/review/{item['id']}/namesakes", headers=reviewer)).json()
    assert r["candidates"][0]["qid"] == "Q1" and r["confirmed_qid"] in ("", None)


# ---------------------------------------------------------------------------------- command centre tiles
async def test_the_overview_reports_real_counts_and_hides_sections_the_role_cannot_see(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    reviewer, _ = await staff(make_user, "reviewer")
    auditor, _ = await staff(make_user, "auditor")

    r = (await client.get("/v1/admin/overview", headers=reviewer)).json()
    assert r["queue"]["open"] >= 1 and r["queue"]["overdue"] <= r["queue"]["open"]
    assert r["queue"]["oldest_hours"] is not None and r["queue"]["oldest_hours"] >= 0
    assert sum(r["queue"]["by_reason_code"].values()) >= 1
    assert "approvals" not in r and "agents" not in r  # a reviewer is not shown what an auditor sees

    a = (await client.get("/v1/admin/overview", headers=auditor)).json()
    assert {"pending", "oldest_hours"} <= set(a["approvals"]) and {"calls_24h", "failed_24h"} <= set(a["agents"])
    assert a["registry"]["profiles"]["approved"] >= 0 and a["registry"]["certificates"] >= 0

    # taking the case moves it from "unassigned" to "held"
    before = r["queue"]["unassigned"]
    await client.post(f"/v1/admin/review/{item['id']}/claim", headers=reviewer)
    after = (await client.get("/v1/admin/overview", headers=reviewer)).json()["queue"]["unassigned"]
    assert after == before - 1

    member, _ = await make_user()
    assert (await client.get("/v1/admin/overview", headers=member)).status_code in (401, 403)
