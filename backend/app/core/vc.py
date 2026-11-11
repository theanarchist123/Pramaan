"""W3C Verifiable Credentials 2.0 plumbing (TRU-08): Data Integrity proofs (`eddsa-jcs-2022`), Multikey encoding and Bitstring Status Lists.

Written from the W3C Recommendations (see docs/adr/0003-verifiable-credentials.md) and checked against the vc-di-eddsa worked example in
tests/test_vc.py: the signature reproduces the published proofValue exactly. Pure functions; no I/O, no keys held here (callers pass a
`sign(bytes) -> bytes` callable or a key resolver), so a signing key never enters this module (I-6).
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
from typing import Any, Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ED25519_PUBLIC_HEADER = b"\xed\x01"
ED25519_PRIVATE_HEADER = b"\x80\x26"
SUITE = "eddsa-jcs-2022"
PROOF_TYPE = "DataIntegrityProof"
CREDENTIALS_CONTEXT = "https://www.w3.org/ns/credentials/v2"

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def jcs(value: Any) -> str:
    """RFC 8785 canonical JSON for the values we use (strings, integers, booleans, null, arrays, objects with string keys)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ------------------------------------------------------------------------------------------------ base58btc and Multikey
def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return _B58[0] * (len(raw) - len(raw.lstrip(b"\x00"))) + out


def b58decode(text: str) -> bytes:
    n = 0
    for ch in text:
        n = n * 58 + _B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(text) - len(text.lstrip(_B58[0]))) + body


def encode_multikey(raw: bytes, header: bytes) -> str:
    return "z" + b58encode(header + raw)


def decode_multikey(multibase: str, header: bytes) -> bytes:
    if not multibase.startswith("z"):
        raise ValueError("a Multikey is base58-btc multibase (starts with 'z')")
    data = b58decode(multibase[1:])
    if not data.startswith(header):
        raise ValueError("unexpected Multikey header")
    return data[len(header):]


# ------------------------------------------------------------------------------------------------ eddsa-jcs-2022
def _hash_data(document: dict, proof_config: dict) -> bytes:
    """SHA-256(JCS(proofConfig)) || SHA-256(JCS(document)): the proof-configuration hash comes first (vc-di-eddsa 3.3.4). 64 bytes."""
    return hashlib.sha256(jcs(proof_config).encode()).digest() + hashlib.sha256(jcs(document).encode()).digest()


def add_proof(document: dict, options: dict, sign: Callable[[bytes], bytes]) -> dict:
    """Secure `document` (which must not already carry a proof) with an embedded Data Integrity proof. `options` holds type, cryptosuite,
    created, verificationMethod and proofPurpose; the document's @context is copied into the proof, as the Recommendation requires."""
    if "proof" in document:
        raise ValueError("the document already has a proof")
    if options.get("type") != PROOF_TYPE or options.get("cryptosuite") != SUITE:
        raise ValueError("this implements only DataIntegrityProof / eddsa-jcs-2022")
    config = {**options, **({"@context": document["@context"]} if "@context" in document else {})}
    value = "z" + b58encode(sign(_hash_data(document, config)))
    return {**document, "proof": {**config, "proofValue": value}}


def verify_proof(secured: dict, resolve_key: Callable[[str], bytes | None]) -> bool:
    """True only if the proof is a valid eddsa-jcs-2022 proof over exactly this document. `resolve_key(verificationMethod)` returns the raw
    32-byte Ed25519 public key to trust, or None. Anything malformed returns False; it never raises."""
    try:
        proof = secured["proof"]
        if not isinstance(proof, dict) or proof.get("type") != PROOF_TYPE or proof.get("cryptosuite") != SUITE:
            return False
        value = proof["proofValue"]
        if not value.startswith("z"):
            return False
        public = resolve_key(proof["verificationMethod"])
        if public is None:
            return False
        document = {k: v for k, v in secured.items() if k != "proof"}
        config = {k: v for k, v in proof.items() if k != "proofValue"}
        Ed25519PublicKey.from_public_bytes(public).verify(b58decode(value[1:]), _hash_data(document, config))
        return True
    except (InvalidSignature, KeyError, ValueError, TypeError, AttributeError):
        return False


# ------------------------------------------------------------------------------------------------ Bitstring Status List v1.0
MIN_LIST_BITS = 131072  # 16 KB: the Recommendation's minimum, so one revocation reveals little about who else is in the list


class StatusList:
    """A bitstring where index 0 is the LEFT-most bit of the first byte. `encode()` is multibase base64url (prefix 'u', no padding) of the
    GZIP-compressed bytes, which is what `encodedList` must hold."""

    def __init__(self, data: bytes | None = None, size: int = MIN_LIST_BITS):
        self._bits = bytearray(data if data is not None else b"\x00" * (size // 8))
        if len(self._bits) * 8 < MIN_LIST_BITS:
            raise ValueError("a status list must hold at least 131,072 entries")

    @property
    def size(self) -> int:
        return len(self._bits) * 8

    def _check(self, i: int) -> None:
        if not 0 <= i < self.size:
            raise IndexError("status index out of range")

    def set(self, i: int, on: bool = True) -> None:
        self._check(i)
        mask = 0x80 >> (i % 8)
        self._bits[i // 8] = (self._bits[i // 8] | mask) if on else (self._bits[i // 8] & ~mask & 0xFF)

    def get(self, i: int) -> bool:
        self._check(i)
        return bool(self._bits[i // 8] & (0x80 >> (i % 8)))

    def raw(self) -> bytes:
        return bytes(self._bits)

    def encode(self) -> str:
        return "u" + base64.urlsafe_b64encode(gzip.compress(bytes(self._bits), mtime=0)).decode().rstrip("=")

    @classmethod
    def decode(cls, encoded: str) -> "StatusList":
        if not encoded.startswith("u"):
            raise ValueError("encodedList must be multibase base64url (prefix 'u')")
        try:
            body = encoded[1:]
            return cls(gzip.decompress(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))))
        except (OSError, ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise ValueError("encodedList is not valid") from exc
