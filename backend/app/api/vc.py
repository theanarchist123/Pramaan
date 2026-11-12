"""Public Verifiable Credential endpoints (TRU-08): the DID document, a certificate as a VC, and the revocation status list."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services import credentials
from app.services.certificates import get_certificate

router = APIRouter(tags=["verifiable-credentials"])
_VC = "application/vc+ld+json"


@router.get("/.well-known/did.json")
async def did_json(response: Response):
    response.headers["Cache-Control"] = "public, max-age=300"
    return credentials.did_document()


@router.get("/v1/certificates/{code}/vc")
async def certificate_as_vc(code: str, session: AsyncSession = Depends(get_session)):
    cert = await get_certificate(session, code.strip().upper())
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    body = await credentials.credential_for(session, cert)
    await session.commit()  # persists a lazily assigned status index
    from fastapi.responses import JSONResponse

    return JSONResponse(body, media_type=_VC)


@router.get("/v1/status/revocation/{list_id}")
async def revocation_status_list(list_id: str, session: AsyncSession = Depends(get_session)):
    if list_id != credentials.STATUS_LIST_ID:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such status list")
    from fastapi.responses import JSONResponse

    return JSONResponse(await credentials.status_list_credential(session), media_type=_VC, headers={"Cache-Control": "public, max-age=60"})
