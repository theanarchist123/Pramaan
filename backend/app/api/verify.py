"""Public, key-less endpoints: anyone can verify a certificate."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints
from app.core.ratelimit import ip_limit
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


class BatchIn(BaseModel):
    codes: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]] = Field(min_length=1, max_length=50)


@router.post("/verify/batch", dependencies=[Depends(ip_limit("verify-batch", 30))])
async def verify_batch(body: BatchIn, session: AsyncSession = Depends(get_session)):
    """Check up to 50 certificate codes in one call. Each answer is exactly what GET /v1/verify/{code} says (same function), codes are normalised to
    upper case, duplicates are answered once, and order is kept. Public: verification needs no account."""
    seen: set[str] = set()
    results = []
    for raw in body.codes:
        code = raw.strip().upper()
        if code in seen:
            continue
        seen.add(code)
        found = await get_certificate(session, code) is not None
        v = await verify_certificate(session, code)
        results.append({
            "code": code, "found": found, "valid": v.valid, "revoked": v.revoked, "superseded_by": v.superseded_by,
            "key_id": v.key_id, "issued_at": v.issued_at, "reason": v.reason,
        })
    return {"checked": len(results), "results": results}


@router.get("/verify/{code}", response_model=VerifyOut)
async def verify(code: str, session: AsyncSession = Depends(get_session)):
    code = code.strip().upper()
    result = await verify_certificate(session, code)
    cert = await get_certificate(session, code)
    if cert is not None and cert.profile_id is not None:
        from app.services import insights as insights_svc

        await insights_svc.record(cert.profile_id, "cert_checks")  # a count only
    return result


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


# --------------------------------------------------------------------------- #
# Merkle view of the log (TRU-09): signed checkpoint, inclusion and consistency proofs
# --------------------------------------------------------------------------- #
async def _leaves(session: AsyncSession) -> tuple[list[TransparencyLog], list[bytes]]:
    from app.core import merkle

    rows = (await session.execute(select(TransparencyLog).order_by(TransparencyLog.id.asc()))).scalars().all()
    return list(rows), [merkle.leaf_hash(bytes.fromhex(r.entry_hash)) for r in rows]


def checkpoint_text(size: int, root_hex: str) -> str:
    """What the registry signs. A fixed, human-readable form so anyone can rebuild it byte for byte."""
    return f"pramaan-log-checkpoint-v1\nsize={size}\nroot={root_hex}\n"


@router.get("/transparency/checkpoint")
async def transparency_checkpoint(session: AsyncSession = Depends(get_session)):
    import hashlib

    from app.core import merkle

    _, leaves = await _leaves(session)
    root_hex = merkle.root(leaves).hex()
    text = checkpoint_text(len(leaves), root_hex)
    signer = get_signer()
    return {
        "size": len(leaves), "root": root_hex, "text": text, "key_id": signer.key_id,
        "signature": signer.sign_digest(hashlib.sha256(text.encode()).hexdigest()),
    }


@router.get("/transparency/proof/{code}")
async def transparency_inclusion(code: str, session: AsyncSession = Depends(get_session)):
    from app.core import merkle

    rows, leaves = await _leaves(session)
    index = next((i for i, r in enumerate(rows) if r.certificate_code == code.strip().upper()), None)
    if index is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That certificate is not in the log")
    return {
        "index": index, "size": len(leaves), "entry_hash": rows[index].entry_hash,
        "root": merkle.root(leaves).hex(), "proof": [p.hex() for p in merkle.inclusion_proof(leaves, index)],
    }


@router.get("/transparency/consistency")
async def transparency_consistency(first: int = Query(ge=1), session: AsyncSession = Depends(get_session)):
    from app.core import merkle

    _, leaves = await _leaves(session)
    if first > len(leaves):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That size is larger than the log")
    return {
        "first": first, "second": len(leaves), "first_root": merkle.root(leaves[:first]).hex(),
        "second_root": merkle.root(leaves).hex(), "proof": [p.hex() for p in merkle.consistency_proof(leaves, first)],
    }
