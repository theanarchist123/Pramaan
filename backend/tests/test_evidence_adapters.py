import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest

from app.evidence import base, openalex
from app.evidence.base import CircuitBreaker, EvidenceDoc, gather
from app.services.wikipedia import Source


def doc(**kw):
    d = dict(title="T", url="https://x.example/a", text="some text", source="test", reliability=0.8)
    d.update(kw)
    return EvidenceDoc(**d)


def test_a_doc_is_a_source_with_provenance_and_a_content_hash():
    d = doc(text="Asha Rao won the Sahitya Akademi Award in 2019.").stamped()
    assert isinstance(d, Source) and d.content_hash == hashlib.sha256(d.text.encode()).hexdigest()
    assert d.retrieved_at.endswith("+00:00") or d.retrieved_at.endswith("Z")
    assert 0 < d.reliability <= 1


def test_asdict_round_trips_through_the_workflow_state():
    import dataclasses

    d = doc().stamped()
    assert EvidenceDoc(**dataclasses.asdict(d)) == d


class _Adapter:
    def __init__(self, name, docs=None, boom=None, delay=0.0, reliability=0.8):
        self.name, self.reliability, self.docs, self.boom, self.delay = name, reliability, docs or [], boom, delay
        self.calls = 0

    async def search(self, person):
        import asyncio

        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.boom:
            raise self.boom
        return list(self.docs)


PERSON = SimpleNamespace(name="Asha Rao", qid=None, institutions=[])


async def test_gather_merges_adapters_and_a_failing_one_never_breaks_the_rest():
    good = _Adapter("good", [doc(url="https://a.example/1")])
    bad = _Adapter("bad", boom=httpx.ConnectError("down"))
    out = await gather(PERSON, [good, bad], breaker=CircuitBreaker())
    assert [d.url for d in out] == ["https://a.example/1"] and out[0].retrieved_at and out[0].content_hash


async def test_a_slow_adapter_is_cut_off_by_its_timeout():
    slow = _Adapter("slow", [doc()], delay=2.0)
    out = await gather(PERSON, [slow], breaker=CircuitBreaker(), timeout=0.05)
    assert out == []


async def test_the_circuit_breaker_stops_calling_an_adapter_that_keeps_failing():
    bad = _Adapter("bad", boom=RuntimeError("nope"))
    br = CircuitBreaker(threshold=3, cooldown=60)
    for _ in range(6):
        await gather(PERSON, [bad], breaker=br)
    assert bad.calls == 3  # open after three failures; the other three were skipped


async def test_documents_are_deduplicated_by_url_and_capped_in_number():
    a = _Adapter("a", [doc(url="https://dup.example/1"), doc(url="https://dup.example/1")])
    b = _Adapter("b", [doc(url=f"https://b.example/{i}") for i in range(30)])
    out = await gather(PERSON, [a, b], breaker=CircuitBreaker(), max_docs=10)
    assert len(out) == 10 and len({d.url for d in out}) == 10


# ---- OpenAlex (open API, keyless allowed; official docs read 2026-11-12) --------------------------------

AUTHORS = {"results": [
    {"id": "https://openalex.org/A1", "display_name": "Asha Rao", "last_known_institutions": [{"display_name": "Indian Institute of Science"}]},
    {"id": "https://openalex.org/A2", "display_name": "Asha Rao", "last_known_institutions": [{"display_name": "University of Nowhere"}]},
]}
WORKS = {"results": [
    {"display_name": "Tidal energy in coastal Kerala", "publication_year": 2021, "doi": "https://doi.org/10.1/abc",
     "authorships": [{"author": {"display_name": "Asha Rao"}}, {"author": {"display_name": "Raj Kumar"}}]},
]}


def transport():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "api.openalex.org"
        if req.url.path == "/authors":
            return httpx.Response(200, json=AUTHORS)
        if req.url.path == "/works":
            assert "A1" in str(req.url)  # only the author whose institution matched
            return httpx.Response(200, json=WORKS)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


async def test_openalex_needs_a_matching_institution_so_a_namesake_cannot_vouch():
    ad = openalex.OpenAlexAdapter(transport=transport())
    docs = await ad.search(SimpleNamespace(name="Asha Rao", qid=None, institutions=["Indian Institute of Science, Bangalore"]))
    assert len(docs) == 1 and "Tidal energy in coastal Kerala" in docs[0].text and "Raj Kumar" in docs[0].text
    assert docs[0].source == "openalex" and docs[0].reliability < 0.9 and docs[0].url == "https://doi.org/10.1/abc"
    # With no institution to compare, it declines to guess.
    assert await ad.search(SimpleNamespace(name="Asha Rao", qid=None, institutions=[])) == []


async def test_openalex_failures_are_empty_not_errors():
    ad = openalex.OpenAlexAdapter(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await ad.search(SimpleNamespace(name="Asha Rao", qid=None, institutions=["Indian Institute of Science"])) == []


def test_default_adapter_set_is_wikipedia_then_wikidata_then_openalex(monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "openalex_enabled", True)
    names = [a.name for a in base.default_adapters()]
    assert names == ["wikipedia", "wikidata", "openalex"]
