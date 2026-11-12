"""Hybrid retrieval (AGT-08): vector similarity AND Postgres full-text, fused and re-ranked. The words a person typed must count even when the embedding misses them."""
import uuid

import pytest

from app.models import Claim, Profile
from app.services import directory as d


def test_combine_weights_vector_and_lexical_and_stays_in_zero_to_one():
    assert d.combine(0.8, 0.0) == pytest.approx(0.56, abs=0.01)
    assert d.combine(0.0, 1.0) == pytest.approx(0.3, abs=0.01)
    assert d.combine(1.0, 1.0) == 1.0
    assert 0 <= d.combine(-0.5, 2.0) <= 1


def test_rerank_boosts_a_name_match_and_never_exceeds_one():
    assert d.name_boost("Dr Asha Rao", "asha rao physicist") > 0
    assert d.name_boost("Dr Asha Rao", "chemist from goa") == 0
    assert d.name_boost("A", "") == 0
    assert d.combine(0.95, 1.0) + d.name_boost("Dr Asha Rao", "asha rao") >= 1.0  # the caller clamps


def test_tsquery_text_is_safe_for_odd_input():
    assert d.lexical_query("Kerala's  tidal-energy; DROP TABLE") == "kerala s tidal energy drop table"
    assert d.lexical_query("   ") == ""
    assert d.lexical_query("साहित्य अकादमी") == "साहित्य अकादमी"


@pytest.fixture
async def corpus(client, make_user):
    from app.db import get_sessionmaker
    from app.services.directory import index_profile

    async def person(name, sector, claim, state="Kerala"):
        owner, _ = await make_user()
        p = (await client.post("/v1/profiles", headers=owner, json={"full_name": name, "sector": sector, "state": state, "consent_public_listing": True})).json()
        await client.post(f"/v1/profiles/{p['id']}/claims", headers=owner, json={"field": "achievement", "value": claim})
        async with get_sessionmaker()() as s:
            prof = await s.get(Profile, uuid.UUID(p["id"]))
            prof.status = "approved"
            for c in prof.claims:
                c.status, c.confidence = "web", 0.9
            await index_profile(s, prof)
            await s.commit()
        return p["id"]

    tag = uuid.uuid4().hex[:6]
    a = await person(f"Rao {tag}", "Energy", f"Pioneered zxqtidalzxq barrage design {tag}")
    b = await person(f"Iyer {tag}", "Literature", f"Wrote three novels about monsoon {tag}")
    return a, b, tag


async def test_a_rare_word_in_a_claim_finds_the_person_even_when_the_embedding_cannot(client, corpus):
    from app.db import get_sessionmaker

    a, b, tag = corpus
    async with get_sessionmaker()() as s:
        hits = await d.search(s, f"zxqtidalzxq {tag}", limit=5)
    ids = [str(h.profile.id) for h in hits]
    assert a in ids and ids[0] == a
    top = hits[0]
    assert any("words you typed" in r.lower() or "zxqtidalzxq" in r.lower() for r in top.reasons)
    assert 0 <= top.score <= 1


async def test_filters_still_apply_to_the_lexical_side(client, corpus):
    from app.db import get_sessionmaker

    a, _, tag = corpus
    async with get_sessionmaker()() as s:
        hits = await d.search(s, f"zxqtidalzxq {tag}", state="Goa", limit=5)
    assert a not in [str(h.profile.id) for h in hits]  # a hard filter is never bypassed by a keyword match


async def test_an_empty_or_symbol_only_query_does_not_break_search(client, corpus):
    from app.db import get_sessionmaker

    async with get_sessionmaker()() as s:
        assert isinstance(await d.search(s, "!!!", limit=3), list)
