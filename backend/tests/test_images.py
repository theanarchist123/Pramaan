"""Unsplash API imagery (spec 4.9): hotlinked, attributed, human-curated, key never exposed."""

from __future__ import annotations

import uuid

import pytest

from app.config import get_settings
from app.services import images as svc

PHOTO = {
    "id": "abc123", "width": 4000, "height": 2667, "blur_hash": "LKO2?U%2Tw=w", "color": "#264d59",
    "alt_description": "wind turbines at dusk",
    "urls": {"raw": "https://images.unsplash.com/photo-abc123?ixid=MnwxMjA3fDB8MXxzZWFyY2h8MXx8&ixlib=rb-4.0.3"},
    "user": {"name": "Asha Rao", "links": {"html": "https://unsplash.com/@asharao"}},
    "links": {"html": "https://unsplash.com/photos/abc123", "download_location": "https://api.unsplash.com/photos/abc123/download?ixid=xyz"},
}


@pytest.fixture
def fake_unsplash(monkeypatch):
    calls = []

    async def _get(path, params=None):
        calls.append((path, params))
        if path == "/search/photos":
            return {"results": [PHOTO]}
        return {"url": "https://images.unsplash.com/photo-abc123"}  # the download ping

    monkeypatch.setattr(svc, "_get", _get)
    monkeypatch.setattr(get_settings(), "unsplash_access_key", "test-key")
    return calls


async def test_search_asks_for_safe_landscape_photos_and_returns_candidates(client, make_user, fake_unsplash):
    admin, _ = await make_user(promote_to_admin=True)
    person, _ = await make_user()
    assert (await client.get("/v1/admin/images/candidates", headers=person, params={"q": "wind turbines"})).status_code == 403
    r = await client.get("/v1/admin/images/candidates", headers=admin, params={"q": "wind turbines", "color": "teal"})
    assert r.status_code == 200 and r.json()[0]["unsplash_id"] == "abc123"
    path, params = fake_unsplash[0]
    assert params["content_filter"] == "high" and params["orientation"] == "landscape" and params["color"] == "teal"
    assert not any("download" in p for p, _ in fake_unsplash)  # searching never pings the download endpoint


async def test_approving_pings_download_once_and_the_public_set_is_attributed_and_hotlinked(client, make_user, fake_unsplash):
    admin, _ = await make_user(promote_to_admin=True)
    cand = (await client.get("/v1/admin/images/candidates", headers=admin, params={"q": "wind turbines"})).json()[0]
    ok = await client.post("/v1/admin/images/approve", headers=admin, json={"candidate": cand, "sector": "Energy", "purpose": "tile"})
    assert ok.status_code == 201
    assert [p for p, _ in fake_unsplash if "download" in p] == ["https://api.unsplash.com/photos/abc123/download?ixid=xyz"]
    again = await client.post("/v1/admin/images/approve", headers=admin, json={"candidate": cand, "sector": "Energy", "purpose": "cover"})
    assert again.status_code == 201 and len([p for p, _ in fake_unsplash if "download" in p]) == 1  # not pinged twice

    shown = (await client.get("/v1/images/sector/Energy")).json()  # public: no auth, no key
    img = next(i for i in shown if i["id"] == ok.json()["id"])
    assert img["url_raw"].startswith("https://images.unsplash.com/") and "ixid=" in img["url_raw"]  # hotlink, ixid kept
    att = img["attribution"]
    assert att["photographer"] == "Asha Rao"
    assert "utm_source=pramaan" in att["photographer_url"] and "utm_medium=referral" in att["photo_url"]
    assert "test-key" not in str(img) and "download_location" not in img  # the key and the ping URL stay on the server

    assert (await client.get("/v1/images/sector/Atlantis")).status_code == 404
    gone = await client.post(f"/v1/admin/images/{img['id']}/deactivate", headers=admin)
    assert gone.status_code == 200
    assert img["id"] not in {i["id"] for i in (await client.get("/v1/images/sector/Energy")).json()}


async def test_only_unsplash_hotlinks_and_known_sectors_and_purposes_are_accepted(client, make_user, fake_unsplash):
    admin, _ = await make_user(promote_to_admin=True)
    cand = {"unsplash_id": "x1", "url_raw": "https://evil.example/photo.jpg", "photographer_name": "n",
            "photographer_url": "https://unsplash.com/@n", "photo_url": "https://unsplash.com/photos/x1", "download_location": "https://api.unsplash.com/photos/x1/download"}
    post = lambda c, s="Energy", p="tile": client.post("/v1/admin/images/approve", headers=admin, json={"candidate": c, "sector": s, "purpose": p})  # noqa: E731
    assert (await post(cand)).status_code == 422  # not an Unsplash hotlink
    good = {**cand, "url_raw": "https://images.unsplash.com/photo-x1?ixid=1"}
    assert (await post(good, s="Astrology")).status_code == 422
    assert (await post(good, p="certificate")).status_code == 422  # certificates only ever use the frozen local photos
    assert (await post({"unsplash_id": "x"})).status_code == 422  # incomplete


async def test_without_a_key_the_public_read_still_works_and_curation_says_why(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "unsplash_access_key", "")
    admin, _ = await make_user(promote_to_admin=True)
    assert (await client.get("/v1/images/sector/Science")).status_code == 200  # reads our own table
    r = await client.get("/v1/admin/images/candidates", headers=admin, params={"q": "telescope"})
    assert r.status_code == 503 and "UNSPLASH_ACCESS_KEY" in r.text


def test_attribution_links_carry_utm_parameters():
    assert svc.utm("https://unsplash.com/@a") == "https://unsplash.com/@a?utm_source=pramaan&utm_medium=referral"
    assert svc.utm("https://unsplash.com/p?x=1").endswith("&utm_source=pramaan&utm_medium=referral")


async def test_a_failed_download_ping_does_not_block_approval(client, make_user, monkeypatch):
    import httpx

    async def flaky(path, params=None):
        if path == "/search/photos":
            return {"results": [{**PHOTO, "id": f"f{uuid.uuid4().hex[:6]}"}]}
        raise httpx.ConnectError("down")

    monkeypatch.setattr(svc, "_get", flaky)
    monkeypatch.setattr(get_settings(), "unsplash_access_key", "k")
    admin, _ = await make_user(promote_to_admin=True)
    cand = (await client.get("/v1/admin/images/candidates", headers=admin, params={"q": "anything"})).json()[0]
    assert (await client.post("/v1/admin/images/approve", headers=admin, json={"candidate": cand, "sector": "Law"})).status_code == 201
