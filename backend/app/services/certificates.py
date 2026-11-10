"""Issuing and verifying signed certificates + the hash-chained transparency log."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.keys import get_signer, public_keyring
from app.core.signing import (
    GENESIS_HASH,
    build_certificate_payload,
    chain_hash,
    digest_payload,
    verify_chain,
    verify_payload,
    verify_signature,
)
from app.models import Certificate, Profile, TransparencyLog
from app.schemas import VerifyOut

VERIFIED_STATUSES = {"web", "document"}
MIN_CONFIDENCE = 0.5
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_CHAIN_LOCK_ID = 7001


class CertificateError(Exception):
    pass


def new_code() -> str:
    return "PRM-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))


def verified_claims(profile: Profile) -> list[dict]:
    def label(c) -> str:
        # Append the year only if the text doesn't already say it.
        return c.value if not c.year or str(c.year) in c.value else f"{c.value} ({c.year})"

    return [
        {"field": c.field, "value": label(c), "status": c.status}
        for c in profile.claims
        if c.status in VERIFIED_STATUSES and c.confidence >= MIN_CONFIDENCE
    ]


async def issue_certificate(
    session: AsyncSession, profile: Profile, *, photo_id: str = ""
) -> Certificate:
    if profile.status != "approved":
        raise CertificateError("Profile must be approved before a certificate can be issued.")
    claims = verified_claims(profile)
    if not claims:
        raise CertificateError("No verified claims yet — nothing to certify.")

    existing = (
        await session.execute(
            select(Certificate).where(Certificate.profile_id == profile.id, Certificate.revoked_at.is_(None))
            .order_by(Certificate.issued_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        current = sorted((c["field"], str(c["value"]), c["status"]) for c in claims)
        issued = sorted((c["field"], str(c["value"]), c["status"]) for c in existing.payload.get("claims", []))
        if current == issued and existing.payload.get("full_name") == profile.full_name:
            raise CertificateError("An active certificate already covers these claims.")

    signer = get_signer()
    issued_at = datetime.now(timezone.utc)
    code = new_code()
    payload = build_certificate_payload(
        cert_id=code,
        profile_id=str(profile.id),
        full_name=profile.full_name,
        claims=claims,
        issued_at=issued_at,
    )
    # Random salt: the public digest can't be used to confirm a guessed name/claims after erasure.
    payload["salt"] = secrets.token_hex(16)
    digest = digest_payload(payload)

    # Serialise appends so the chain can never fork.
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_LOCK_ID})
    last = (
        await session.execute(select(TransparencyLog).order_by(TransparencyLog.id.desc()).limit(1))
    ).scalar_one_or_none()
    prev = last.entry_hash if last else GENESIS_HASH
    issued_iso = payload["issued_at"]

    cert = Certificate(
        code=code,
        profile_id=profile.id,
        payload=payload,
        digest=digest,
        signature=signer.sign_digest(digest),
        key_id=signer.key_id,
        art_seed=digest,
        photo_id=photo_id,
        issued_at=issued_at,
    )
    session.add(cert)
    session.add(
        TransparencyLog(
            certificate_code=code,
            digest=digest,
            prev_hash=prev,
            entry_hash=chain_hash(prev, digest, issued_iso),
            issued_at=issued_iso,
        )
    )
    await session.flush()
    return cert


async def get_certificate(session: AsyncSession, code: str) -> Certificate | None:
    return (
        await session.execute(select(Certificate).where(Certificate.code == code))
    ).scalar_one_or_none()


async def verify_certificate(session: AsyncSession, code: str) -> VerifyOut:
    cert = await get_certificate(session, code)
    if cert is None:
        return VerifyOut(valid=False, code=code, reason="No certificate with this code exists.")

    signer = get_signer()
    cert_pub = public_keyring().get(cert.key_id)
    digest_ok = digest_payload(cert.payload) == cert.digest
    sig_ok = bool(cert_pub) and digest_ok and verify_signature(cert.digest, cert.signature, cert_pub)

    entry = (
        await session.execute(
            select(TransparencyLog).where(TransparencyLog.certificate_code == code)
        )
    ).scalar_one_or_none()
    chain_ok = bool(
        entry
        and entry.digest == cert.digest
        and chain_hash(entry.prev_hash, entry.digest, entry.issued_at) == entry.entry_hash
    )

    log_size = (await session.execute(select(func.count()).select_from(TransparencyLog))).scalar_one()
    log_position = None
    if entry is not None:
        log_position = (
            await session.execute(
                select(func.count()).select_from(TransparencyLog).where(TransparencyLog.id <= entry.id)
            )
        ).scalar_one()

    revoked = cert.revoked_at is not None
    valid = sig_ok and chain_ok and not revoked
    if revoked:
        reason = "This certificate was revoked by the registry."
    elif not sig_ok:
        reason = "Stored certificate content no longer matches its signature."
    elif not chain_ok:
        reason = "Certificate is missing from, or inconsistent with, the transparency log."
    else:
        reason = "Signature valid; content unchanged since issuance."

    return VerifyOut(
        valid=valid,
        code=code,
        reason=reason,
        revoked=revoked,
        digest=cert.digest,
        key_id=cert.key_id,
        issued_at=cert.payload.get("issued_at", ""),
        chain_ok=chain_ok,
        payload=cert.payload,
        signature_ok=sig_ok,
        signature=cert.signature,
        public_key=cert_pub or signer.public_key_b64,
        log_position=log_position,
        log_size=log_size,
        entry_hash=entry.entry_hash if entry else "",
    )


async def check_submitted_payload(session: AsyncSession, code: str, submitted: dict) -> VerifyOut:
    """The 'Try to tamper' backend: does an edited payload still verify, and what changed?"""
    cert = await get_certificate(session, code)
    if cert is None:
        return VerifyOut(valid=False, code=code, reason="No certificate with this code exists.")
    result = verify_payload(
        submitted, cert.signature, public_keyring().get(cert.key_id, ""), original=cert.payload
    )
    return VerifyOut(
        valid=result.valid,
        code=code,
        reason=result.reason,
        digest=result.digest,
        key_id=cert.key_id,
        issued_at=cert.payload.get("issued_at", ""),
        changed_fields=result.changed_fields,
        payload=submitted,
    )


async def verify_full_chain(session: AsyncSession) -> tuple[bool, int | None, int]:
    rows = (
        (await session.execute(select(TransparencyLog).order_by(TransparencyLog.id))).scalars().all()
    )
    entries = [
        {
            "prev_hash": r.prev_hash,
            "digest": r.digest,
            "issued_at": r.issued_at,
            "entry_hash": r.entry_hash,
        }
        for r in rows
    ]
    ok, bad = verify_chain(entries)
    return ok, (rows[bad].id if bad is not None else None), len(rows)
