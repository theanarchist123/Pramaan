"""Shilpkar tier T2 (AGT-10, spec 8.4): UI views are a JSON view spec validated against a schema and drawn by the app's own interpreter. No agent-written code runs."""
import copy

import pytest

from app.services import viewspec as vs

GOOD = {
    "title": "Members per state",
    "layout": "grid2",
    "blocks": [
        {"type": "heading", "text": "Where our members are", "level": 2},
        {"type": "text", "text": "A count of approved, consenting people in each state."},
        {"type": "stat", "label": "Total members", "bind": {"endpoint": "/v1/stats/map", "path": "total"}},
        {"type": "bar_chart", "label": "By state", "bind": {"endpoint": "/v1/stats/map", "path": "by_state"}},
        {"type": "table", "columns": ["State", "Members"], "bind": {"endpoint": "/v1/stats/map", "path": "by_state"}},
    ],
}


def test_a_good_spec_validates_and_is_normalised():
    spec, problems = vs.validate(GOOD)
    assert problems == [] and spec.title == "Members per state" and len(spec.blocks) == 5


@pytest.mark.parametrize("mutate,why", [
    (lambda s: s["blocks"].append({"type": "script", "src": "x"}), "not an allowed component"),
    (lambda s: s["blocks"].append({"type": "iframe", "src": "https://evil.example"}), "not an allowed component"),
    (lambda s: s["blocks"][2]["bind"].update(endpoint="/v1/admin/overview"), "approved read endpoints"),
    (lambda s: s["blocks"][2]["bind"].update(endpoint="https://evil.example/x"), "approved read endpoints"),
    (lambda s: s["blocks"][2]["bind"].update(path="__proto__.x"), "binding path"),
    (lambda s: s["blocks"][2]["bind"].update(path="a b"), "binding path"),
    (lambda s: s["blocks"][1].update(text="<script>alert(1)</script>"), "markup"),
    (lambda s: s["blocks"][1].update(text="see https://evil.example now"), "link"),
    (lambda s: s["blocks"][1].update(text="x" * 2000), "too long"),
    (lambda s: s.update(blocks=s["blocks"] * 6), "at most"),
    (lambda s: s.update(layout="absolute"), "layout"),
    (lambda s: s.update(onload="alert(1)"), "unexpected"),
])
def test_anything_outside_the_allowlist_is_rejected(mutate, why):
    bad = copy.deepcopy(GOOD)
    mutate(bad)
    _, problems = vs.validate(bad)
    assert problems and any(why in p.lower() for p in problems), problems


def test_garbage_is_a_problem_not_an_exception():
    assert vs.validate("nope")[1] and vs.validate(None)[1] and vs.validate({"title": 5})[1]


def test_the_endpoint_allowlist_is_only_public_read_endpoints():
    assert vs.ALLOWED_ENDPOINTS and all(e.startswith("/v1/") and "/admin" not in e and "{" not in e for e in vs.ALLOWED_ENDPOINTS)


async def test_the_draft_publish_rollback_life_cycle_needs_a_second_person(client, make_user):
    a, _ = await make_user(promote_to_admin=True)
    b, _ = await make_user(promote_to_admin=True)
    r = await client.post("/v1/admin/views", headers=a, json={"request": "show members per state"})
    assert r.status_code == 201 and r.json()["status"] == "draft"
    vid, slug = r.json()["id"], r.json()["slug"]
    assert (await client.get(f"/v1/views/{slug}")).status_code == 404            # a draft is not public
    assert (await client.post(f"/v1/admin/views/{vid}/publish", headers=a)).status_code == 403  # nobody publishes their own proposal
    assert (await client.post(f"/v1/admin/views/{vid}/publish", headers=b)).status_code == 200
    pub = (await client.get(f"/v1/views/{slug}")).json()
    assert pub["spec"]["blocks"] and pub["version"] == 1
    # replace with a new draft version, publish it, then roll back to version 1
    r2 = await client.put(f"/v1/admin/views/{vid}", headers=a, json={"spec": {**GOOD, "title": "Version two"}})
    assert r2.status_code == 200
    assert (await client.post(f"/v1/admin/views/{vid}/publish", headers=b)).status_code == 200
    assert (await client.get(f"/v1/views/{slug}")).json()["spec"]["title"] == "Version two"
    assert (await client.post(f"/v1/admin/views/{vid}/rollback", headers=b)).status_code == 200
    assert (await client.get(f"/v1/views/{slug}")).json()["spec"]["title"] != "Version two"
    assert (await client.post(f"/v1/admin/views/{vid}/archive", headers=b)).status_code == 200
    assert (await client.get(f"/v1/views/{slug}")).status_code == 404


async def test_an_invalid_spec_cannot_be_saved(client, make_user):
    a, _ = await make_user(promote_to_admin=True)
    vid = (await client.post("/v1/admin/views", headers=a, json={"request": "x views"})).json()["id"]
    bad = {**GOOD, "blocks": [{"type": "script", "src": "x"}]}
    assert (await client.put(f"/v1/admin/views/{vid}", headers=a, json={"spec": bad})).status_code == 422


async def test_views_are_admin_only_to_write(client, make_user):
    person, _ = await make_user()
    assert (await client.post("/v1/admin/views", headers=person, json={"request": "show things"})).status_code == 403
    assert (await client.get("/v1/views")).status_code == 200
