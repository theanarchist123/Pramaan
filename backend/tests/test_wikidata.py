"""Wikidata evidence: parsing of the real response shapes, humans only, and it plugs into Pariksha's quote check."""

from __future__ import annotations

import pytest

from app.agents.textutil import quote_in_source
from app.config import get_settings
from app.services import wikidata


def claim(value):
    return {"mainsnak": {"datavalue": {"value": value}}}


ENTITIES = {
    "Q1": {"labels": {"en": {"value": "Meera Iyer"}}, "descriptions": {"en": {"value": "Indian marine scientist"}},
           "claims": {"P31": [claim({"id": "Q5"})], "P569": [claim({"time": "+1975-03-02T00:00:00Z"})],
                      "P166": [claim({"id": "Q10"}), claim({"id": "Q11"})], "P69": [claim({"id": "Q12"})]}},
    "Q2": {"labels": {"en": {"value": "Meera Iyer"}}, "descriptions": {"en": {"value": "a ship"}},
           "claims": {"P31": [claim({"id": "Q811979"})]}},  # not a human: must be ignored
}
LABELS = {"Q10": "Padma Shri", "Q11": "Sagar Samman", "Q12": "Cochin University"}


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(get_settings(), "wikidata_enabled", True)
    calls = []

    async def _get(params):
        calls.append(params["action"])
        if params["action"] == "wbsearchentities":
            return {"search": [{"id": "Q1"}, {"id": "Q2"}]}
        if "labels|descriptions|claims" in params["props"]:
            return {"entities": ENTITIES}
        return {"entities": {q: {"labels": {"en": {"value": LABELS[q]}}} for q in params["ids"].split("|")}}

    monkeypatch.setattr(wikidata, "_get", _get)
    return calls


async def test_a_person_becomes_quotable_evidence_and_non_humans_are_dropped(fake):
    sources = await wikidata.fetch_sources("Meera Iyer")
    assert len(sources) == 1 and sources[0].url == "https://www.wikidata.org/wiki/Q1"
    text = sources[0].text
    assert "Born: 1975." in text and "Awards: Padma Shri; Sagar Samman." in text and "Educated at: Cochin University." in text
    assert quote_in_source("Awards: Padma Shri; Sagar Samman.", text)  # Pariksha's verbatim-quote rule can cite it


async def test_it_can_be_switched_off_and_failures_mean_no_evidence(monkeypatch):
    import httpx

    monkeypatch.setattr(get_settings(), "wikidata_enabled", False)
    assert await wikidata.fetch_sources("Anyone") == []
    monkeypatch.setattr(get_settings(), "wikidata_enabled", True)

    async def boom(params):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(wikidata, "_get", boom)
    assert await wikidata.fetch_sources("Anyone") == []
