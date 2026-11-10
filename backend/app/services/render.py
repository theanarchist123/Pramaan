"""Renders the certificate page to PDF / PNG with headless Chromium (same HTML the user sees).

Outputs are cached by (code, digest) so repeated downloads are instant and a changed
certificate can never be served from a stale file.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path


from app.config import get_settings

log = logging.getLogger("pramaan.render")
_sem = asyncio.Semaphore(1)  # headless Chromium is heavy (~300 MB); one at a time keeps small hosts alive

CERT_W, CERT_H = 1123, 794  # A4 landscape at 96 dpi


class RenderError(RuntimeError):
    pass


def _cache_path(code: str, digest: str, ext: str) -> Path:
    d = get_settings().data_dir / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{code}-{digest[:12]}.{ext}"


async def render(code: str, digest: str, kind: str) -> Path:
    """kind: 'pdf' | 'png'"""
    assert kind in ("pdf", "png")
    path = _cache_path(code, digest, kind)
    if path.exists():
        return path

    from playwright.async_api import async_playwright

    s = get_settings()
    url = f"{(s.render_base_url or s.public_base_url).rstrip('/')}/certificate/{code}?print=1"
    async with _sem:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(args=["--disable-dev-shm-usage", "--disable-gpu"])
                try:
                    page = await browser.new_page(
                        viewport={"width": CERT_W, "height": CERT_H}, device_scale_factor=2
                    )
                    # Not "networkidle": it flags itself ready
                    # (data-cert-ready) once its photo and QR code have loaded or failed.
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_selector('[data-cert-ready="true"]', timeout=20000)
                    await page.evaluate("document.fonts.ready")
                    if kind == "pdf":
                        await page.pdf(
                            path=str(path), width=f"{CERT_W}px", height=f"{CERT_H}px",
                            print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                        )
                    else:
                        await page.locator("#certificate").screenshot(path=str(path))
                finally:
                    await browser.close()
        except Exception as exc:  # noqa: BLE001
            path.unlink(missing_ok=True)
            log.exception("certificate render failed")
            raise RenderError("Could not render the certificate right now") from exc
    return path
