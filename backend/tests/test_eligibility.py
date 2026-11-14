"""Who qualifies for the registry: deterministic rules (invariant I-1: code decides, never a model)."""
from types import SimpleNamespace as C

from app.services.eligibility import MIN_MET, assess


def claim(field: str, status: str):
    return C(field=field, status=status)


def test_nothing_verified_meets_nothing():
    r = assess([claim("award", "self"), claim("position", "self")])
    assert r["met_count"] == 0 and r["eligible"] is False
    assert all(not c["met"] for c in r["criteria"])


def test_a_verified_award_alone_is_not_enough():
    r = assess([claim("award", "document")])
    ids = {c["id"]: c["met"] for c in r["criteria"]}
    assert ids["recognition"] is True
    assert r["met_count"] == 1 and r["eligible"] is False


def test_recognition_plus_standing_plus_depth_qualifies():
    r = assess([claim("award", "document"), claim("position", "web"), claim("publication", "human")])
    assert r["met_count"] >= MIN_MET and r["eligible"] is True


def test_self_declared_never_counts_even_in_bulk():
    r = assess([claim("award", "self")] * 5 + [claim("publication", "self")] * 5)
    assert r["eligible"] is False and r["met_count"] == 0


def test_each_criterion_explains_itself_in_plain_words():
    r = assess([])
    assert len(r["criteria"]) >= 3
    assert all(c["label"] and c["how"] for c in r["criteria"])
