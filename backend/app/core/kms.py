"""An external-key signer (KMS/HSM): the private key lives in the provider and never enters this process (invariant I-6).

`KmsSigner` has the same four members the rest of the code uses from `core.signing.Signer` (`sign_digest`, `sign_raw`, `public_key_b64`, `key_id`), so nothing else changes.
It refuses to start if the provider's signatures do not verify with the provider's own public key, and it checks EVERY signature before returning it, so a wrong key, a
garbled answer or an outage becomes an error, never a bad certificate and never a silent fallback to a different key.

Providers (facts read from their documentation on 2026-11-12, not exercised here: this repository has no cloud account):
* AWS KMS: key spec ECC_NIST_EDWARDS25519, algorithm ED25519_SHA_512 with MessageType RAW (pure Ed25519), messages of 0 to 4096 bytes.
* Google Cloud KMS: algorithm EC_SIGN_ED25519 (PureEdDSA over the raw data).
Both are pure Ed25519, so the signatures verify with every existing verifier. Ed25519ph (AWS ED25519_PH_SHA_512) is NOT used: it does not verify as Ed25519.
"""
from __future__ import annotations

import hashlib
from typing import Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.core.signing import _b64e

MAX_MESSAGE = 4096  # AWS KMS limit for RAW messages; the tightest of the two providers


class SigningError(RuntimeError):
    pass


class KmsBackend(Protocol):
    def public_key_raw(self) -> bytes: ...
    def sign(self, message: bytes) -> bytes: ...


class KmsSigner:
    def __init__(self, backend: KmsBackend):
        self._b = backend
        try:
            raw = backend.public_key_raw()
        except SigningError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SigningError(f"could not read the public key from the key service: {type(exc).__name__}") from None
        if len(raw) != 32:
            raise SigningError("the key service did not return an Ed25519 public key (32 bytes)")
        self._raw = raw
        self._public = Ed25519PublicKey.from_public_bytes(raw)
        self.sign_raw(b"pramaan startup self-test")  # raises SigningError if the provider's signatures do not verify

    @property
    def public_key_b64(self) -> str:
        return _b64e(self._raw)

    @property
    def key_id(self) -> str:
        return hashlib.sha256(self._raw).hexdigest()[:16]

    def sign_raw(self, data: bytes) -> bytes:
        if len(data) > MAX_MESSAGE:
            raise ValueError(f"the key service signs at most {MAX_MESSAGE} bytes")
        try:
            sig = self._b.sign(data)
        except SigningError:
            raise
        except Exception as exc:  # noqa: BLE001 - an outage is an error: we never fall back to another key
            raise SigningError(f"the key service could not sign: {type(exc).__name__}") from None
        try:
            self._public.verify(sig, data)
        except (InvalidSignature, ValueError):
            raise SigningError("the key service returned a signature that does not verify with its own public key") from None
        return sig

    def sign_digest(self, digest_hex: str) -> str:
        return _b64e(self.sign_raw(bytes.fromhex(digest_hex)))


class AwsKmsBackend:
    """AWS KMS, key spec ECC_NIST_EDWARDS25519. Needs boto3 and AWS credentials in the environment (an instance role is best)."""

    def __init__(self, key_id: str, region: str = ""):
        self.key_id, self.region, self._client = key_id, region, None

    def _kms(self):
        if self._client is None:
            try:
                import boto3
            except ImportError:
                raise SigningError("boto3 is not installed: install it to use AWS KMS (pip install boto3)") from None
            self._client = boto3.client("kms", **({"region_name": self.region} if self.region else {}))
        return self._client

    def public_key_raw(self) -> bytes:
        der = self._kms().get_public_key(KeyId=self.key_id)["PublicKey"]
        key = serialization.load_der_public_key(der)
        return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def sign(self, message: bytes) -> bytes:
        return self._kms().sign(KeyId=self.key_id, Message=message, MessageType="RAW", SigningAlgorithm="ED25519_SHA_512")["Signature"]


class GcpKmsBackend:
    """Google Cloud KMS, algorithm EC_SIGN_ED25519. `key_version` is the full name:
    projects/P/locations/L/keyRings/R/cryptoKeys/K/cryptoKeyVersions/V. Needs google-cloud-kms and application-default credentials."""

    def __init__(self, key_version: str):
        self.key_version, self._client = key_version, None

    def _kms(self):
        if self._client is None:
            try:
                from google.cloud import kms
            except ImportError:
                raise SigningError("google-cloud-kms is not installed: install it to use Google Cloud KMS (pip install google-cloud-kms)") from None
            self._client = kms.KeyManagementServiceClient()
        return self._client

    def public_key_raw(self) -> bytes:
        pem = self._kms().get_public_key(request={"name": self.key_version}).pem
        key = serialization.load_pem_public_key(pem.encode())
        return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def sign(self, message: bytes) -> bytes:
        return self._kms().asymmetric_sign(request={"name": self.key_version, "data": message}).signature
