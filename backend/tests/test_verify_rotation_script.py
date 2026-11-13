"""scripts/verify_rotation.py against the real app (through the test client), before and after a rotation: it must pass on a healthy rotation and fail on a bad one."""
import asyncio
import base64
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_rotation as vr  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.core.keys import get_signer  # noqa: E402
from tests.test_api_flow import _approved_profile_with_cert  # noqa: E402


def _seed():
    raw = Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def _getter(client):
    async def fetch(path):
        return (await client.get(path)).json()

    paths = {}

    def get(path):
        return paths[path]

    async def load(*ps):
        for p in ps:
            paths[p] = await fetch(p)

    return get, load


async def test_a_healthy_rotation_passes_every_check_and_a_dropped_old_key_fails(client, make_user, monkeypatch):
    _, _, _, old_cert = await _approved_profile_with_cert(client, make_user)
    old_kid, old_pub = get_signer().key_id, get_signer().public_key_b64
    s = get_settings()
    orig_seed, orig_ret = s.signing_key_b64, s.signing_retired_public_keys
    try:
        monkeypatch.setattr(s, "signing_key_b64", _seed())
        monkeypatch.setattr(s, "signing_retired_public_keys", old_pub)
        get_signer.cache_clear()
        get, load = await _getter(client)
        await load("/.well-known/pramaan-keys.json", "/.well-known/did.json", f"/v1/verify/{old_cert['code']}", "/v1/transparency/checkpoint")
        results = vr.run_checks(get, old_cert["code"], old_kid)
        assert all(ok for _, ok, _ in results), [r for r in results if not r[1]]
        # now forget the old public key: the script must notice
        monkeypatch.setattr(s, "signing_retired_public_keys", "")
        get_signer.cache_clear()
        await load("/.well-known/pramaan-keys.json", "/.well-known/did.json", f"/v1/verify/{old_cert['code']}", "/v1/transparency/checkpoint")
        bad = vr.run_checks(get, old_cert["code"], old_kid)
        assert not all(ok for _, ok, _ in bad) and any(n == "old key is still published" and not ok for n, ok, _ in bad)
    finally:
        monkeypatch.setattr(s, "signing_key_b64", orig_seed)
        monkeypatch.setattr(s, "signing_retired_public_keys", orig_ret)
        get_signer.cache_clear()
