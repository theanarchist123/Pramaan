"""Sending email (one-time codes, invitations). Free hosts such as Render block outbound SMTP ports, so mail can also go over HTTPS (Brevo's API), and every failure is
classified so the operator can see WHY a code email was not sent (blocked network, wrong login, unverified sender...) instead of a bare 502."""
import json
import logging
import smtplib

import httpx
import pytest

from app.config import get_settings
from app.services import mailer, outreach


@pytest.fixture
def cfg(monkeypatch):
    s = get_settings()

    def set_(**kw):
        defaults = dict(smtp_host="", smtp_port=587, smtp_user="", smtp_password="", smtp_from="Pramaan <hello@example.org>", brevo_api_key="")
        for k, v in {**defaults, **kw}.items():
            monkeypatch.setattr(s, k, v)

    return set_


def test_provider_and_configured(cfg):
    cfg()
    assert mailer.provider() == "none" and not mailer.configured()
    cfg(smtp_host="smtp.example.org")
    assert mailer.provider() == "smtp" and mailer.configured()
    cfg(smtp_host="smtp.example.org", brevo_api_key="k")
    assert mailer.provider() == "brevo"  # the HTTPS provider wins when both are set


def test_sender_is_parsed_from_the_from_setting():
    assert mailer.parse_sender("Pramaan <hello@example.org>") == ("Pramaan", "hello@example.org")
    assert mailer.parse_sender("hello@example.org") == ("Pramaan", "hello@example.org")


def _transport(handler, seen):
    def h(req: httpx.Request):
        seen.append(req)
        return handler(req)
    return httpx.MockTransport(h)


def test_brevo_sends_over_https_with_the_key_in_a_header_only(cfg, monkeypatch):
    cfg(brevo_api_key="xkeysib-SECRET")
    seen = []
    monkeypatch.setattr(mailer, "_http", lambda: httpx.Client(transport=_transport(lambda r: httpx.Response(201, json={"messageId": "<1>"}), seen)))
    mailer.send_sync("ann@example.com", "Your code", "Your code is 123456")
    (req,) = seen
    assert req.url.host == "api.brevo.com" and req.headers["api-key"] == "xkeysib-SECRET"
    body = json.loads(req.content)
    assert body["sender"] == {"name": "Pramaan", "email": "hello@example.org"} and body["to"] == [{"email": "ann@example.com"}]
    assert body["subject"] == "Your code" and "123456" in body["textContent"] and "xkeysib" not in req.content.decode()


def test_brevo_refusal_is_a_classified_error_that_never_contains_the_key(cfg, monkeypatch):
    cfg(brevo_api_key="xkeysib-SECRET")
    monkeypatch.setattr(mailer, "_http", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"code": "invalid_parameter", "message": "Sender is not valid"}))))
    with pytest.raises(mailer.MailError) as e:
        mailer.send_sync("ann@example.com", "s", "b")
    assert e.value.reason == "sender_not_verified" and "Sender is not valid" in e.value.detail and "SECRET" not in e.value.detail
    monkeypatch.setattr(mailer, "_http", lambda: httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"message": "Key not found"}))))
    with pytest.raises(mailer.MailError) as e:
        mailer.send_sync("ann@example.com", "s", "b")
    assert e.value.reason == "auth_failed"


