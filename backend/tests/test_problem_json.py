from app.core import ratelimit


async def test_errors_are_problem_json_with_a_detail_string(client):
    r = await client.get("/v1/verify/nope-not-a-code/zzz")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
    b = r.json()
    assert b["status"] == 404 and b["title"] == "Not Found" and isinstance(b["detail"], str) and b["type"]


async def test_validation_errors_list_fields_without_echoing_input(client):
    r = await client.post("/v1/verify/batch", json={"codes": "not-a-list-SECRETVALUE"})
    assert r.status_code == 422 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["errors"] and "SECRETVALUE" not in r.text


async def test_non_v1_errors_keep_the_default_shape(client):
    r = await client.get("/not-a-route")
    assert r.status_code == 404 and not r.headers["content-type"].startswith("application/problem+json")


async def test_api_keys_report_their_rate_limit(client, make_user):
    ratelimit.reset()
    person, _ = await make_user()
    key = (await client.post("/v1/api-keys", headers=person, json={"name": "k", "scopes": ["profiles:read"], "rate_limit_per_min": 5})).json()["key"]
    r = await client.get("/v1/profiles/mine", headers={"X-API-Key": key})
    assert r.headers["ratelimit-limit"] == "5" and int(r.headers["ratelimit-remaining"]) == 4
