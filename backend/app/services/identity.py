"""Identity binding helpers (TRU-04). A binding shows that a person controls something tied to an institution: an email at its domain, or a
page on its site. It does NOT prove who they are, and nothing here approves anything: a reviewer reads the binding and weighs it.
"""
from __future__ import annotations

import asyncio
import ipaddress
import re
import secrets
from urllib.parse import urlparse

import httpx

from app.services.webhooks import UnsafeURL, check_url, pin_url, resolve_public


class UnsafeTarget(ValueError):
    """The page the person named cannot be fetched safely (private address, wrong scheme, too large...)."""


# Addresses at these domains say nothing about an institution, so they cannot bind one.
FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "ymail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "icloud.com", "me.com", "proton.me", "protonmail.com", "rediffmail.com", "aol.com", "gmx.com", "gmx.net", "mail.com", "yandex.com", "zoho.com",
}
_EMAIL = re.compile(r"^[^@\s]{1,64}@([A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+)$")


def institutional_domain(email: str) -> str | None:
    """The lower-cased domain of an institutional address, or None when it is malformed, an IP literal, or a free-mail provider."""
    m = _EMAIL.match(email.strip())
    if not m:
        return None
    domain = m.group(1).lower()
    try:
        ipaddress.ip_address(domain)
        return None
    except ValueError:
        pass
    return None if domain in FREE_MAIL or len(domain) > 253 else domain


def page_host(url: str) -> str | None:
    """The host of an https URL the person says they control, or None if it is not a plain public-looking https address. (The private-address
    guard runs when the page is actually fetched, because DNS can change after this check.)"""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host or len(url) > 500 or host == "localhost" or parsed.username or parsed.password:
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        return host


def new_token() -> str:
    return f"pramaan-verify-{secrets.token_hex(12)}"


async def fetch_page_text(url: str) -> str:
    """Fetch the page at EXACTLY this URL: private and internal addresses refused, the checked IP pinned (no DNS rebinding), no redirects,
    small responses only. Tests replace this function; the guard test calls it for real with hostile URLs."""
    try:
        check_url(url)
    except UnsafeURL as exc:
        raise UnsafeTarget(str(exc)) from exc
    parsed = urlparse(url)
    try:
        ip = await asyncio.to_thread(resolve_public, parsed.hostname or "", parsed.port or 443)
    except UnsafeURL as exc:
        raise UnsafeTarget(str(exc)) from exc
    pinned, host_header, sni = pin_url(url, ip)
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            r = await client.get(pinned, headers={"Host": host_header, "User-Agent": "PramaanIdentityCheck/1.0"}, extensions={"sni_hostname": sni})
    except httpx.HTTPError as exc:
        raise UnsafeTarget("The page could not be fetched") from exc
    if r.status_code != 200:
        raise UnsafeTarget(f"The page answered {r.status_code}")
    if len(r.content) > 300_000:
        raise UnsafeTarget("The page is too large to check")
    return r.text
