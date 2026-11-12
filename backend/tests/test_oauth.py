import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from app.core import ratelimit

REDIRECT = "https://app.example.org/callback"


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def register(client, person, redirects=(REDIRECT,)):
    r = await client.post("/v1/oauth/clients", headers=person, json={"name": "Demo app", "redirect_uris": list(redirects)})
    assert r.status_code == 201, r.text
    return r.json()["client_id"]


def q(cid, challenge, **kw):
    base = {"client_id": cid, "redirect_uri": REDIRECT, "scope": "verify:read profiles:read", "state": "xyz",
            "code_challenge": challenge, "code_challenge_method": "S256", "response_type": "code"}
    base.update(kw)
    return base


async def get_code(client, person, cid, challenge, approve=True):
    r = await client.post("/v1/oauth/authorize", headers=person, json={**q(cid, challenge), "approve": approve})
    assert r.status_code == 200, r.text
    url = urlparse(r.json()["redirect_to"])
    return {k: v[0] for k, v in parse_qs(url.query).items()}, url


async def exchange(client, cid, code, verifier, redirect=REDIRECT):
    return await client.post("/v1/oauth/token", data={"grant_type": "authorization_code", "client_id": cid, "code": code,
                                                      "redirect_uri": redirect, "code_verifier": verifier})


async def test_the_whole_flow_and_the_token_works_but_only_within_its_scopes(client, make_user):
    ratelimit.reset()
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    info = (await client.get("/v1/oauth/authorize", headers=person, params=q(cid, challenge))).json()
    assert info["client_name"] == "Demo app" and info["scopes"] == ["verify:read", "profiles:read"]
    params, url = await get_code(client, person, cid, challenge)
    assert url.geturl().startswith(REDIRECT) and params["state"] == "xyz"
    r = await exchange(client, cid, params["code"], verifier)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    tok = r.json()
    assert tok["token_type"] == "Bearer" and tok["access_token"].startswith("pat_") and tok["refresh_token"]
    auth = {"Authorization": f"Bearer {tok['access_token']}"}
    assert (await client.get("/v1/profiles/mine", headers=auth)).status_code == 200
    assert (await client.post("/v1/profiles", headers=auth, json={"full_name": "No"})).status_code == 403  # profiles:write was never granted
    assert (await client.get("/v1/api-keys", headers=auth)).status_code == 403  # never able to manage keys


