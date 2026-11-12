"""Verifiable Credentials 2.0 (TRU-08). The conformance tests use the W3C's own published eddsa-jcs-2022 worked example
(https://www.w3.org/TR/vc-di-eddsa/, Examples 30-39, read 2026-11-11). Ed25519 is deterministic, so the signature must match exactly."""

from __future__ import annotations

import copy
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import vc

SECRET = "z3u2en7t5LR2WtQH5PfFqMqwVHBeXouLzo6haApm8XHqvjxq"
PUBLIC = "z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2"
DOC = {
    "@context": ["https://www.w3.org/ns/credentials/v2", "https://www.w3.org/ns/credentials/examples/v2"],
    "id": "urn:uuid:58172aac-d8ba-11ed-83dd-0b3aef56cc33",
    "type": ["VerifiableCredential", "AlumniCredential"],
    "name": "Alumni Credential",
    "description": "A minimum viable example of an Alumni Credential.",
    "issuer": "https://vc.example/issuers/5678",
    "validFrom": "2023-01-01T00:00:00Z",
    "credentialSubject": {"id": "did:example:abcdefgh", "alumniOf": "The School of Examples"},
}
VM = f"did:key:{PUBLIC}#{PUBLIC}"
OPTIONS = {"type": "DataIntegrityProof", "cryptosuite": "eddsa-jcs-2022", "created": "2023-02-24T23:36:38Z",
           "verificationMethod": VM, "proofPurpose": "assertionMethod"}
CANONICAL_DOC_HASH = "59b7cb6251b8991add1ce0bc83107e3db9dbbab5bd2c28f687db1a03abc92f19"
CANONICAL_OPTIONS_HASH = "66ab154f5c2890a140cb8388a22a160454f80575f6eae09e5a097cabe539a1db"
PROOF_VALUE = "z2HnFSSPPBzR36zdDgK8PbEHeXbR56YF24jwMpt3R1eHXQzJDMWS93FCzpvJpwTWd3GAVFuUfjoJdcnTMuVor51aX"


def test_base58_and_multikey_round_trip_the_w3c_keys():
    seed = vc.decode_multikey(SECRET, vc.ED25519_PRIVATE_HEADER)
    pub = vc.decode_multikey(PUBLIC, vc.ED25519_PUBLIC_HEADER)
    assert len(seed) == 32 and len(pub) == 32
    assert vc.encode_multikey(pub, vc.ED25519_PUBLIC_HEADER) == PUBLIC
    assert vc.encode_multikey(seed, vc.ED25519_PRIVATE_HEADER) == SECRET
    # the public key really is the one derived from the secret
    derived = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes_raw()
    assert derived == pub
    for raw in (b"", b"\x00", b"\x00\x00abc", b"hello world"):
        assert vc.b58decode(vc.b58encode(raw)) == raw


def test_the_canonical_hashes_match_the_published_example():
    assert hashlib.sha256(vc.jcs(DOC).encode()).hexdigest() == CANONICAL_DOC_HASH
    config = {**OPTIONS, "@context": DOC["@context"]}
    assert hashlib.sha256(vc.jcs(config).encode()).hexdigest() == CANONICAL_OPTIONS_HASH


def test_signing_reproduces_the_w3c_proof_value_exactly_and_it_verifies():
    seed = vc.decode_multikey(SECRET, vc.ED25519_PRIVATE_HEADER)
    key = Ed25519PrivateKey.from_private_bytes(seed)
    signed = vc.add_proof(DOC, OPTIONS, key.sign)
    assert signed["proof"]["proofValue"] == PROOF_VALUE
    assert signed["proof"]["@context"] == DOC["@context"]
    assert vc.verify_proof(signed, lambda vm: vc.decode_multikey(PUBLIC, vc.ED25519_PUBLIC_HEADER)) is True


def _signed():
    key = Ed25519PrivateKey.from_private_bytes(vc.decode_multikey(SECRET, vc.ED25519_PRIVATE_HEADER))
    return vc.add_proof(DOC, OPTIONS, key.sign)


def _resolve(vm):
    return vc.decode_multikey(PUBLIC, vc.ED25519_PUBLIC_HEADER)


@pytest.mark.parametrize("edit", ["name", "subject", "issuer", "proof_created", "proof_purpose", "proof_value", "drop_proof"])
def test_any_change_to_the_document_or_proof_fails_verification(edit):
    s = copy.deepcopy(_signed())
    if edit == "name":
        s["name"] = "Different"
    elif edit == "subject":
        s["credentialSubject"]["alumniOf"] = "Elsewhere"
    elif edit == "issuer":
        s["issuer"] = "https://evil.example/"
    elif edit == "proof_created":
        s["proof"]["created"] = "2024-01-01T00:00:00Z"
    elif edit == "proof_purpose":
        s["proof"]["proofPurpose"] = "authentication"
    elif edit == "proof_value":
        s["proof"]["proofValue"] = s["proof"]["proofValue"][:-2] + "11"
    else:
        del s["proof"]
    assert vc.verify_proof(s, _resolve) is False


