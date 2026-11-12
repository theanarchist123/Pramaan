"""Chitrakar's brief and the frozen photo's hash are part of what the registry signs (AGT-04, spec 9.1 and 9.3)."""
import hashlib
import json

from app.agents import chitrakar
from app.core.signing import digest_payload
from tests.test_api_flow import _approved_profile_with_cert


async def test_a_new_certificate_signs_its_art_brief_and_photo_hash(client, make_user):
    _, _, profile, cert = await _approved_profile_with_cert(client, make_user)
    art = cert["payload"]["art"]
    assert art["renderer"] == chitrakar.RENDERER and art["brief_source"] in ("model", "fallback")
    brief = chitrakar.ArtBrief(**art["brief"])
    assert chitrakar.validate(brief, profile["sector"]) == [] and chitrakar.audit(brief) == []
    assert art["brief_sha256"] == hashlib.sha256(chitrakar.canonical(brief).encode()).hexdigest()
    assert art["photo"]["id"] == cert["photo_id"] and art["photo"]["sha256"] == chitrakar.photo_manifest()[cert["photo_id"]]
    # the digest covers the art: changing the brief changes the digest, so a swapped design cannot verify
    tampered = json.loads(json.dumps(cert["payload"]))
    tampered["art"]["brief"]["motifs"] = ["orbit_rings"]
    assert digest_payload(tampered) != cert["digest"]
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True


async def test_the_photo_is_chosen_before_signing_not_after(client, make_user):
    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    assert cert["photo_id"] and cert["payload"]["art"]["photo"]["id"] == cert["photo_id"]


async def test_a_paused_chitrakar_still_issues_with_the_deterministic_design(client, make_user):
    from app.db import get_sessionmaker
    from app.models import GovernedSetting
    from app.services import governed

    async with get_sessionmaker()() as s:
        s.add(GovernedSetting(key="agent_chitrakar_enabled", value={"v": False}, version=1))
        await s.commit()
    governed.clear_cache()
    try:
        _, _, _, cert = await _approved_profile_with_cert(client, make_user)
        assert cert["payload"]["art"]["brief_source"] == "fallback"
    finally:
        async with get_sessionmaker()() as s:
            await s.delete(await s.get(GovernedSetting, "agent_chitrakar_enabled"))
            await s.commit()
        governed.clear_cache()
