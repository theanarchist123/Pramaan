"""Identity binding (TRU-04): two ways to show a person controls something that ties them to an institution. Neither proves WHO they are; they
add evidence a reviewer can weigh. Phone OTP is not built (it needs an SMS provider)."""

from __future__ import annotations

import uuid

import pytest

from app.services import identity
from tests.test_review_workbench import escalated_case, staff


async def _profile(client, person):
    return (await client.post("/v1/profiles", headers=person, json={"full_name": f"Bind {uuid.uuid4().hex[:6]}", "consent_public_listing": True})).json()


# ---------------------------------------------------------------------------------- institutional email
async def test_a_free_mail_address_is_refused_because_it_says_nothing_about_an_institution(client, make_user):
    person, _ = await make_user()
    p = await _profile(client, person)
    for addr in ("someone@gmail.com", "someone@Yahoo.co.in", "someone@outlook.com", "not-an-email", "a@b", "x@127.0.0.1"):
        r = await client.post(f"/v1/profiles/{p['id']}/identity/email", headers=person, json={"email": addr})
        assert r.status_code == 422, addr


async def test_proving_you_control_an_email_at_an_institution_binds_that_domain_and_nothing_else(client, make_user):
    person, _ = await make_user()
    p = await _profile(client, person)
    sent = (await client.post(f"/v1/profiles/{p['id']}/identity/email", headers=person, json={"email": "meera@uni.example"})).json()
    assert sent["sent"] is True and len(sent["dev_code"]) == 6 and sent["domain"] == "uni.example"

    bad = "000000" if sent["dev_code"] != "000000" else "111111"
    assert (await client.post(f"/v1/profiles/{p['id']}/identity/email/confirm", headers=person, json={"code": bad})).status_code == 400
    ok = await client.post(f"/v1/profiles/{p['id']}/identity/email/confirm", headers=person, json={"code": sent["dev_code"]})
    assert ok.status_code == 200 and ok.json()["kind"] == "domain_email" and ok.json()["subject"] == "uni.example"

    listed = (await client.get(f"/v1/profiles/{p['id']}/identity", headers=person)).json()
    assert [b["subject"] for b in listed["verified"]] == ["uni.example"]
    assert "meera" not in str(listed) and "meera@" not in str(listed)  # the address itself is never stored or returned
    assert (await client.post(f"/v1/profiles/{p['id']}/identity/email/confirm", headers=person, json={"code": sent["dev_code"]})).status_code == 400  # one use


async def test_too_many_wrong_codes_lock_that_challenge(client, make_user):
    person, _ = await make_user()
    p = await _profile(client, person)
    sent = (await client.post(f"/v1/profiles/{p['id']}/identity/email", headers=person, json={"email": "a@uni.example"})).json()
    bad = "000000" if sent["dev_code"] != "000000" else "111111"
    codes = [(await client.post(f"/v1/profiles/{p['id']}/identity/email/confirm", headers=person, json={"code": bad})).status_code for _ in range(6)]
    assert codes[-1] == 400
    late = await client.post(f"/v1/profiles/{p['id']}/identity/email/confirm", headers=person, json={"code": sent["dev_code"]})
    assert late.status_code == 400  # even the right code no longer works: request a new one


# ---------------------------------------------------------------------------------- a code on a page you control
async def test_a_code_on_a_page_you_control_binds_that_host_only_when_the_page_really_contains_it(client, make_user, monkeypatch):
    person, _ = await make_user()
    p = await _profile(client, person)
    started = (await client.post(f"/v1/profiles/{p['id']}/identity/page", headers=person, json={"url": "https://faculty.example.edu/people/meera"})).json()
    token = started["token"]
    assert token.startswith("pramaan-verify-") and started["host"] == "faculty.example.edu"

    async def page_without(url):
        return "<html>Meera Iyer, marine biology</html>"

    monkeypatch.setattr(identity, "fetch_page_text", page_without)
    assert (await client.post(f"/v1/profiles/{p['id']}/identity/page/check", headers=person)).status_code == 409  # not there: nothing bound

    async def page_with(url):
        assert url == "https://faculty.example.edu/people/meera"  # it fetches the page the person named, nothing else
        return f"<html>Meera Iyer <!-- {token} --></html>"

    monkeypatch.setattr(identity, "fetch_page_text", page_with)
    done = await client.post(f"/v1/profiles/{p['id']}/identity/page/check", headers=person)
    assert done.status_code == 200 and done.json()["kind"] == "page_code" and done.json()["subject"] == "faculty.example.edu"


def test_the_page_fetch_refuses_private_and_internal_addresses(monkeypatch):
    import asyncio

    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "webhook_allow_private", False)
    for url in ("http://127.0.0.1/x", "https://localhost/x", "http://169.254.169.254/latest/meta-data", "file:///etc/passwd", "ftp://example.com/x"):
        with pytest.raises(identity.UnsafeTarget):
            asyncio.run(identity.fetch_page_text(url))


# ---------------------------------------------------------------------------------- who can do it, and who sees it
async def test_only_the_owner_can_bind_and_reviewers_see_verified_bindings_on_the_case(client, make_user, monkeypatch):
    person, profile, item = await escalated_case(client, make_user, monkeypatch)
    stranger, _ = await make_user()
    assert (await client.post(f"/v1/profiles/{profile['id']}/identity/email", headers=stranger, json={"email": "x@uni.example"})).status_code in (403, 404)

    sent = (await client.post(f"/v1/profiles/{profile['id']}/identity/email", headers=person, json={"email": "meera@uni.example"})).json()
    await client.post(f"/v1/profiles/{profile['id']}/identity/email/confirm", headers=person, json={"code": sent["dev_code"]})
    await client.post(f"/v1/profiles/{profile['id']}/identity/page", headers=person, json={"url": "https://faculty.example.edu/m"})  # started, never confirmed

    reviewer, _ = await staff(make_user, "reviewer")
    detail = (await client.get(f"/v1/admin/review/{item['id']}", headers=reviewer)).json()
    assert [(b["kind"], b["subject"]) for b in detail["bindings"]] == [("domain_email", "uni.example")]  # the unconfirmed page is NOT listed as verified


def test_the_test_suite_cannot_send_real_email_even_if_the_developers_env_has_smtp():
    """Added after a test leaked a few real emails through the developer's configured SMTP account."""
    from app.config import get_settings
    from app.services import outreach

    assert get_settings().smtp_host == ""
    with pytest.raises(AssertionError, match="real email"):
        outreach._smtp_send("someone@example.com", "subject", "body")
