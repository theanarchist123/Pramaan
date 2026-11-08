from datetime import datetime, timezone

from app.core.signing import (
    GENESIS_HASH,
    Signer,
    build_certificate_payload,
    canonical_json,
    chain_hash,
    digest_payload,
    verify_chain,
    verify_payload,
    verify_signature,
)

ISSUED = datetime(2026, 11, 7, 10, 30, tzinfo=timezone.utc)


def make_payload(**overrides):
    base = dict(
        cert_id="CERT-1",
        profile_id="P-1",
        full_name="Meera Iyer",
        claims=[
            {"field": "sector", "value": "Marine science", "status": "document"},
            {"field": "award", "value": "Sagar Samman 2024", "status": "web"},
        ],
        issued_at=ISSUED,
    )
    base.update(overrides)
    return build_certificate_payload(**base)


def test_canonical_json_is_order_independent_and_keeps_unicode():
    assert canonical_json({"b": 1, "a": "नमस्ते"}) == canonical_json({"a": "नमस्ते", "b": 1})
    assert "नमस्ते".encode() in canonical_json({"a": "नमस्ते"})


def test_claim_order_does_not_change_digest():
    a = make_payload()
    b = make_payload(claims=list(reversed(make_payload()["claims"])))
    assert digest_payload(a) == digest_payload(b)


def test_sign_and_verify_roundtrip():
    signer = Signer.load()
    payload = make_payload()
    digest = digest_payload(payload)
    sig = signer.sign_digest(digest)
    assert verify_signature(digest, sig, signer.public_key_b64)
    result = verify_payload(payload, sig, signer.public_key_b64)
    assert result.valid


def test_tampering_is_detected_and_field_is_named():
    signer = Signer.load()
    original = make_payload()
    sig = signer.sign_digest(digest_payload(original))

    forged = make_payload(
        claims=[
            {"field": "sector", "value": "Marine science", "status": "document"},
            {"field": "award", "value": "Padma Vibhushan 2024", "status": "web"},
        ]
    )
    result = verify_payload(forged, sig, signer.public_key_b64, original=original)
    assert not result.valid
    assert any(c.startswith("claims[award") for c in result.changed_fields)
    assert not any(c.startswith("claims[sector") for c in result.changed_fields)


def test_name_change_detected():
    signer = Signer.load()
    original = make_payload()
    sig = signer.sign_digest(digest_payload(original))
    forged = make_payload(full_name="Someone Else")
    result = verify_payload(forged, sig, signer.public_key_b64, original=original)
    assert not result.valid
    assert "full_name" in result.changed_fields


def test_wrong_key_rejected():
    s1, s2 = Signer.load(), Signer.load()
    payload = make_payload()
    digest = digest_payload(payload)
    assert not verify_signature(digest, s1.sign_digest(digest), s2.public_key_b64)


def test_garbage_signature_does_not_raise():
    signer = Signer.load()
    assert not verify_signature("00" * 32, "not-a-signature", signer.public_key_b64)


def test_signer_persists_key_file(tmp_path):
    path = tmp_path / "signing.key"
    first = Signer.load(key_path=path)
    second = Signer.load(key_path=path)
    assert first.public_key_b64 == second.public_key_b64
    assert first.key_id == second.key_id


def _build_chain(n):
    entries, prev = [], GENESIS_HASH
    for i in range(n):
        iso = f"2026-11-07T10:3{i}:00Z"
        digest = digest_payload({"i": i})
        entry_hash = chain_hash(prev, digest, iso)
        entries.append(
            {"prev_hash": prev, "digest": digest, "issued_at": iso, "entry_hash": entry_hash}
        )
        prev = entry_hash
    return entries


def test_chain_valid():
    assert verify_chain(_build_chain(5)) == (True, None)


def test_chain_detects_rewritten_history():
    entries = _build_chain(5)
    entries[2]["digest"] = digest_payload({"evil": True})
    ok, bad = verify_chain(entries)
    assert not ok and bad == 2


def test_chain_detects_deleted_entry():
    entries = _build_chain(5)
    del entries[1]
    ok, bad = verify_chain(entries)
    assert not ok and bad == 1
