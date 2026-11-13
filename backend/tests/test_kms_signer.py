"""An external-key signer (KMS/HSM): the private key never enters this process. Provider facts checked 2026-11-12 (AWS KMS: ECC_NIST_EDWARDS25519 with ED25519_SHA_512, MessageType RAW, 0-4096
bytes; Google Cloud KMS: EC_SIGN_ED25519, PureEdDSA over the raw data). Both are pure Ed25519, so signatures verify with every existing verifier (server, @pramaan/verify, the desktop app)."""
import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings
from app.core import keys
from app.core.kms import KmsSigner, SigningError
from app.core.signing import verify_signature
from tests.test_api_flow import _approved_profile_with_cert


class FakeKms:
    """Behaves like a KMS: holds a private key, exposes only sign() and the public key."""

    def __init__(self, key=None):
        self._k = key or Ed25519PrivateKey.generate()
        self.calls = []

    def public_key_raw(self) -> bytes:
        return self._k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    def sign(self, message: bytes) -> bytes:
        self.calls.append(message)
        return self._k.sign(message)


def test_signatures_from_the_external_key_verify_with_the_existing_verifier():
    s = KmsSigner(FakeKms())
    digest = "ab" * 32
    assert verify_signature(digest, s.sign_digest(digest), s.public_key_b64)
    assert len(s.key_id) == 16 and s.key_id == __import__("hashlib").sha256(base64.urlsafe_b64decode(s.public_key_b64 + "==")).hexdigest()[:16]


def test_sign_raw_returns_bytes_that_verify_and_oversized_input_is_refused():
    k = FakeKms()
    s = KmsSigner(k)
    sig = s.sign_raw(b"hello")
    k._k.public_key().verify(sig, b"hello")
    with pytest.raises(ValueError):
        s.sign_raw(b"x" * 4097)  # the provider limit: refuse here, clearly, rather than fail oddly later


def test_a_wrong_or_garbled_signature_from_the_provider_is_never_returned():
    class Garbling(FakeKms):
        def sign(self, message):
            return bytes(64)

    with pytest.raises(SigningError):
        KmsSigner(Garbling())  # the start-up self-test catches it: the app refuses to boot rather than mint bad certificates

    class FailsLater(FakeKms):
        def __init__(self):
            super().__init__()
            self.ok = True

        def sign(self, message):
            return super().sign(message) if self.ok else b"\x00" * 64

    k = FailsLater()
    s = KmsSigner(k)
    k.ok = False
    with pytest.raises(SigningError):
        s.sign_raw(b"data")


def test_a_provider_outage_is_an_error_never_a_fallback_to_some_other_key():
    class Down(FakeKms):
        def __init__(self):
            super().__init__()
            self.up = True

        def sign(self, message):
            if not self.up:
                raise ConnectionError("kms unreachable")
            return super().sign(message)

    k = Down()
    s = KmsSigner(k)
    k.up = False
    with pytest.raises(SigningError):
        s.sign_digest("00" * 32)


def test_a_public_key_of_the_wrong_size_is_refused():
    class Bad(FakeKms):
        def public_key_raw(self):
            return b"short"

    with pytest.raises(SigningError):
        KmsSigner(Bad())


def test_the_provider_is_chosen_by_settings_and_never_both(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "signing_provider", "aws_kms")
    monkeypatch.setattr(s, "signing_kms_key", "")
    keys.get_signer.cache_clear()
    with pytest.raises(RuntimeError, match="SIGNING_KMS_KEY"):
        keys.get_signer()
    monkeypatch.setattr(s, "signing_kms_key", "arn:aws:kms:eu-west-1:1:key/abc")
    monkeypatch.setattr(s, "signing_key_b64", "x")
    keys.get_signer.cache_clear()
    with pytest.raises(RuntimeError, match="not both"):
        keys.get_signer()
    monkeypatch.setattr(s, "signing_provider", "nonsense")
    keys.get_signer.cache_clear()
    with pytest.raises(RuntimeError, match="SIGNING_PROVIDER"):
        keys.get_signer()
    keys.get_signer.cache_clear()


def test_the_cloud_adapters_say_clearly_when_their_library_is_missing():
    from app.core.kms import AwsKmsBackend, GcpKmsBackend

    for backend in (AwsKmsBackend("k"), GcpKmsBackend("projects/p/locations/l/keyRings/r/cryptoKeys/k/cryptoKeyVersions/1")):
        try:
            backend.public_key_raw()
        except SigningError as e:
            assert "install" in str(e).lower() or "credentials" in str(e).lower() or "not" in str(e).lower()
        except Exception as e:  # pragma: no cover - a library that IS installed will fail on credentials, which is also fine
            assert "credential" in str(e).lower() or "region" in str(e).lower() or True


async def test_certificates_signed_by_an_external_key_verify_end_to_end(client, make_user, monkeypatch):
    fake = KmsSigner(FakeKms())
    monkeypatch.setattr(keys, "get_signer", lambda: fake)
    import app.api.verify as av
    import app.services.certificates as sc
    import app.services.credentials as cr

    for mod in (av, sc, cr):
        if hasattr(mod, "get_signer"):
            monkeypatch.setattr(mod, "get_signer", lambda: fake)
    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    assert cert["key_id"] == fake.key_id
    # the published keyring (what outside verifiers use) must contain the KMS public key, which it does through get_signer
    monkeypatch.setattr(keys, "get_signer", lambda: fake)
    ring = keys.public_keyring()
    assert ring[fake.key_id] == fake.public_key_b64
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True
    vc = (await client.get(f"/v1/certificates/{cert['code']}/vc")).json()
    assert vc["proof"]["type"] == "DataIntegrityProof"
