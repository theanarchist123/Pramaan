"""End-to-end API flow: profile -> claim -> review -> certificate -> verify -> tamper -> erase."""

from app.core import ratelimit


async def _approved_profile_with_cert(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)

    r = await client.post(
        "/v1/profiles",
        headers=person,
        json={
            "full_name": "Meera Iyer",
            "headline": "Marine scientist",
            "sector": "Science",
            "state": "Kerala",
            "consent_public_listing": True,
        },
    )
    assert r.status_code == 201, r.text
    profile = r.json()

    r = await client.post(
        f"/v1/profiles/{profile['id']}/claims",
        headers=person,
        json={"field": "award", "value": "Sagar Samman", "year": 2024},
    )
    assert r.status_code == 201
    claim = r.json()
    assert claim["status"] == "self"  # never trusted on arrival

    assert (await client.post(f"/v1/profiles/{profile['id']}/submit", headers=person)).status_code == 200
    r = await client.post(
        f"/v1/admin/claims/{claim['id']}/verify", headers=admin, json={"reason": "Checked against the published honours list", "evidence_ref": "https://example.org/honours"}
    )
    assert r.status_code == 200
    r = await client.post(
        f"/v1/admin/profiles/{profile['id']}/status", headers=admin, json={"status": "approved"}
    )
    assert r.json()["status"] == "approved"

    r = await client.post(f"/v1/profiles/{profile['id']}/certificate", headers=person)
    assert r.status_code == 201, r.text
    return person, admin, profile, r.json()


async def test_full_flow_verify_and_tamper(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    code = cert["code"]

    # public verification needs no credentials
    r = await client.get(f"/v1/verify/{code}")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is True and body["chain_ok"] is True
    # the page can show every step of the check, and a stranger can redo them offline
    assert body["log_position"] >= 1 and body["log_size"] >= body["log_position"]
    assert body["signature"] and body["public_key"] and body["entry_hash"]

    # themed photo was chosen for the person's sector; QR points at the public verify page
    # The certificate gets a vetted picture for its sector: a stock photo, or (once any are approved) a reviewed generated asset. Updated, not weakened: the
    # sector rule is unchanged, only the set of vetted sources grew (see app/generated_art.py).
    from app import generated_art
    from app.domain import SECTOR_PHOTOS

    assert cert["photo_id"] in SECTOR_PHOTOS["Science"] + generated_art.ids_for_sector("Science")
    qr = await client.get(f"/v1/certificates/{code}/qr.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in qr.content
    assert (await client.get("/v1/certificates/PRM-NOPE/qr.svg")).status_code == 404
    mine = await client.get(f"/v1/profiles/{profile['id']}/certificates", headers=person)
    assert [c["code"] for c in mine.json()] == [code]
    stranger = await client.get(f"/v1/profiles/{profile['id']}/certificates")
    assert stranger.status_code == 401

    # an edited payload fails and the changed field is named
    forged = dict(cert["payload"])
    forged["claims"] = [dict(c, value="Padma Vibhushan 2024") for c in forged["claims"]]
    r = await client.post("/v1/verify/check", json={"code": code, "payload": forged})
    result = r.json()
    assert result["valid"] is False
    assert any(f.startswith("claims[award") for f in result["changed_fields"])

    # an untouched payload still verifies
    r = await client.post("/v1/verify/check", json={"code": code, "payload": cert["payload"]})
    assert r.json()["valid"] is True

    # transparency log is intact and public
    assert (await client.get("/v1/transparency/verify")).json()["ok"] is True
    assert any(e["certificate_code"] == code for e in (await client.get("/v1/transparency")).json())

    # public key is published
    keys = (await client.get("/.well-known/pramaan-keys.json")).json()["keys"]
    assert keys[0]["crv"] == "Ed25519"


async def test_offline_verification_recipe_shown_on_the_verify_page_works(client, make_user):
    """The page tells strangers how to verify with nothing but the public key. Prove that recipe."""
    import base64
    import hashlib
    import json

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    v = (await client.get(f"/v1/verify/{cert['code']}")).json()
    b64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731

    def check(payload):
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).digest()
        Ed25519PublicKey.from_public_bytes(b64(v["public_key"])).verify(b64(v["signature"]), digest)

    check(v["payload"])  # genuine: no exception
    forged = json.loads(json.dumps(v["payload"]))
    forged["full_name"] = "Someone Else"
    try:
        check(forged)
    except InvalidSignature:
        pass
    else:  # pragma: no cover
        raise AssertionError("forged payload verified!")

    # the published key matches the one in the verification response
    keys = (await client.get("/.well-known/pramaan-keys.json")).json()["keys"]
    assert keys[0]["x"] == v["public_key"]


async def test_year_is_not_duplicated_in_certified_claims(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    p = (await client.post("/v1/profiles", headers=person,
                           json={"full_name": "Year Test", "consent_public_listing": True})).json()
    c = (await client.post(f"/v1/profiles/{p['id']}/claims", headers=person,
                           json={"field": "award", "value": "Won the Foo Prize in 2022.", "year": 2022})).json()
    await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)
    await client.post(f"/v1/admin/claims/{c['id']}/verify", headers=admin, json={"reason": "Checked against the published honours list", "evidence_ref": "https://example.org/honours"})
    await client.post(f"/v1/admin/profiles/{p['id']}/status", headers=admin, json={"status": "approved"})
    cert = (await client.post(f"/v1/profiles/{p['id']}/certificate", headers=person)).json()
    assert cert["payload"]["claims"][0]["value"] == "Won the Foo Prize in 2022."


async def test_unverified_claims_are_not_certified(client, make_user):
    person, _ = await make_user()
    admin, _ = await make_user(promote_to_admin=True)
    p = (
        await client.post(
            "/v1/profiles",
            headers=person,
            json={"full_name": "Only Self Claims", "consent_public_listing": True},
        )
    ).json()
    await client.post(
        f"/v1/profiles/{p['id']}/claims", headers=person, json={"field": "award", "value": "Unproven"}
    )
    await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)
    await client.post(f"/v1/admin/profiles/{p['id']}/status", headers=admin, json={"status": "approved"})
    r = await client.post(f"/v1/profiles/{p['id']}/certificate", headers=person)
    assert r.status_code == 409  # nothing verified -> nothing to certify


