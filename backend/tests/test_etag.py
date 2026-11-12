from app.core.etag import eligible, make_etag, matches


def test_only_anonymous_public_gets_are_tagged():
    assert eligible("GET", "/v1/verify/PRM-X", False)
    assert not eligible("GET", "/v1/verify/PRM-X", True)  # credentials: private, never tagged
    assert not eligible("POST", "/v1/verify/batch", False)
    assert not eligible("GET", "/v1/admin/overview", False)
    assert not eligible("GET", "/v1/me", False)


def test_if_none_match_matching():
    e = make_etag(b"{}")
    assert matches(e, e) and matches("*", e) and matches('"a", ' + e, e)
    assert not matches("", e) and not matches('W/"other"', e)


def test_304_round_trip(client):
    r = client.get("/.well-known/pramaan-keys.json")
    assert r.status_code == 200 and r.headers["etag"] and r.headers["cache-control"] == "no-cache"
    again = client.get("/.well-known/pramaan-keys.json", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    changed = client.get("/.well-known/pramaan-keys.json", headers={"If-None-Match": 'W/"x"'})
    assert changed.status_code == 200 and changed.json() == r.json()


def test_credentialed_request_gets_no_etag(client):
    r = client.get("/.well-known/pramaan-keys.json", headers={"Authorization": "Bearer nope"})
    assert "etag" not in r.headers


def test_middleware_without_a_database():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.core import etag

    app = FastAPI()

    @app.middleware("http")
    async def mw(request, call_next):
        return await etag.apply(request, call_next)

    @app.get("/v1/verify/{code}")
    def v(code: str):
        return {"code": code, "valid": True}

    c = TestClient(app)
    r = c.get("/v1/verify/A")
    assert r.status_code == 200 and r.json() == {"code": "A", "valid": True} and r.headers["cache-control"] == "no-cache"
    r2 = c.get("/v1/verify/A", headers={"If-None-Match": r.headers["etag"]})
    assert r2.status_code == 304 and r2.content == b""
    assert c.get("/v1/verify/B", headers={"If-None-Match": r.headers["etag"]}).status_code == 200