def test_an_unknown_verification_method_or_wrong_suite_never_verifies_and_never_raises():
    s = _signed()
    assert vc.verify_proof(s, lambda vm: None) is False
    bad = copy.deepcopy(s)
    bad["proof"]["cryptosuite"] = "eddsa-rdfc-2022"
    assert vc.verify_proof(bad, _resolve) is False
    assert vc.verify_proof({"proof": "junk"}, _resolve) is False
    assert vc.verify_proof({}, _resolve) is False


# ---------------------------------------------------------------------------------- status list (Bitstring Status List v1.0)
def test_a_status_list_has_the_minimum_size_sets_bits_left_to_right_and_round_trips():
    bits = vc.StatusList()
    assert bits.size == 131072
    bits.set(0)
    bits.set(7)
    bits.set(131071)
    encoded = bits.encode()
    assert encoded.startswith("u")  # multibase base64url, no padding
    back = vc.StatusList.decode(encoded)
    assert back.get(0) and back.get(7) and back.get(131071) and not back.get(1) and not back.get(8)
    assert back.raw()[0] == 0b10000001  # index 0 is the LEFT-most bit of the first byte
    with pytest.raises(IndexError):
        bits.set(131072)
    with pytest.raises(ValueError):
        vc.StatusList.decode("zNotBase64Url")


# ---------------------------------------------------------------------------------- end to end, over HTTP, like an outside verifier
async def _resolver_from_did_json(client):
    """Build a key resolver ONLY from what the registry publishes at /.well-known/did.json."""
    doc = (await client.get("/.well-known/did.json")).json()
    keys = {m["id"]: vc.decode_multikey(m["publicKeyMultibase"], vc.ED25519_PUBLIC_HEADER) for m in doc["verificationMethod"]}
    return doc, (lambda vm: keys.get(vm))


async def test_a_certificate_is_also_a_verifiable_credential_that_an_outsider_can_check(client, make_user):
    from tests.test_api_flow import _approved_profile_with_cert

    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    doc, resolve = await _resolver_from_did_json(client)
    assert doc["id"].startswith("did:web:") and doc["assertionMethod"]

    r = await client.get(f"/v1/certificates/{cert['code']}/vc")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vc+ld+json")
    cred = r.json()
    assert cred["@context"][0] == "https://www.w3.org/ns/credentials/v2"
    assert {"VerifiableCredential", "PramaanCertificate"} <= set(cred["type"]) and cred["issuer"]["id"] == doc["id"]
    assert cred["proof"]["verificationMethod"] in doc["assertionMethod"]
    assert vc.verify_proof(cred, resolve) is True

    # the credential says what the certificate says
    api_cert = (await client.get(f"/v1/certificates/{cert['code']}")).json()
    assert cred["credentialSubject"]["certificateCode"] == cert["code"]
    assert cred["credentialSubject"]["name"] == api_cert["payload"]["full_name"]
    assert cred["credentialSubject"]["contentDigest"] == api_cert["digest"]

    # stable: a second fetch is byte-identical (Ed25519 is deterministic and the proof time is the issue time)
    assert (await client.get(f"/v1/certificates/{cert['code']}/vc")).json() == cred
    # any edit breaks it
    forged = copy.deepcopy(cred)
    forged["credentialSubject"]["name"] = "Someone Else"
    assert vc.verify_proof(forged, resolve) is False
    assert (await client.get("/v1/certificates/PRM-NOSUCHCODE/vc")).status_code == 404


async def test_the_revocation_list_agrees_with_verify_and_indexes_are_unique(client, make_user):
    from datetime import datetime, timezone

    from sqlalchemy import update

    from app.db import get_sessionmaker
    from app.models import Certificate
    from tests.test_api_flow import _approved_profile_with_cert

    _, _, _, a = await _approved_profile_with_cert(client, make_user)
    _, _, _, b = await _approved_profile_with_cert(client, make_user)
    _, resolve = await _resolver_from_did_json(client)
    ca = (await client.get(f"/v1/certificates/{a['code']}/vc")).json()
    cb = (await client.get(f"/v1/certificates/{b['code']}/vc")).json()
    ia, ib = int(ca["credentialStatus"]["statusListIndex"]), int(cb["credentialStatus"]["statusListIndex"])
    assert ia != ib and 0 <= ia < 131072 and 0 <= ib < 131072
    assert ca["credentialStatus"]["statusListCredential"] == cb["credentialStatus"]["statusListCredential"]

    async def listed():
        r = await client.get("/v1/status/revocation/1")
        sl = r.json()
        assert vc.verify_proof(sl, resolve) is True  # the list itself is signed by the registry
        assert "BitstringStatusListCredential" in sl["type"] and sl["credentialSubject"]["statusPurpose"] == "revocation"
        return vc.StatusList.decode(sl["credentialSubject"]["encodedList"])

    before = await listed()
    assert not before.get(ia) and not before.get(ib)
    async with get_sessionmaker()() as s:
        await s.execute(update(Certificate).where(Certificate.code == a["code"]).values(revoked_at=datetime.now(timezone.utc)))
        await s.commit()
    after = await listed()
    assert after.get(ia) and not after.get(ib)  # exactly the revoked one
    assert (await client.get(f"/v1/verify/{a['code']}")).json()["revoked"] is True  # and /v1/verify says the same
    assert (await client.get(f"/v1/verify/{b['code']}")).json()["revoked"] is False
    assert (await client.get("/v1/status/revocation/2")).status_code == 404
