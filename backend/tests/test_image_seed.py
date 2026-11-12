"""Automatic photo seeding: it picks and approves photos itself, safely and within Unsplash's hourly limit. All tests use fakes: no Unsplash call."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select

from app.db import get_sessionmaker
from app.models import ImageAsset
from app.services import image_seed as seed


def cand(n: int, alt: str = "wind turbines on a hill", url: str | None = None) -> dict:
    return {
        "unsplash_id": f"ph{n}", "url_raw": url or f"https://images.unsplash.com/photo-{n}?ixid=x", "width": 3000, "height": 2000, "blur_hash": "",
        "dominant_color": "#336699", "alt_text": alt, "photographer_name": f"P{n}", "photographer_url": f"https://unsplash.com/@p{n}",
        "photo_url": f"https://unsplash.com/photos/ph{n}", "download_location": f"https://api.unsplash.com/photos/ph{n}/download",
    }


class Fakes:
    def __init__(self, results: dict[str, list[dict]] | None = None):
        self.results, self.searches, self.pings = results or {}, [], []

    async def search(self, query: str):
        self.searches.append(query)
        return self.results.get(query, [cand(hash(query) % 10_000 + i) for i in range(6)])

    async def ping(self, url: str):
        self.pings.append(url)


@pytest.fixture(autouse=True)
async def _clean_images(app_instance):
    async with get_sessionmaker()() as s:
        await s.execute(delete(ImageAsset))
        await s.commit()
    yield
    async with get_sessionmaker()() as s:
        await s.execute(delete(ImageAsset))
        await s.commit()


async def _run(f: Fakes, **kw):
    async with get_sessionmaker()() as s:
        report = await seed.seed_images(s, search=f.search, ping=f.ping, **kw)
        await s.commit()
        return report


async def test_it_fills_a_tile_and_a_cover_for_every_field_by_itself():
    f = Fakes()
    r = await _run(f, budget=200)
    async with get_sessionmaker()() as s:
        rows = (await s.execute(select(ImageAsset))).scalars().all()
    assert len(rows) == 28 and len({x.unsplash_id for x in rows}) == 28  # 14 fields x 2 slots, never the same photo twice
    assert {(x.sector, x.purpose) for x in rows} == {(sec, p) for sec in seed.SECTOR_QUERIES for p in ("tile", "cover")}
    assert all(x.url_raw.startswith("https://images.unsplash.com/") and x.active and x.source == "unsplash_api" for x in rows)
    assert len(f.pings) == 28 and r["approved"] == 28  # Unsplash's download ping, once per approved photo


async def test_it_never_picks_a_photo_whose_description_mentions_people():
    bad = ["a smiling woman in a field", "Portrait of a farmer", "two men working", "children playing", "a doctor with a patient", "students in class", "team of players"]
    results = {q: [cand(i, alt=a) for i, a in enumerate(bad)] + [cand(900 + hash(q) % 50, alt="empty terraced hillside at dawn")] for q in seed.all_queries()}
    f = Fakes(results)
    await _run(f, budget=500)
    async with get_sessionmaker()() as s:
        rows = (await s.execute(select(ImageAsset))).scalars().all()
    assert rows and all(not seed.mentions_people(x.alt_text) for x in rows)
    assert all("terraced" in x.alt_text for x in rows)


def test_the_people_filter_is_strict_but_not_silly():
    for text in ("a woman reading", "Portrait of a man", "kids at school", "a crowd at a stadium", "hands holding a seedling", "surgeon in theatre", "gold and blue hindu deity statue", "a statue of a goddess"):
        assert seed.mentions_people(text), text
    for text in ("wind turbines on a hill", "an empty classroom", "stack of old books", "the manhattan skyline", "a mantis on a leaf", ""):
        assert not seed.mentions_people(text), text  # words inside other words do not count


async def test_it_leaves_slots_you_already_filled_alone_and_is_safe_to_run_twice():
    async with get_sessionmaker()() as s:
        s.add(ImageAsset(unsplash_id="mine", sector="Agriculture", purpose="cover", url_raw="https://images.unsplash.com/mine", photographer_name="Me",
                         photographer_url="https://unsplash.com/@me", photo_url="https://unsplash.com/photos/mine", download_location="x", active=True))
        await s.commit()
    f = Fakes()
    first = await _run(f, budget=200)
    assert first["approved"] == 27  # 28 slots minus the one already filled
    second = await _run(Fakes(), budget=200)
    assert second["approved"] == 0 and second["already_filled"] == 28
    async with get_sessionmaker()() as s:
        mine = (await s.execute(select(ImageAsset).where(ImageAsset.unsplash_id == "mine"))).scalar_one()
    assert mine.active and mine.photographer_name == "Me"  # untouched


async def test_it_stops_before_the_hourly_limit_and_says_so_so_a_later_run_can_finish():
    f = Fakes()
    r = await _run(f, budget=20)
    assert r["requests_used"] <= 20 and r["stopped_early"] is True and 0 < r["approved"] < 28
    assert len(f.searches) + len(f.pings) == r["requests_used"]
    more = await _run(Fakes(), budget=200)
    assert more["approved"] == 28 - r["approved"]  # picks up where it left off


async def test_a_dry_run_chooses_and_reports_but_approves_nothing_and_pings_nothing():
    f = Fakes()
    r = await _run(f, budget=200, dry_run=True)
    assert r["approved"] == 0 and len(r["would_approve"]) == 28 and f.pings == []
    async with get_sessionmaker()() as s:
        assert (await s.execute(select(ImageAsset))).first() is None


async def test_searches_are_cached_so_a_trial_run_does_not_spend_the_quota_twice():
    cache: dict = {}
    f1 = Fakes()
    await _run(f1, budget=200, dry_run=True, cache=cache)
    assert f1.searches and cache
    f2 = Fakes()
    r = await _run(f2, budget=200, cache=cache)
    assert f2.searches == []  # everything came from the cache
    assert r["approved"] == 28 and r["requests_used"] == 28  # only the download pings cost anything


async def test_only_real_unsplash_hotlinks_are_accepted():
    results = {q: [cand(1, url="https://evil.example/photo.jpg"), cand(2, url="http://images.unsplash.com/insecure")] for q in seed.all_queries()}
    r = await _run(Fakes(results), budget=500)
    assert r["approved"] == 0
