"""A key reported as compromised (the gap the key-rotation runbook named). The rule: signatures by that key are trusted only for log entries made BEFORE the reported time.
The transparency log is the thing an attacker holding only the key cannot forge into, so it is what makes this rule meaningful."""
from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.core import keys
from tests.test_api_flow import _approved_profile_with_cert


def test_the_setting_parses_and_a_malformed_one_is_an_error_not_silence(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "signing_compromised_keys", "")
    assert keys.compromised() == {}
    monkeypatch.setattr(s, "signing_compromised_keys", "abcd1234abcd1234=2026-11-10T00:00:00Z, 1111222233334444=2026-01-01T12:30:00+00:00")
    got = keys.compromised()
    assert got["abcd1234abcd1234"] == datetime(2026, 11, 10, tzinfo=timezone.utc) and len(got) == 2
    for bad in ("nokid", "abcd=notadate", "=2026-01-01T00:00:00Z", "abcd=2026-01-01T00:00:00"):  # a time without a zone is ambiguous: refused
        monkeypatch.setattr(s, "signing_compromised_keys", bad)
        with pytest.raises(RuntimeError, match="SIGNING_COMPROMISED_KEYS"):
            keys.compromised()


async def test_older_certificates_stay_valid_but_nothing_logged_after_the_report_does(client, make_user, monkeypatch):
    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    kid = cert["key_id"]
    s = get_settings()
    monkeypatch.setattr(s, "signing_compromised_keys", f"{kid}=2099-01-01T00:00:00Z")  # reported in the future: this certificate predates it
    assert (await client.get(f"/v1/verify/{cert['code']}")).json()["valid"] is True
    monkeypatch.setattr(s, "signing_compromised_keys", f"{kid}=2000-01-01T00:00:00Z")  # reported in the past: this certificate was logged after it
    bad = (await client.get(f"/v1/verify/{cert['code']}")).json()
    assert bad["valid"] is False and "compromised" in bad["reason"].lower() and bad["signature_ok"] is True


async def test_the_current_key_cannot_issue_once_it_is_marked_compromised(client, make_user, monkeypatch):
    person, _, profile, _ = await _approved_profile_with_cert(client, make_user)
    s = get_settings()
    monkeypatch.setattr(s, "signing_compromised_keys", f"{keys.get_signer().key_id}=2000-01-01T00:00:00Z")
    r = await client.post(f"/v1/profiles/{profile['id']}/certificate", headers=person)
    assert r.status_code == 409 and "compromised" in r.json()["detail"].lower()


async def test_the_published_keys_say_which_key_is_compromised_and_since_when(client, monkeypatch):
    s = get_settings()
    kid = keys.get_signer().key_id
    monkeypatch.setattr(s, "signing_compromised_keys", f"{kid}=2026-11-10T00:00:00Z")
    body = (await client.get("/.well-known/pramaan-keys.json")).json()
    entry = next(k for k in body["keys"] if k["kid"] == kid)
    assert entry["compromised_since"] == "2026-11-10T00:00:00Z"
    monkeypatch.setattr(s, "signing_compromised_keys", "")
    assert "compromised_since" not in next(k for k in (await client.get("/.well-known/pramaan-keys.json")).json()["keys"] if k["kid"] == kid)
