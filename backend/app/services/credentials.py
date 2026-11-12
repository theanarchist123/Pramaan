"""Issue a certificate as a W3C Verifiable Credential 2.0 and publish the revocation status list (TRU-08). See docs/adr/0003."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import vc
from app.core.keys import get_signer, public_keyring
from app.models import Certificate

_STATUS_LOCK_ID = 74_219_051  # serialises index assignment so two requests cannot pick the same free index
STATUS_LIST_ID = "1"
# Pramaan's own terms live under a vocabulary so strict JSON-LD processors do not flag them as undefined.
VOCAB = {"@vocab": "https://pramaan.example/ns/v1#"}


def api_base() -> str:
    return get_settings().api_base_url.rstrip("/")


def did() -> str:
    """did:web:<host> (a port is %3A-encoded, per the did:web method). The method is a CCG draft, not a standard: docs/adr/0003."""
    host = get_settings().did_web_host or urlparse(api_base()).netloc
    return "did:web:" + host.replace(":", "%3A")


def status_url() -> str:
    return f"{api_base()}/v1/status/revocation/{STATUS_LIST_ID}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _multikey(pub_b64url: str) -> str:
    import base64

    raw = base64.urlsafe_b64decode(pub_b64url + "=" * (-len(pub_b64url) % 4))
    return vc.encode_multikey(raw, vc.ED25519_PUBLIC_HEADER)


def did_document() -> dict:
    """The registry's DID document: every published key (current and retired) as a Multikey assertion method."""
    me = did()
    methods = [{"id": f"{me}#{kid}", "type": "Multikey", "controller": me, "publicKeyMultibase": _multikey(pub)} for kid, pub in public_keyring().items()]
    return {
        "@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/multikey/v1"],
        "id": me,
        "verificationMethod": methods,
        "assertionMethod": [m["id"] for m in methods],
    }


def resolve_key(verification_method: str) -> bytes | None:
    """The raw public key for one of OUR verification methods, or None. Used by tests and by self-checks."""
    for m in did_document()["verificationMethod"]:
        if m["id"] == verification_method:
            return vc.decode_multikey(m["publicKeyMultibase"], vc.ED25519_PUBLIC_HEADER)
    return None


async def ensure_status_index(session: AsyncSession, cert: Certificate) -> int:
    if cert.status_index is not None:
        return cert.status_index
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _STATUS_LOCK_ID})
    await session.refresh(cert)
    if cert.status_index is not None:
        return cert.status_index
    used = set((await session.execute(select(Certificate.status_index).where(Certificate.status_index.is_not(None)))).scalars().all())
    if len(used) >= vc.MIN_LIST_BITS:
        raise RuntimeError("the revocation status list is full: a second list is needed")
    while True:
        candidate = secrets.randbelow(vc.MIN_LIST_BITS)  # random on purpose: an index must not reveal when a certificate was issued
        if candidate not in used:
            break
    cert.status_index = candidate
    await session.flush()
    return candidate


def _proof_options(created: datetime) -> dict:
    return {"type": vc.PROOF_TYPE, "cryptosuite": vc.SUITE, "created": _iso(created),
            "verificationMethod": f"{did()}#{get_signer().key_id}", "proofPurpose": "assertionMethod"}


async def credential_for(session: AsyncSession, cert: Certificate) -> dict:
    """The certificate as a signed VC 2.0. Deterministic for a given certificate (the proof time is the issue time)."""
    index = await ensure_status_index(session, cert)
    p = cert.payload
    document = {
        "@context": [vc.CREDENTIALS_CONTEXT, VOCAB],
        "id": f"urn:pramaan:certificate:{quote(cert.code)}",
        "type": ["VerifiableCredential", "PramaanCertificate"],
        "issuer": {"id": did(), "name": "Pramaan"},
        "validFrom": _iso(cert.issued_at),
        "credentialSubject": {
            "name": p.get("full_name", ""),
            "certificateCode": cert.code,
            "claims": [{"field": c["field"], "value": c["value"], "status": c["status"]} for c in p.get("claims", [])],
            "contentDigest": cert.digest,
        },
        "credentialStatus": {
            "id": f"{status_url()}#{index}",
            "type": "BitstringStatusListEntry",
            "statusPurpose": "revocation",
            "statusListIndex": str(index),
            "statusListCredential": status_url(),
        },
    }
    return vc.add_proof(document, _proof_options(cert.issued_at), get_signer().sign_raw)


async def status_list_credential(session: AsyncSession) -> dict:
    """The signed revocation list. A set bit means 'revoked'. Built from the database on each request, so it can never disagree with
    /v1/verify about whether a certificate has been revoked."""
    bits = vc.StatusList()
    revoked = (await session.execute(
        select(Certificate.status_index).where(Certificate.revoked_at.is_not(None), Certificate.status_index.is_not(None))
    )).scalars().all()
    for i in revoked:
        bits.set(i)
    now = datetime.now(timezone.utc)
    document = {
        "@context": [vc.CREDENTIALS_CONTEXT],
        "id": status_url(),
        "type": ["VerifiableCredential", "BitstringStatusListCredential"],
        "issuer": did(),
        "validFrom": _iso(now),
        "credentialSubject": {"id": f"{status_url()}#list", "type": "BitstringStatusList", "statusPurpose": "revocation", "encodedList": bits.encode()},
    }
    return vc.add_proof(document, _proof_options(now), get_signer().sign_raw)
