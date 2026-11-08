"""Embeddable "Verified by Pramaan" badges (SVG). Anyone can put one on their website or email
signature; it is rendered live, so a revoked or unknown certificate can never keep showing a green tick."""

from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Profile
from app.services.certificates import get_certificate, verify_certificate

router = APIRouter(prefix="/v1/badge", tags=["developer"])

# SVG can carry script. This badge never needs any, and is meant to be loaded via <img>, but
# defence in depth costs nothing: forbid everything except inline styles.
_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "public, max-age=60",
}
_TONES = {
    "ok": ("#1e7f5c", "#ffffff"),
    "warn": ("#b45309", "#ffffff"),
    "bad": ("#6b6b6b", "#ffffff"),
}


def _svg(label: str, value: str, tone: str) -> str:
    bg, fg = _TONES[tone]
    label_w = 74
    value_w = max(60, int(len(value) * 6.4) + 20)
    w = label_w + value_w
    label, value = escape(label, quote=True), escape(value, quote=True)  # names are user input
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="22" role="img" aria-label="{label}: {value}">'
        f"<title>{label}: {value}</title>"
        f'<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#fff" stop-opacity=".12"/>'
        f'<stop offset="1" stop-opacity=".12"/></linearGradient>'
        f'<clipPath id="r"><rect width="{w}" height="22" rx="4"/></clipPath>'
        f'<g clip-path="url(#r)"><rect width="{label_w}" height="22" fill="#1b2a49"/>'
        f'<rect x="{label_w}" width="{value_w}" height="22" fill="{bg}"/>'
        f'<rect width="{w}" height="22" fill="url(#s)"/></g>'
        f'<g fill="{fg}" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">'
        f'<text x="{label_w / 2}" y="15" fill="#fff">✓ Pramaan</text>'
        f'<text x="{label_w + value_w / 2}" y="15">{value}</text></g></svg>'
    )


def _resp(label: str, value: str, tone: str, code: int = 200) -> Response:
    return Response(_svg(label, value, tone), status_code=code, media_type="image/svg+xml", headers=_HEADERS)


@router.get("/certificate/{code}.svg")
async def certificate_badge(code: str, session: AsyncSession = Depends(get_session)):
    code = code.strip().upper()
    if await get_certificate(session, code) is None:
        return _resp("Pramaan", "not found", "bad", 404)
    result = await verify_certificate(session, code)
    if result.valid:
        return _resp("Pramaan", f"verified · {code}", "ok")
    if result.revoked:
        return _resp("Pramaan", "revoked", "warn")
    return _resp("Pramaan", "invalid", "bad")


@router.get("/profile/{slug}.svg")
async def profile_badge(slug: str, session: AsyncSession = Depends(get_session)):
    p = (await session.execute(select(Profile).where(Profile.slug == slug))).scalar_one_or_none()
    if p is None or p.status != "approved":
        return _resp("Pramaan", "not listed", "bad", 404)
    verified = sum(1 for c in p.claims if c.status != "self")
    return _resp("Pramaan", f"verified · {verified} claim{'s' if verified != 1 else ''}", "ok")
