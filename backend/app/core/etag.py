"""Conditional GET for public, anonymous JSON (API-03). A client that already holds the answer sends If-None-Match and gets a body-less 304.

Only anonymous GETs under the public prefixes are touched, and only 200 JSON answers; anything with credentials is never tagged, so a private
answer can't be cached by mistake. `Cache-Control: no-cache` means "revalidate every time", so a revocation is still seen at once.
"""
from __future__ import annotations

import hashlib

from starlette.responses import Response

PUBLIC_PREFIXES = ("/v1/verify/", "/v1/certificates/", "/v1/profiles", "/v1/transparency", "/v1/status/", "/.well-known/", "/v1/graph", "/v1/stats")


def eligible(method: str, path: str, has_credentials: bool) -> bool:
    return method == "GET" and not has_credentials and path.startswith(PUBLIC_PREFIXES)


def make_etag(body: bytes) -> str:
    return 'W/"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def matches(if_none_match: str, etag: str) -> bool:
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    mine = etag.removeprefix("W/")
    return any(t.strip().removeprefix("W/") == mine for t in if_none_match.split(","))


async def apply(request, call_next):
    creds = bool(request.headers.get("authorization") or request.headers.get("cookie"))
    response = await call_next(request)
    if not eligible(request.method, request.url.path, creds) or response.status_code != 200:
        return response
    if "application/json" not in response.headers.get("content-type", ""):
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    etag = make_etag(body)
    headers = {k: v for k, v in response.headers.items() if k.lower() not in ("content-length", "etag")}
    headers["ETag"] = etag
    headers["Cache-Control"] = "no-cache"
    if matches(request.headers.get("if-none-match", ""), etag):
        for h in ("content-type",):
            headers.pop(h, None)
        return Response(status_code=304, headers=headers)
    return Response(content=body, status_code=200, headers=headers)