async def test_pkce_is_mandatory_and_the_verifier_must_match(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    no_pkce = await client.post("/v1/oauth/authorize", headers=person, json={**q(cid, challenge), "code_challenge": "", "approve": True})
    assert no_pkce.status_code == 400
    plain = await client.post("/v1/oauth/authorize", headers=person, json={**q(cid, challenge, code_challenge_method="plain"), "approve": True})
    assert plain.status_code == 400
    params, _ = await get_code(client, person, cid, challenge)
    bad = await exchange(client, cid, params["code"], "wrong-verifier-" + "x" * 40)
    assert bad.status_code == 400 and bad.json()["error"] == "invalid_grant"


async def test_a_code_works_once_and_replaying_it_revokes_what_it_made(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    params, _ = await get_code(client, person, cid, challenge)
    first = await exchange(client, cid, params["code"], verifier)
    assert first.status_code == 200
    again = await exchange(client, cid, params["code"], verifier)
    assert again.status_code == 400
    r = await client.get("/v1/profiles/mine", headers={"Authorization": f"Bearer {first.json()['access_token']}"})
    assert r.status_code == 401  # the replay was treated as theft


async def test_redirect_uris_must_match_exactly_and_unregistered_ones_never_redirect(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    _, challenge = pkce()
    r = await client.post("/v1/oauth/authorize", headers=person, json={**q(cid, challenge, redirect_uri="https://evil.example/cb"), "approve": True})
    assert r.status_code == 400 and "redirect_to" not in r.text
    for bad in ("http://app.example.org/cb", "javascript:alert(1)", "https://user:pw@app.example.org/cb", "https://app.example.org/cb#frag"):
        r = await client.post("/v1/oauth/clients", headers=person, json={"name": "x", "redirect_uris": [bad]})
        assert r.status_code == 422, bad
    ok = await client.post("/v1/oauth/clients", headers=person, json={"name": "cli", "redirect_uris": ["http://127.0.0.1:8123/cb"]})
    assert ok.status_code == 201  # loopback http is allowed for native apps


async def test_denying_sends_access_denied_and_no_code(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    _, challenge = pkce()
    params, _ = await get_code(client, person, cid, challenge, approve=False)
    assert params["error"] == "access_denied" and "code" not in params and params["state"] == "xyz"


async def test_refresh_rotates_and_a_reused_refresh_token_kills_the_family(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    params, _ = await get_code(client, person, cid, challenge)
    t1 = (await exchange(client, cid, params["code"], verifier)).json()
    r2 = await client.post("/v1/oauth/token", data={"grant_type": "refresh_token", "client_id": cid, "refresh_token": t1["refresh_token"]})
    assert r2.status_code == 200
    t2 = r2.json()
    assert t2["refresh_token"] != t1["refresh_token"]
    assert (await client.get("/v1/profiles/mine", headers={"Authorization": f"Bearer {t1['access_token']}"})).status_code == 401
    reuse = await client.post("/v1/oauth/token", data={"grant_type": "refresh_token", "client_id": cid, "refresh_token": t1["refresh_token"]})
    assert reuse.status_code == 400
    assert (await client.get("/v1/profiles/mine", headers={"Authorization": f"Bearer {t2['access_token']}"})).status_code == 401


async def test_revoke_and_the_user_can_list_and_remove_grants(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    params, _ = await get_code(client, person, cid, challenge)
    tok = (await exchange(client, cid, params["code"], verifier)).json()
    grants = (await client.get("/v1/oauth/grants", headers=person)).json()
    assert len(grants) == 1 and grants[0]["client_name"] == "Demo app" and "access_token" not in str(grants)
    assert (await client.delete(f"/v1/oauth/grants/{grants[0]['id']}", headers=person)).status_code == 204
    assert (await client.get("/v1/profiles/mine", headers={"Authorization": f"Bearer {tok['access_token']}"})).status_code == 401
    # RFC 7009: revoking anything, even junk, answers 200
    assert (await client.post("/v1/oauth/revoke", data={"token": "junk"})).status_code == 200


async def test_an_admins_oauth_token_is_not_admin(client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    cid = await register(client, admin)
    verifier, challenge = pkce()
    params, _ = await get_code(client, admin, cid, challenge)
    tok = (await exchange(client, cid, params["code"], verifier)).json()
    assert (await client.get("/v1/admin/review", headers={"Authorization": f"Bearer {tok['access_token']}"})).status_code == 403


async def test_discovery_document(client):
    d = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert d["code_challenge_methods_supported"] == ["S256"] and d["token_endpoint"].endswith("/v1/oauth/token")


async def test_apps_cannot_reach_sign_in_mfa_identity_or_account_endpoints(client, make_user):
    person, _ = await make_user()
    cid = await register(client, person)
    verifier, challenge = pkce()
    params, _ = await get_code(client, person, cid, challenge)
    tok = (await exchange(client, cid, params["code"], verifier)).json()
    auth = {"Authorization": f"Bearer {tok['access_token']}"}
    assert (await client.get("/v1/auth/mfa/status", headers=auth)).status_code == 403
    assert (await client.post("/v1/auth/mfa/enroll", headers=auth)).status_code == 403
    assert (await client.get("/v1/oauth/grants", headers=auth)).status_code == 403
    assert (await client.post("/v1/oauth/clients", headers=auth, json={"name": "x", "redirect_uris": [REDIRECT]})).status_code == 403
