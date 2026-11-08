"""Public, key-less endpoints: anyone can verify a certificate."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.keys import get_signer
from app.services.render import RenderError, render
from app.db import get_session
from app.models import Certificate, Profile, TransparencyLog
from app.schemas import CertificateOut, TransparencyEntry, VerifyCheckIn, VerifyOut
from app.services.certificates import (
    check_submitted_payload,
    get_certificate,
    verify_certificate,
    verify_full_chain,
)

router = APIRouter(prefix="/v1", tags=["verification"])


@router.get("/verify/{code}", response_model=VerifyOut)
async def verify(code: str, session: AsyncSession = Depends(get_session)):
    return await verify_certificate(session, code.strip().upper())


@router.post("/verify/check", response_model=VerifyOut)
async def verify_check(body: VerifyCheckIn, session: AsyncSession = Depends(get_session)):
    """Submit an (edited) payload; learn whether it still matches the signature."""
    return await check_submitted_payload(session, body.code.strip().upper(), body.payload)


@router.get("/certificates/{code}")
async def certificate_detail(code: str, session: AsyncSession = Depends(get_session)):
    """Everything the certificate page needs to render: payload, art seed, owner slug."""
    cert = await get_certificate(session, code.strip().upper())
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    profile = await session.get(Profile, cert.profile_id) if cert.profile_id else None
    out = CertificateOut.model_validate(cert).model_dump(mode="json")
    out["profile"] = (
        {
            "slug": profile.slug,
            "full_name": profile.full_name,
            "headline": profile.headline,
            "sector": profile.sector,
            "state": profile.state,
        }
        if profile
        else None
    )
    out["verify_url"] = f"/verify/{cert.code}"
    out["revoked"] = cert.revoked_at is not None
    return out


@router.get("/certificates/{code}/qr.svg")
async def certificate_qr(code: str, session: AsyncSession = Depends(get_session)):
    """QR code pointing at the public verification page."""
    import io

    import segno

    cert = await get_certificate(session, code.strip().upper())
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    url = f"{get_settings().public_base_url}/verify/{cert.code}"
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", border=0, scale=8, dark="#1b1a17", light=None, xmldecl=False)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


async def _render_response(code: str, kind: str, session: AsyncSession) -> FileResponse:
    cert = await get_certificate(session, code.strip().upper())
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    if cert.revoked_at is not None:
        raise HTTPException(status.HTTP_410_GONE, "This certificate was revoked")
    try:
        path = await render(cert.code, cert.digest, kind)
    except RenderError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    media = "application/pdf" if kind == "pdf" else "image/png"
    return FileResponse(path, media_type=media, filename=f"pramaan-{cert.code}.{kind}")


@router.get("/certificates/{code}/pdf")
async def certificate_pdf(code: str, session: AsyncSession = Depends(get_session)):
    return await _render_response(code, "pdf", session)


@router.get("/certificates/{code}/image.png")
async def certificate_png(code: str, session: AsyncSession = Depends(get_session)):
    return await _render_response(code, "png", session)


@router.get("/transparency", response_model=list[TransparencyEntry])
async def transparency(
    limit: int = Query(default=50, ge=1, le=500), session: AsyncSession = Depends(get_session)
):
    rows = await session.execute(
        select(TransparencyLog).order_by(TransparencyLog.id.desc()).limit(limit)
    )
    return rows.scalars().all()


@router.get("/transparency/verify")
async def transparency_verify(session: AsyncSession = Depends(get_session)):
    ok, bad_id, count = await verify_full_chain(session)
    return {"ok": ok, "first_bad_entry_id": bad_id, "entries": count}


@router.get("/stats")
async def public_stats(session: AsyncSession = Depends(get_session)):
    from sqlalchemy import func

    profiles = (
        await session.execute(select(func.count()).select_from(Profile).where(Profile.status == "approved"))
    ).scalar_one()
    certs = (await session.execute(select(func.count()).select_from(Certificate))).scalar_one()
    return {"profiles": profiles, "certificates": certs, "key_id": get_signer().key_id}
