"""OAuth 2.0 endpoints (API-02). See services/oauth.py for the rules.

The consent screen lives in the web app; it calls GET/POST /v1/oauth/authorize as the signed-in member. The token endpoint takes the standard
form-encoded body and is the only one a third-party app calls directly.
"""
from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.ratelimit import ip_limit
from app.db import get_session
from app.deps import Principal, get_principal
from app.models import OAuthClient, OAuthToken
from app.services import oauth as svc

router = APIRouter(prefix="/v1/oauth", tags=["oauth"])
meta = APIRouter(tags=["oauth"])


def _member(principal: Principal) -> Principal:
    if principal.via != "jwt":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sign in to do this")
    return principal


def _err(e: svc.OAuthError) -> JSONResponse:
    body = {"error": e.error}
    if e.description:
        body["error_description"] = e.description
    return JSONResponse(body, status_code=e.status, headers={"Cache-Control": "no-store"})


class ClientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    redirect_uris: list[str] = Field(min_length=1, max_length=5)


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def register_client(body: ClientIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    _member(principal)
    bad = [u for u in body.redirect_uris if not svc.valid_redirect(u)]
    if bad:
        raise HTTPException(422, "Redirect URIs must be https (or http on localhost), with no credentials or fragment")
    c = OAuthClient(client_id="pc_" + secrets.token_urlsafe(18), name=body.name.strip(), redirect_uris=list(dict.fromkeys(body.redirect_uris)),
                    owner_id=principal.user.id)
    session.add(c)
    await session.commit()
    return {"client_id": c.client_id, "name": c.name, "redirect_uris": c.redirect_uris}


class AuthorizeIn(BaseModel):
    client_id: str
    redirect_uri: str
    scope: str
    state: str | None = Field(default=None, max_length=500)
    code_challenge: str = ""
    code_challenge_method: str = "S256"
    response_type: str = "code"
    approve: bool = False


async def _validate(session: AsyncSession, a: AuthorizeIn | dict):
    d = a if isinstance(a, dict) else a.model_dump()
    if d["response_type"] != "code":
        raise svc.OAuthError("unsupported_response_type", "Only response_type=code is supported")
    client = await svc.get_client(session, d["client_id"])
    svc.check_request(client, d["redirect_uri"], d["code_challenge"], d["code_challenge_method"])
    return client, svc.parse_scopes(d["scope"])


@router.get("/authorize")
async def authorize_info(
    client_id: str, redirect_uri: str, scope: str, state: str | None = None, code_challenge: str = "", code_challenge_method: str = "S256",
    response_type: str = "code", principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session),
):
    """What the consent screen shows. Anything wrong with the app or redirect is an error here, never a redirect."""
    _member(principal)
    try:
        client, scopes = await _validate(session, dict(client_id=client_id, redirect_uri=redirect_uri, scope=scope, code_challenge=code_challenge,
                                                       code_challenge_method=code_challenge_method, response_type=response_type))
    except svc.OAuthError as e:
        return _err(e)
    return {"client_name": client.name, "scopes": scopes, "redirect_host": redirect_uri.split("/")[2] if "//" in redirect_uri else ""}


@router.post("/authorize")
async def authorize(body: AuthorizeIn, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    _member(principal)
    try:
        client, scopes = await _validate(session, body)
    except svc.OAuthError as e:
        return _err(e)
    if not body.approve:
        return {"redirect_to": svc.redirect_with(body.redirect_uri, {"error": "access_denied", "state": body.state})}
    code = await svc.issue_code(session, client, principal.user, scopes, body.redirect_uri, body.code_challenge)
    return {"redirect_to": svc.redirect_with(body.redirect_uri, {"code": code, "state": body.state})}


@router.post("/token", dependencies=[Depends(ip_limit("oauth-token", 60))])
async def token(
    grant_type: str = Form(...), client_id: str = Form(...), code: str = Form(""), redirect_uri: str = Form(""),
    code_verifier: str = Form(""), refresh_token: str = Form(""), session: AsyncSession = Depends(get_session),
):
    try:
        if grant_type == "authorization_code":
            body = await svc.exchange_code(session, client_id, code, redirect_uri, code_verifier)
        elif grant_type == "refresh_token":
            body = await svc.refresh(session, client_id, refresh_token)
        else:
            raise svc.OAuthError("unsupported_grant_type", "Use authorization_code or refresh_token")
    except svc.OAuthError as e:
        return _err(e)
    return JSONResponse(body, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


@router.post("/revoke", dependencies=[Depends(ip_limit("oauth-revoke", 60))])
async def revoke(token: str = Form(""), session: AsyncSession = Depends(get_session)):
    await svc.revoke_token(session, token)
    return Response(status_code=200)


@router.get("/grants")
async def grants(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    """The apps you have let in: names and scopes only, never a token."""
    _member(principal)
    rows = (await session.execute(
        select(OAuthToken, OAuthClient.name).join(OAuthClient, OAuthClient.client_id == OAuthToken.client_id)
        .where(OAuthToken.user_id == principal.user.id, OAuthToken.revoked_at.is_(None)).order_by(OAuthToken.created_at.desc())
    )).all()
    return [{"id": t.id, "client_name": name, "scopes": t.scopes, "since": t.created_at} for t, name in rows]


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_grant(grant_id: uuid.UUID, principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    _member(principal)
    row = await session.get(OAuthToken, grant_id)
    if row is None or row.user_id != principal.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    await svc.revoke_family(session, row.family)
    await session.commit()


@meta.get("/.well-known/oauth-authorization-server")
async def discovery(request: Request):
    """RFC 8414 metadata. The authorization endpoint is the consent screen in the web app."""
    s = get_settings()
    api = s.api_base_url.rstrip("/")
    return {
        "issuer": api, "authorization_endpoint": f"{s.public_base_url.rstrip('/')}/oauth/authorize", "token_endpoint": f"{api}/v1/oauth/token",
        "revocation_endpoint": f"{api}/v1/oauth/revoke", "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"], "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"], "scopes_supported": sorted(svc.OAUTH_SCOPES),
    }