def test_brevo_network_failure_is_classified(cfg, monkeypatch):
    cfg(brevo_api_key="k")

    def boom(r):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(mailer, "_http", lambda: httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(mailer.MailError) as e:
        mailer.send_sync("ann@example.com", "s", "b")
    assert e.value.reason == "network_blocked"


@pytest.mark.parametrize("exc,reason", [
    (TimeoutError("timed out"), "network_blocked"),
    (ConnectionRefusedError("refused"), "network_blocked"),
    (OSError(101, "Network is unreachable"), "network_blocked"),
    (smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"), "auth_failed"),
    (smtplib.SMTPSenderRefused(550, b"sender not allowed", "x@y.z"), "sender_not_verified"),
    (smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no such user")}), "recipient_refused"),
    (RuntimeError("something else"), "other"),
])
def test_smtp_failures_are_classified(cfg, monkeypatch, exc, reason):
    cfg(smtp_host="smtp.example.org", smtp_user="u", smtp_password="hunter2-password")

    class Fake:
        def __init__(self, *a, **k):
            raise exc

    monkeypatch.setattr(smtplib, "SMTP", Fake)
    with pytest.raises(mailer.MailError) as e:
        mailer.send_sync("ann@example.com", "s", "b")
    assert e.value.reason == reason and "hunter2" not in e.value.detail


def test_nothing_configured_is_its_own_error(cfg):
    cfg()
    with pytest.raises(mailer.MailError) as e:
        mailer.send_sync("ann@example.com", "s", "b")
    assert e.value.reason == "not_configured"


def test_render_with_smtp_gets_a_clear_warning_and_https_mail_does_not(cfg):
    cfg(smtp_host="smtp.gmail.com", smtp_port=587)
    assert "block" in (mailer.deployment_warning({"RENDER": "true"}) or "").lower()
    assert mailer.deployment_warning({}) is None  # not on Render: nothing to say
    cfg(smtp_host="smtp.gmail.com", brevo_api_key="k")
    assert mailer.deployment_warning({"RENDER": "true"}) is None
    cfg()
    assert mailer.deployment_warning({"RENDER": "true"}) is None


async def test_the_code_email_failure_logs_the_reason_without_the_code_or_the_address(client, make_user, cfg, monkeypatch, caplog):
    cfg(smtp_host="smtp.example.org")
    person, me = await make_user()

    def fail(to, subject, body):
        raise mailer.MailError("network_blocked", "TimeoutError: timed out")

    monkeypatch.setattr(outreach, "_smtp_send", fail)
    caplog.set_level(logging.WARNING)
    r = await client.post("/v1/auth/otp/request", headers=person)
    assert r.status_code == 502 and r.json()["detail"].startswith("Could not send the email right now (network_blocked:") and "BREVO_API_KEY" in r.json()["detail"]
    text = " ".join(rec.getMessage() for rec in caplog.records)
    assert "network_blocked" in text and me["email"] not in text


async def test_staff_can_send_themselves_a_test_email_and_nobody_else_can(client, make_user, cfg, monkeypatch):
    cfg(smtp_host="smtp.example.org")
    sent = []
    monkeypatch.setattr(outreach, "_smtp_send", lambda to, subject, body: sent.append(to))
    admin, me = await make_user(promote_to_admin=True)
    r = await client.post("/v1/admin/email/test", headers=admin)
    assert r.status_code == 200 and r.json() == {"ok": True, "provider": "smtp", "sent_to": mailer.mask(me["email"]), "reason": "", "detail": ""}
    assert sent == [me["email"]]  # only ever to the caller's own address

    def fail(to, subject, body):
        raise mailer.MailError("auth_failed", "SMTPAuthenticationError: 535")

    monkeypatch.setattr(outreach, "_smtp_send", fail)
    bad = (await client.post("/v1/admin/email/test", headers=admin)).json()
    assert bad["ok"] is False and bad["reason"] == "auth_failed" and "535" in bad["detail"]
    person, _ = await make_user()
    assert (await client.post("/v1/admin/email/test", headers=person)).status_code == 403
    assert (await client.post("/v1/admin/email/test")).status_code == 401


def test_user_message_names_the_reason_and_never_leaks_detail():
    e = mailer.MailError("auth_failed", "Brevo said 401: key xkeysib-SECRET refused")
    m = mailer.user_message(e)
    assert m.startswith("Could not send the email right now (auth_failed:") and "SECRET" not in m and "401" not in m
    assert "see the server log" in mailer.user_message(RuntimeError("boom"))
