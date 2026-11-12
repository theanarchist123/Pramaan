"""Batch verification (API-04): check many certificate codes in one call. Public, bounded, and each answer is exactly what /v1/verify/{code} says."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update

from app.db import get_sessionmaker
from app.models import Certificate
from tests.test_api_flow import _approved_profile_with_cert


async def test_a_batch_answers_each_code_exactly_as_the_single_check_does(client, make_user):
    _, _, _, good = await _approved_profile_with_cert(client, make_user)
    _, _, _, gone = await _approved_profile_with_cert(client, make_user)
    async with get_sessionmaker()() as s:
        await s.execute(update(Certificate).where(Certificate.code == gone["code"]).values(revoked_at=datetime.now(timezone.utc)))
        await s.commit()

    r = await client.post("/v1/verify/batch", json={"codes": [good["code"], gone["code"], "PRM-ABCDEFGHJK", good["code"].lower(), "nonsense"]})
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert [x["code"] for x in results] == [good["code"], gone["code"], "PRM-ABCDEFGHJK", "NONSENSE"]  # codes are normalised to upper case; order kept, the duplicate (any case) answered once
    by = {x["code"]: x for x in results}
    for code in (good["code"], gone["code"]):
        single = (await client.get(f"/v1/verify/{code}")).json()
        assert {k: by[code][k] for k in ("valid", "revoked", "key_id", "reason")} == {k: single[k] for k in ("valid", "revoked", "key_id", "reason")}
    assert by[good["code"]]["valid"] is True and by[gone["code"]]["revoked"] is True
    assert by["PRM-ABCDEFGHJK"]["found"] is False and by["NONSENSE"]["found"] is False and by["NONSENSE"]["valid"] is False
    assert r.json()["checked"] == 4


async def test_the_batch_is_bounded_and_rejects_junk_input(client):
    assert (await client.post("/v1/verify/batch", json={"codes": []})).status_code == 422
    assert (await client.post("/v1/verify/batch", json={"codes": [f"PRM-{i:010d}" for i in range(51)]})).status_code == 422  # at most 50
    assert (await client.post("/v1/verify/batch", json={"codes": ["x" * 200]})).status_code == 422
    assert (await client.post("/v1/verify/batch", json={})).status_code == 422
    ok = await client.post("/v1/verify/batch", json={"codes": [f"PRM-{i:010d}" for i in range(50)]})
    assert ok.status_code == 200 and len(ok.json()["results"]) == 50  # the limit itself is allowed
