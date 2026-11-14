"""API behaviour for introductions and insights. Needs Postgres (docker compose up -d db)."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import update

from app.db import get_sessionmaker
from app.models import Profile, User


async def _verified(user_json):
    async with get_sessionmaker()() as s:
        await s.execute(update(User).where(User.id == uuid.UUID(user_json["id"])).values(email_verified_at=datetime.now(timezone.utc)))
        await s.commit()


async def _approved_profile(client, headers, name="Meera Iyer"):
    p = (await client.post("/v1/profiles", headers=headers, json={"full_name": name, "sector": "Science", "state": "Kerala", "consent_public_listing": True})).json()
    async with get_sessionmaker()() as s:
        await s.execute(update(Profile).where(Profile.id == uuid.UUID(p["id"])).values(status="approved"))
        await s.commit()
    return p


async def test_visits_are_counted_without_storing_who_visited(client, make_user):
    h, u = await make_user()
    p = await _approved_profile(client, h)
    for _ in range(3):
        assert (await client.get(f"/v1/profiles/{p['slug']}")).status_code == 200
    stats = (await client.get(f"/v1/profiles/{p['id']}/insights", headers=h)).json()
    assert stats["views_total"] == 3 and stats["checks_total"] == 0
    # the owner's own view does not inflate the count
    await client.get(f"/v1/profiles/{p['slug']}", headers=h)
    assert (await client.get(f"/v1/profiles/{p['id']}/insights", headers=h)).json()["views_total"] == 3


async def test_only_the_owner_sees_insights(client, make_user):
    h, _ = await make_user()
    p = await _approved_profile(client, h)
    other, _ = await make_user()
    assert (await client.get(f"/v1/profiles/{p['id']}/insights", headers=other)).status_code in (403, 404)


async def test_intro_request_flow_and_it_cannot_target_yourself(client, make_user):
    owner, ou = await make_user()
    await _verified(ou)
    p = await _approved_profile(client, owner)
    asker, au = await make_user()
    await _verified(au)

    r = await client.post(f"/v1/profiles/{p['slug']}/intro", headers=asker, json={"message": "I would like to invite you to speak. https://evil.example"})
    assert r.status_code == 201, r.text
    inbox = (await client.get("/v1/intros/incoming", headers=owner)).json()
    assert len(inbox) == 1 and "http" not in inbox[0]["message"] and "email" not in inbox[0]
    # you cannot ask for an introduction to yourself
    assert (await client.post(f"/v1/profiles/{p['slug']}/intro", headers=owner, json={"message": "hello me"})).status_code == 400
    # only the owner can answer
    assert (await client.post(f"/v1/intros/{inbox[0]['id']}/respond", headers=asker, json={"accept": True})).status_code in (403, 404)
    done = await client.post(f"/v1/intros/{inbox[0]['id']}/respond", headers=owner, json={"accept": True})
    assert done.status_code == 200 and done.json()["status"] == "accepted"


async def test_photo_upload_is_reencoded_and_an_approved_profile_goes_back_for_review(client, make_user):
    import io

    from PIL import Image

    h, u = await make_user()
    p = await _approved_profile(client, h)
    buf = io.BytesIO()
    Image.new("RGB", (900, 1200), (200, 120, 40)).save(buf, "PNG")
    r = await client.post(f"/v1/profiles/{p['id']}/photo", headers=h, files={"file": ("me.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["photo_url"].endswith(f"/v1/profiles/{p['slug']}/photo") and r.json()["status"] == "pending_review"
    # not public while it waits for a person; the owner can see it
    assert (await client.get(f"/v1/profiles/{p['slug']}/photo")).status_code == 404
    mine = await client.get(f"/v1/profiles/{p['slug']}/photo", headers=h)
    assert mine.status_code == 200 and mine.headers["content-type"] == "image/jpeg"
    assert max(Image.open(io.BytesIO(mine.content)).size) <= 640
    # a non-image is refused
    bad = await client.post(f"/v1/profiles/{p['id']}/photo", headers=h, files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 422
