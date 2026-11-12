from app.core import ratelimit


async def test_a_test_key_reads_but_never_writes(client, make_user):
    ratelimit.reset()
    person, _ = await make_user()
    r = await client.post("/v1/api-keys", headers=person, json={"name": "ci", "scopes": ["profiles:read"], "mode": "test"})
    assert r.status_code == 201
    key = r.json()["key"]
    assert key.startswith("pk_test_")
    assert (await client.get("/v1/profiles/mine", headers={"X-API-Key": key})).status_code == 200
    assert (await client.post("/v1/profiles", headers={"X-API-Key": key}, json={"full_name": "Nope"})).status_code == 403
    assert (await client.get("/v1/api-keys", headers={"X-API-Key": key})).status_code == 403


async def test_a_test_key_cannot_be_created_with_write_scopes(client, make_user):
    person, _ = await make_user()
    for scope in ("profiles:write", "webhooks:manage"):
        r = await client.post("/v1/api-keys", headers=person, json={"name": "x", "scopes": [scope], "mode": "test"})
        assert r.status_code == 422


async def test_a_test_key_whose_row_somehow_has_write_scope_still_cannot_write(client, make_user):
    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import ApiKey

    person, _ = await make_user()
    r = await client.post("/v1/api-keys", headers=person, json={"name": "x", "scopes": ["profiles:read"], "mode": "test"})
    async with get_sessionmaker()() as s:
        await s.execute(update(ApiKey).where(ApiKey.name == "x").values(scopes=["profiles:read", "profiles:write"]))
        await s.commit()
    key = r.json()["key"]
    assert (await client.post("/v1/profiles", headers={"X-API-Key": key}, json={"full_name": "Nope"})).status_code == 403
