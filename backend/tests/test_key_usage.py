from app.core import ratelimit


async def _key(client, person, limit=60):
    r = await client.post("/v1/api-keys", headers=person, json={"name": "usage", "scopes": ["profiles:read"], "rate_limit_per_min": limit})
    return r.json()["id"], r.json()["key"]


async def test_usage_counts_each_call_and_the_throttled_ones(client, make_user):
    ratelimit.reset()
    person, _ = await make_user()
    kid, key = await _key(client, person, limit=2)
    for _ in range(4):
        await client.get("/v1/profiles/mine", headers={"X-API-Key": key})
    u = (await client.get(f"/v1/api-keys/{kid}/usage?days=7", headers=person)).json()
    assert len(u["days"]) == 7 and u["total"] == 4 and u["throttled"] == 2
    assert u["days"][-1]["requests"] == 4 and u["days"][0]["requests"] == 0


async def test_you_cannot_read_someone_elses_usage_and_a_key_cannot_read_usage(client, make_user):
    ratelimit.reset()
    a, _ = await make_user()
    b, _ = await make_user()
    kid, key = await _key(client, a)
    assert (await client.get(f"/v1/api-keys/{kid}/usage", headers=b)).status_code == 404
    assert (await client.get(f"/v1/api-keys/{kid}/usage", headers={"X-API-Key": key})).status_code == 403


async def test_the_admin_overview_needs_the_audit_permission(client, make_user):
    person, _ = await make_user()
    assert (await client.get("/v1/admin/api-keys/usage", headers=person)).status_code == 403
    assert (await client.get("/v1/admin/api-keys/usage")).status_code == 401
