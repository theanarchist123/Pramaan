"""Key rotation dry run (TRU-11): old certificates must keep verifying after the signing key changes, as long as the old PUBLIC key is kept
in the keyring. This is the test behind docs/security/key-rotation.md."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings
from app.core.keys import get_signer
from tests.test_api_flow import _approved_profile_with_cert


def _new_seed_b64() -> str:
    seed = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return base64.urlsafe_b64encode(seed).decode().rstrip("=")


@pytest.fixture
def rotated(monkeypatch):
    """Returns a function that performs a rotation: new current key, the old PUBLIC key moved to the retired list (or not)."""
    settings = get_settings()
    original_seed, original_retired = settings.signing_key_b64, settings.signing_retired_public_keys

    def rotate(keep_old_public_key: bool) -> tuple[str, str]:
        old = get_signer()
        old_kid, old_pub = old.key_id, old.public_key_b64
        monkeypatch.setattr(settings, "signing_key_b64", _new_seed_b64())
        monkeypatch.setattr(settings, "signing_retired_public_keys", old_pub if keep_old_public_key else "")
        get_signer.cache_clear()
        assert get_signer().key_id != old_kid
        return old_kid, get_signer().key_id

    yield rotate
    monkeypatch.setattr(settings, "signing_key_b64", original_seed)
    monkeypatch.setattr(settings, "signing_retired_public_keys", original_retired)
    get_signer.cache_clear()


async def test_after_a_rotation_old_certificates_still_verify_and_new_ones_use_the_new_key(client, make_user, rotated):
    _, _, _, old_cert = await _approved_profile_with_cert(client, make_user)
    assert (await client.get(f"/v1/verify/{old_cert['code']}")).json()["valid"] is True

    old_kid, new_kid = rotated(keep_old_public_key=True)

    again = (await client.get(f"/v1/verify/{old_cert['code']}")).json()
    assert again["valid"] is True and again["key_id"] == old_kid  # signed by the retired key, still genuine

    _, _, _, new_cert = await _approved_profile_with_cert(client, make_user)
    fresh = (await client.get(f"/v1/verify/{new_cert['code']}")).json()
    assert fresh["valid"] is True and fresh["key_id"] == new_kid

    published = {k["kid"] for k in (await client.get("/.well-known/pramaan-keys.json")).json()["keys"]}
    assert {old_kid, new_kid} <= published  # offline verifiers can still fetch BOTH keys

    # the credential form follows the same rule: the DID document lists both keys
    did = (await client.get("/.well-known/did.json")).json()
    assert {m["id"].split("#")[1] for m in did["verificationMethod"]} >= {old_kid, new_kid}


async def test_forgetting_the_old_public_key_is_what_breaks_old_certificates(client, make_user, rotated):
    _, _, _, old_cert = await _approved_profile_with_cert(client, make_user)
    rotated(keep_old_public_key=False)  # the mistake the runbook warns about
    broken = (await client.get(f"/v1/verify/{old_cert['code']}")).json()
    assert broken["valid"] is False  # an old certificate can no longer be shown to be genuine
