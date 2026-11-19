"""Directory: indexing on approval, plain-English search, relationship graph, map counts."""

from __future__ import annotations


async def _approved(client, make_user, admin, *, name, sector, state, city="", institutions=(), claim, headline=""):
    person, _ = await make_user()
    p = (
        await client.post(
            "/v1/profiles", headers=person,
            json={"full_name": name, "sector": sector, "state": state, "city": city, "headline": headline,
                  "institutions": list(institutions), "consent_public_listing": True},
        )
    ).json()
    c = (await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": claim})).json()
    await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)
    await client.post(f"/v1/admin/claims/{c['id']}/verify", headers=admin, json={"reason": "Checked against the published honours list", "evidence_ref": "https://example.org/honours"})
    r = await client.post(f"/v1/admin/profiles/{p['id']}/status", headers=admin, json={"status": "approved"})
    assert r.status_code == 200, r.text
    return p


async def _world(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    mk = lambda **kw: _approved(client, make_user, admin, **kw)  # noqa: E731
    solar_ka = await mk(name="Tarini Solarwala", sector="Energy", state="Karnataka", city="Bengaluru",
                        institutions=["Zephyr Institute of Energy"], headline="Solar cell researcher",
                        claim="Zorbex Prize for solar photovoltaic research")
    solar_ka2 = await mk(name="Omkar Photonwale", sector="Energy", state="Karnataka", city="Mysuru",
                         institutions=["Zephyr Institute of Energy"], headline="Rooftop solar entrepreneur",
                         claim="Quillon Award for solar installation")
    solar_rj = await mk(name="Pushkar Desertsun", sector="Energy", state="Rajasthan", city="Jodhpur",
                        headline="Desert solar planner", claim="Marwar solar farm leadership award")
    dancer = await mk(name="Revati Natyakar", sector="Arts & Culture", state="Kerala", city="Kochi",
                      headline="Classical dancer", claim="Kathakali heritage performance award")
    return admin, solar_ka, solar_ka2, solar_rj, dancer


async def test_search_finds_the_right_people_with_reasons(client, make_user):
    _, ka1, ka2, rj, dancer = await _world(client, make_user)
    r = await client.post("/v1/search", json={"query": "solar energy innovators in Karnataka"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"]["state"] == "Karnataka"  # filter understood from plain English
    ids = [h["id"] for h in body["results"]]
    assert {ka1["id"], ka2["id"]} <= set(ids)
    assert rj["id"] not in ids and dancer["id"] not in ids  # filter excluded other states
    top = body["results"][0]
    assert top["score"] > 0 and any("Karnataka" in x for x in top["reasons"])
    assert body["relaxed"] is False and body["embedder"] in ("hash", "fastembed")


async def test_search_relaxes_instead_of_returning_nothing(client, make_user):
    await _world(client, make_user)
    r = (await client.post("/v1/search", json={"query": "classical dancer", "state": "Assam"})).json()
    assert r["relaxed"] is True and r["results"], "should fall back to closest people, not an empty page"


async def test_only_approved_profiles_are_searchable_and_erasure_removes_them(client, make_user):
    admin, ka1, *_ = await _world(client, make_user)
    person, _ = await make_user()
    draft = (await client.post("/v1/profiles", headers=person,
                               json={"full_name": "Unlisted Solarperson", "sector": "Energy", "state": "Karnataka",
                                     "headline": "solar", "consent_public_listing": True})).json()
    res = (await client.post("/v1/search", json={"query": "Unlisted Solarperson solar"})).json()["results"]
    assert all(h["id"] != draft["id"] for h in res)

    # the owner erases their data -> they vanish from search immediately
    owner = (await client.get("/v1/admin/profiles", headers=admin)).json()
    assert any(p["id"] == ka1["id"] for p in owner)
    # (erasure is by the owner; here the admin may also delete)
    assert (await client.delete(f"/v1/profiles/{ka1['id']}", headers=admin)).status_code == 204
    res = (await client.post("/v1/search", json={"query": "Tarini Solarwala solar cell"})).json()["results"]
    assert all(h["id"] != ka1["id"] for h in res)


async def test_graph_links_people_who_share_an_institution(client, make_user):
    _, ka1, ka2, rj, dancer = await _world(client, make_user)
    g = (await client.get("/v1/graph")).json()
    node_ids = {n["id"] for n in g["nodes"]}
    assert {ka1["id"], ka2["id"], rj["id"], dancer["id"]} <= node_ids
    alumni = [l for l in g["links"] if l["type"] == "alumni" and {l["source"], l["target"]} == {ka1["id"], ka2["id"]}]
    assert alumni and "Zephyr Institute of Energy" in alumni[0]["why"]
    # nobody is linked to the dancer by institution
    assert not [l for l in g["links"] if dancer["id"] in (l["source"], l["target"]) and l["type"] == "alumni"]


async def test_two_shared_institutions_make_one_stronger_edge_not_a_crash(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    a = await _approved(client, make_user, admin, name="Anu Doubletie", sector="Science", state="Kerala",
                        institutions=["Alpha Institute", "Beta Trust"], claim="Alpha prize for science")
    b = await _approved(client, make_user, admin, name="Binu Doubletie", sector="Law", state="Goa",
                        institutions=["alpha institute", "BETA TRUST"], claim="Beta prize for law")
    g = (await client.get("/v1/graph")).json()
    ties = [l for l in g["links"] if l["type"] == "alumni" and {l["source"], l["target"]} == {a["id"], b["id"]}]
    assert len(ties) == 1 and ties[0]["weight"] > 1.0  # case-insensitive match, merged into one edge
    why = ties[0]["why"].lower()
    assert "alpha institute" in why and "beta trust" in why


async def test_map_counts_by_state_and_sector(client, make_user):
    await _world(client, make_user)
    m = (await client.get("/v1/stats/map")).json()
    assert m["by_state"]["Karnataka"] >= 2 and m["by_state"]["Kerala"] >= 1
    assert m["by_sector"]["Energy"] >= 3
    assert any(x["state"] == "Karnataka" and x["sector"] == "Energy" and x["count"] >= 2 for x in m["by_state_sector"])
    assert m["total"] == sum(m["by_state"].values())


async def test_public_certificate_list_and_reindex_admin_only(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    assert (await client.post("/v1/admin/reindex", headers=person)).status_code == 403
    r = await client.post("/v1/admin/reindex", headers=admin)
    assert r.status_code == 200 and r.json()["profiles_indexed"] >= 0
    assert (await client.get("/v1/public/does-not-exist/certificates")).status_code == 404


async def test_review_queue_gives_the_reviewer_context(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    p = (await client.post("/v1/profiles", headers=person,
                           json={"full_name": "Review Context", "consent_public_listing": True})).json()
    await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": "Some award"})
    await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)
    item = next(i for i in (await client.get("/v1/admin/review", headers=admin)).json() if i["profile_id"] == p["id"])
    assert item["profile"]["full_name"] == "Review Context"
    assert item["profile"]["claims"][0]["value"] == "Some award"


async def test_the_profile_list_says_which_people_are_fictional_demos(client, make_user):
    """The directory labels invented people from this flag. It was missing from the list, so every demo person looked real (2026-11-19)."""
    import uuid

    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Profile

    admin, _ = await make_user(promote_to_admin=True)
    real = await _approved(client, make_user, admin, name="Real Person Listwala", sector="Law", state="Goa", claim="Goa Bar Association award")
    demo = await _approved(client, make_user, admin, name="Demo Person Listwala", sector="Law", state="Goa", claim="Goa Bar Association medal")
    async with get_sessionmaker()() as s:
        await s.execute(update(Profile).where(Profile.id == uuid.UUID(demo["id"])).values(is_demo=True))
        await s.commit()
    rows = {p["id"]: p for p in (await client.get("/v1/profiles?q=Listwala&limit=100")).json()}
    assert rows[demo["id"]]["is_demo"] is True and rows[real["id"]]["is_demo"] is False


async def test_proof_counts_only_real_members_never_the_fictional_demos(client, make_user):
    """The home page's 'N people verified' must not be padded with invented people."""
    import uuid

    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Profile

    admin, _ = await make_user(promote_to_admin=True)
    before = (await client.get("/v1/stats/proof")).json()
    real = await _approved(client, make_user, admin, name="Proof Real Prooftwala", sector="Law", state="Goa", claim="Goa Bar Council citation")
    demo = await _approved(client, make_user, admin, name="Proof Demo Prooftwala", sector="Law", state="Goa", claim="Goa Bar Council plaque")
    async with get_sessionmaker()() as s:
        await s.execute(update(Profile).where(Profile.id == uuid.UUID(demo["id"])).values(is_demo=True))
        await s.commit()
    after = (await client.get("/v1/stats/proof")).json()
    assert after["real_people"] == before["real_people"] + 1  # the demo person added nothing
    assert after["joined_this_month"] == before["joined_this_month"] + 1
    assert set(after) == {"real_people", "real_certificates", "joined_this_month"}  # counts only: no names, no personal data
    assert real["id"] != demo["id"]