async def test_cannot_certify_unapproved_or_without_consent(client, make_user):
    person, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=person, json={"full_name": "No Consent"})).json()
    assert (await client.post(f"/v1/profiles/{p['id']}/submit", headers=person)).status_code == 409
    assert (await client.post(f"/v1/profiles/{p['id']}/certificate", headers=person)).status_code == 409


async def test_directory_is_public_but_only_shows_approved(client, make_user):
    person, _ = await make_user()
    p = (
        await client.post(
            "/v1/profiles", headers=person, json={"full_name": "Hidden Draft", "consent_public_listing": True}
        )
    ).json()
    listed = (await client.get("/v1/profiles", params={"q": "Hidden Draft"})).json()
    assert all(x["id"] != p["id"] for x in listed)
    assert (await client.get(f"/v1/profiles/{p['slug']}")).status_code == 404  # anonymous
    assert (await client.get(f"/v1/profiles/{p['slug']}", headers=person)).status_code == 200  # owner


async def test_other_users_cannot_edit(client, make_user):
    owner, _ = await make_user()
    stranger, _ = await make_user()
    p = (await client.post("/v1/profiles", headers=owner, json={"full_name": "Owned Profile"})).json()
    r = await client.patch(f"/v1/profiles/{p['id']}", headers=stranger, json={"headline": "hacked"})
    assert r.status_code == 403


async def test_admin_endpoints_reject_non_admins(client, make_user):
    person, _ = await make_user()
    assert (await client.get("/v1/admin/review", headers=person)).status_code == 403
    assert (await client.get("/v1/admin/review")).status_code == 401


async def test_api_key_scopes_and_rate_limit(client, make_user):
    ratelimit.reset()
    person, _ = await make_user()
    r = await client.post(
        "/v1/api-keys",
        headers=person,
        json={"name": "reader", "scopes": ["profiles:read"], "rate_limit_per_min": 3},
    )
    assert r.status_code == 201
    key = r.json()["key"]
    assert key.startswith("pk_live_")

    # read scope works, write scope is refused
    assert (await client.get("/v1/profiles/mine", headers={"X-API-Key": key})).status_code == 200
    r = await client.post("/v1/profiles", headers={"X-API-Key": key}, json={"full_name": "Via Key"})
    assert r.status_code == 403

    # key can't manage keys; rate limit eventually trips
    assert (await client.get("/v1/api-keys", headers={"X-API-Key": key})).status_code == 403
    codes = [
        (await client.get("/v1/profiles/mine", headers={"X-API-Key": key})).status_code
        for _ in range(4)
    ]
    assert 429 in codes

    # revoked key stops working
    listed = (await client.get("/v1/api-keys", headers=person)).json()
    await client.delete(f"/v1/api-keys/{listed[0]['id']}", headers=person)
    ratelimit.reset()
    assert (await client.get("/v1/profiles/mine", headers={"X-API-Key": key})).status_code == 401


async def test_erasure_revokes_certificate_but_keeps_log(client, make_user):
    person, admin, profile, cert = await _approved_profile_with_cert(client, make_user)
    assert (await client.delete(f"/v1/profiles/{profile['id']}", headers=person)).status_code == 204

    body = (await client.get(f"/v1/verify/{cert['code']}")).json()
    assert body["valid"] is False and body["revoked"] is True
    assert (await client.get(f"/v1/profiles/{profile['slug']}")).status_code == 404
    # the log still verifies: it only ever held hashes
    assert (await client.get("/v1/transparency/verify")).json()["ok"] is True
