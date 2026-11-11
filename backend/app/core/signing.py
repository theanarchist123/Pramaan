"""Cryptographic core of Pramaan.

Flow:  verified claims -> canonical JSON -> SHA-256 digest -> Ed25519 signature.
Every issued certificate is also appended to a hash-chained transparency log, so
history cannot be rewritten without breaking every later entry.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PAYLOAD_VERSION = 1
GENESIS_HASH = "0" * 64


# --------------------------------------------------------------------------- #
# Canonicalisation + hashing
# --------------------------------------------------------------------------- #
def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 (Hindi etc. preserved)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def digest_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def build_certificate_payload(
    *,
    cert_id: str,
    profile_id: str,
    full_name: str,
    claims: list[dict[str, Any]],
    issued_at: datetime,
) -> dict[str, Any]:
    """The exact data a certificate vouches for. Only verified claims belong here.

    claims: [{"field": "award", "value": "Padma Shri 2021", "status": "document"}, ...]
    """
    ordered = sorted(
        ({"field": c["field"], "value": c["value"], "status": c["status"]} for c in claims),
        key=lambda c: (c["field"], str(c["value"])),
    )
    return {
        "v": PAYLOAD_VERSION,
        "cert_id": cert_id,
        "profile_id": profile_id,
        "full_name": full_name,
        "claims": ordered,
        "issued_at": issued_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def chain_hash(prev_hash: str, digest: str, issued_at_iso: str) -> str:
    """Link a new log entry to the previous one."""
    return hashlib.sha256(f"{prev_hash}|{digest}|{issued_at_iso}".encode()).hexdigest()


def verify_chain(entries: list[dict[str, str]]) -> tuple[bool, int | None]:
    """entries oldest->newest, each {prev_hash, digest, issued_at, entry_hash}.

    Returns (ok, index_of_first_bad_entry).
    """
    prev = GENESIS_HASH
    for i, e in enumerate(entries):
        if e["prev_hash"] != prev:
            return False, i
        if chain_hash(e["prev_hash"], e["digest"], e["issued_at"]) != e["entry_hash"]:
            return False, i
        prev = e["entry_hash"]
    return True, None


# --------------------------------------------------------------------------- #
# Signer
# --------------------------------------------------------------------------- #
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Signer:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key
        self._public = private_key.public_key()

    @classmethod
    def load(cls, seed_b64: str = "", key_path: Path | None = None) -> "Signer":
        """Load from env seed, else from key file, else generate and persist (dev)."""
        if seed_b64:
            return cls(Ed25519PrivateKey.from_private_bytes(_b64d(seed_b64)))
        if key_path is not None:
            if key_path.exists():
                return cls(Ed25519PrivateKey.from_private_bytes(_b64d(key_path.read_text().strip())))
            key = Ed25519PrivateKey.generate()
            seed = key.private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_text(_b64e(seed))
            return cls(key)
        return cls(Ed25519PrivateKey.generate())

    @property
    def public_key_b64(self) -> str:
        raw = self._public.public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return _b64e(raw)

    @property
    def key_id(self) -> str:
        return hashlib.sha256(_b64d(self.public_key_b64)).hexdigest()[:16]

    def sign_digest(self, digest_hex: str) -> str:
        return _b64e(self._private.sign(bytes.fromhex(digest_hex)))

    def sign_raw(self, data: bytes) -> bytes:
        """Sign arbitrary bytes (used by the Verifiable Credential proofs). The key itself never leaves this object (I-6)."""
        return self._private.sign(data)


def verify_signature(digest_hex: str, signature_b64: str, public_key_b64: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(public_key_b64)).verify(
            _b64d(signature_b64), bytes.fromhex(digest_hex)
        )
        return True
    except (InvalidSignature, ValueError):
        return False


# --------------------------------------------------------------------------- #
# Verification with tamper diagnosis
# --------------------------------------------------------------------------- #
@dataclass
class VerifyResult:
    valid: bool
    digest: str
    reason: str
    changed_fields: list[str] = field(default_factory=list)


def _flatten(payload: dict[str, Any]) -> dict[str, str]:
    flat = {k: json.dumps(v, ensure_ascii=False) for k, v in payload.items() if k != "claims"}
    for i, c in enumerate(payload.get("claims", [])):
        flat[f"claims[{c['field']}#{i}]"] = json.dumps(
            [c["value"], c["status"]], ensure_ascii=False
        )
    return flat


def diff_payloads(original: dict[str, Any], submitted: dict[str, Any]) -> list[str]:
    """Human-readable list of which parts of a payload differ."""
    a, b = _flatten(original), _flatten(submitted)
    changed = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    return changed


def verify_payload(
    submitted: dict[str, Any],
    signature_b64: str,
    public_key_b64: str,
    original: dict[str, Any] | None = None,
) -> VerifyResult:
    """Check a payload against its signature. If `original` is supplied and the check
    fails, report exactly which fields were altered (powers the "Try to tamper" UI)."""
    digest = digest_payload(submitted)
    if verify_signature(digest, signature_b64, public_key_b64):
        return VerifyResult(True, digest, "Signature valid; content unchanged since issuance.")
    changed = diff_payloads(original, submitted) if original is not None else []
    return VerifyResult(
        False,
        digest,
        "Signature does not match this content — it was edited after issuance.",
        changed,
    )
