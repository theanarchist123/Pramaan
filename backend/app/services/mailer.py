"""Sending email: one place, two providers, and failures that say why.

* smtp  : the classic route (SMTP_HOST/PORT/USER/PASSWORD). Many free hosts (Render's free plan among them) block outbound SMTP ports, which shows up as a timeout.
* brevo : over HTTPS (port 443, never blocked) through Brevo's transactional email API (BREVO_API_KEY). Their free plan needs no domain: verify the sender address once
          in Brevo and set SMTP_FROM to it ("Pramaan <you@gmail.com>").
If a Brevo key is set it is used; otherwise SMTP.

Every failure becomes a MailError with a short reason code (network_blocked, auth_failed, sender_not_verified, recipient_refused, rejected, not_configured, other) and a
safe detail (never a password, API key or message body). Callers log the reason, so "could not send the email" on the website can be traced to its cause in the server log.
"""
from __future__ import annotations

import logging
import smtplib
import socket
from email.message import EmailMessage
from email.utils import parseaddr

import httpx

from app.config import get_settings

log = logging.getLogger("pramaan.mail")
BREVO_URL = "https://api.brevo.com/v3/smtp/email"


class MailError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail = reason, detail


def provider() -> str:
    s = get_settings()
    return "brevo" if s.brevo_api_key else "smtp" if s.smtp_host else "none"


def configured() -> bool:
    return provider() != "none"


def mask(email: str) -> str:
    local, at, domain = (email or "").partition("@")
    return f"{local[:2]}***@{domain}" if at and local and domain else "***"


def parse_sender(value: str) -> tuple[str, str]:
    name, addr = parseaddr(value or "")
    return (name or "Pramaan", addr)


def _safe(exc: BaseException, limit: int = 200) -> str:
    msg = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {msg}"[:limit]


def _http() -> httpx.Client:
    return httpx.Client(timeout=15.0, follow_redirects=False)


def _send_brevo(to: str, subject: str, body: str) -> None:
    s = get_settings()
    name, addr = parse_sender(s.smtp_from)
    try:
        with _http() as c:
            r = c.post(BREVO_URL, headers={"api-key": s.brevo_api_key, "accept": "application/json"},
                       json={"sender": {"name": name, "email": addr}, "to": [{"email": to}], "subject": subject, "textContent": body})
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        raise MailError("network_blocked", _safe(exc)) from None
    except httpx.HTTPError as exc:
        raise MailError("other", _safe(exc)) from None
    if r.status_code in (200, 201, 202):
        return
    try:
        message = str(r.json().get("message", ""))[:160]
    except ValueError:
        message = ""
    if r.status_code in (401, 403):
        raise MailError("auth_failed", f"Brevo said {r.status_code}: {message or 'the API key was refused'}")
    if "sender" in message.lower():
        raise MailError("sender_not_verified", f"Brevo said {r.status_code}: {message}")
    raise MailError("rejected", f"Brevo said {r.status_code}: {message}")


def _send_smtp(to: str, subject: str, body: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError("auth_failed", f"SMTPAuthenticationError {exc.smtp_code}") from None
    except smtplib.SMTPSenderRefused as exc:
        raise MailError("sender_not_verified", f"SMTPSenderRefused {exc.smtp_code}") from None
    except smtplib.SMTPRecipientsRefused:
        raise MailError("recipient_refused", "the receiving server refused this address") from None
    except (TimeoutError, ConnectionError, socket.timeout, socket.gaierror, OSError) as exc:
        # A timeout or refusal reaching the mail server almost always means the host blocks outbound SMTP.
        raise MailError("network_blocked", _safe(exc)) from None
    except Exception as exc:  # noqa: BLE001
        raise MailError("other", _safe(exc)) from None


def send_sync(to: str, subject: str, body: str) -> None:
    """Send one plain-text email with the configured provider. Raises MailError. Blocking: call from a thread."""
    p = provider()
    if p == "none":
        raise MailError("not_configured", "no email provider is set (BREVO_API_KEY or SMTP_HOST)")
    try:
        _send_brevo(to, subject, body) if p == "brevo" else _send_smtp(to, subject, body)
    except MailError as exc:
        log.warning("email to %s failed via %s: %s (%s)", mask(to), p, exc.reason, exc.detail)
        raise


HINTS = {
    "network_blocked": "the server cannot reach the mail service: free hosts such as Render block SMTP, so the server needs BREVO_API_KEY",
    "auth_failed": "the mail service refused the server's login or API key",
    "sender_not_verified": "the sender address is not verified with the mail service",
    "recipient_refused": "the receiving mail server refused this address",
    "rejected": "the mail service rejected the message",
    "not_configured": "no email service is set up on the server",
}


def user_message(exc: BaseException) -> str:
    """What the person sees when a code email could not be sent. The reason code is not sensitive and tells the site owner (who is usually the one testing) what to fix."""
    reason = getattr(exc, "reason", "other")
    return f"Could not send the email right now ({reason}: {HINTS.get(reason, 'an unexpected error; see the server log')})"


def deployment_warning(env: dict[str, str]) -> str | None:
    """A message to print at start-up when the configuration is known not to work where it is running."""
    if env.get("RENDER") == "true" and provider() == "smtp":
        return ("email: SMTP is configured, but this looks like Render, whose free web services block outbound SMTP ports (25, 465, 587): mail will time out. "
                "Set BREVO_API_KEY (HTTPS) instead, or move to a paid Render instance.")
    return None
