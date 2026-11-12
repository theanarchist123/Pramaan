from types import SimpleNamespace

from app.services.onboarding import PLACEHOLDER_NAME, coverage


def P(**kw):
    base = dict(full_name=PLACEHOLDER_NAME, sector="", state="", headline="", bio="", claims=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_an_empty_draft_is_not_ready_and_lists_what_is_missing():
    c = coverage(P())
    assert c["score"] == 0 and not c["ready"] and "your name" in c["missing"]


def test_ready_needs_name_field_state_and_a_claim_whatever_the_model_says():
    c = coverage(P(full_name="Asha Rao", sector="Science", state="Kerala"))
    assert not c["ready"] and "at least one achievement" in c["missing"]
    c = coverage(P(full_name="Asha Rao", sector="Science", state="Kerala", claims=[object()]))
    assert c["ready"] and 0.6 < c["score"] < 1


def test_full_draft_scores_one():
    assert coverage(P(full_name="A B", sector="S", state="K", headline="h", bio="b", claims=[1]))["score"] == 1.0


async def test_the_turn_reports_coverage(client, make_user):
    person, _ = await make_user()
    r = await client.post("/v1/onboarding/start", headers=person, json={"consent_public_listing": True, "consent_web_research": True})
    pid = r.json()["profile"]["id"]
    t = await client.post(f"/v1/onboarding/{pid}/message", headers=person, json={"text": "I am Dr. Asha Rao, a physicist from Kerala"})
    assert t.status_code == 200 and "score" in t.json()["coverage"]
