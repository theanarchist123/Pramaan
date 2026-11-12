"""Setu (AGT-03): a model PROPOSES connections between people; a deterministic validator accepts one only if the person's own words contain a verbatim
span that names the other person. A model can never invent a connection."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select

from app.agents import setu
from app.agents.schemas import SetuEdgeProposal
from app.db import get_sessionmaker
from app.models import Profile, SetuEdge

RAJ = setu.Candidate(id=uuid.uuid4(), name="Dr. Raj Kumar")
MEERA = setu.Candidate(id=uuid.uuid4(), name="Meera Iyer")
CORPUS = "Co-authored a paper on tidal energy with Dr. Raj Kumar in 2021.\nServed on the board of the Coastal Trust.\nLikes long walks."


def check(**kw):
    base = dict(other_name="Dr. Raj Kumar", kind="co_author", span="Co-authored a paper on tidal energy with Dr. Raj Kumar in 2021")
    base.update(kw)
    return setu.validate(SetuEdgeProposal(**base), self_name="Ananya Rao", corpus=CORPUS, candidates=[RAJ, MEERA])


def test_a_grounded_proposal_is_accepted():
    who, why = check()
    assert who == RAJ and why == ""


def test_a_span_that_is_not_in_the_persons_own_words_is_rejected():
    who, why = check(span="Worked closely with Dr. Raj Kumar on offshore wind projects")  # plausible, but never said
    assert who is None and "not found" in why


def test_a_span_that_does_not_name_the_other_person_is_rejected():
    who, why = check(span="Served on the board of the Coastal Trust", kind="board")  # real text, but it does not say who with
    assert who is None and "does not name" in why


def test_an_unknown_or_self_or_ambiguous_person_is_rejected():
    assert check(other_name="Dr. Someone Else")[0] is None
    assert setu.validate(SetuEdgeProposal(other_name="Ananya Rao", kind="co_author", span="Co-authored a paper on tidal energy with Dr. Raj Kumar in 2021"),
                         self_name="Ananya Rao", corpus=CORPUS, candidates=[RAJ])[0] is None  # no edge to yourself
    twin = setu.Candidate(id=uuid.uuid4(), name="Dr. Raj Kumar")
    assert setu.validate(SetuEdgeProposal(other_name="Dr. Raj Kumar", kind="co_author", span="Co-authored a paper on tidal energy with Dr. Raj Kumar in 2021"),
                         self_name="Ananya Rao", corpus=CORPUS, candidates=[RAJ, twin])[0] is None  # two people with that name: refuse to guess


def test_a_made_up_kind_or_a_tiny_span_is_rejected():
    assert check(span="Dr. Raj Kumar")[0] is None  # too short to be evidence
    try:
        SetuEdgeProposal(other_name="Dr. Raj Kumar", kind="friends", span="Co-authored a paper on tidal energy with Dr. Raj Kumar in 2021")
        raise AssertionError("an unknown kind must not be accepted")
    except ValueError:
        pass


async def test_the_run_stores_only_validated_edges_and_the_graph_shows_them_with_their_evidence(client, make_user):
    from app.agents.events import start_run

    async with get_sessionmaker()() as s:
        await s.execute(delete(SetuEdge))
        await s.commit()

    async def approved(name, claim=None):
        person, _ = await make_user()
        p = (await client.post("/v1/profiles", headers=person, json={"full_name": name, "sector": "Science", "consent_public_listing": True})).json()
        if claim:
            await client.post(f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "achievement", "value": claim})
        async with get_sessionmaker()() as s:
            prof = await s.get(Profile, uuid.UUID(p["id"]))
            prof.status = "approved"
            await s.commit()
        return p

    tag = uuid.uuid4().hex[:5]
    raj = await approved(f"Dr. Raj Kumar {tag}")
    ananya = await approved(f"Ananya Rao {tag}", f"Co-authored a paper on tidal energy with Dr. Raj Kumar {tag} in 2021")
    await approved(f"Loner {tag}", "Likes long walks and quiet mornings")

    async with get_sessionmaker()() as s:
        ctx = await start_run("setu_test")
        report = await setu.run(ctx, s, limit=100000)
        await s.commit()
    assert report["accepted"] >= 1 and report["rejected"] >= 0

    graph = (await client.get("/v1/graph")).json()
    links = [l for l in graph["links"] if l["type"] == "collab" and {l["source"], l["target"]} == {raj["id"], ananya["id"]}]
    assert len(links) == 1 and "tidal energy" in links[0]["why"] and "co-author" in links[0]["why"].lower()  # the evidence travels with the edge

    async with get_sessionmaker()() as s:  # running it again must not duplicate
        await setu.run(await start_run("setu_test"), s, limit=100000)
        await s.commit()
        pair = [e for e in (await s.execute(select(SetuEdge))).scalars().all() if {str(e.a_id), str(e.b_id)} == {raj['id'], ananya['id']}]
        assert len(pair) == 1  # still exactly one stored edge after a second run
    again = [l for l in (await client.get("/v1/graph")).json()["links"] if l["type"] == "collab" and {l["source"], l["target"]} == {raj["id"], ananya["id"]}]
    assert len(again) == 1
