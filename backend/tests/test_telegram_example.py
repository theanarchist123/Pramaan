"""The Telegram bot's message logic, run against the REAL API through the real (sync) SDK."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "sdk" / "python"))
sys.path.insert(0, str(ROOT / "examples" / "telegram-bot"))
from handlers import handle_text  # noqa: E402

from tests.test_api_flow import _approved_profile_with_cert  # noqa: E402
from tests.test_directory import _approved  # noqa: E402


@pytest_asyncio.fixture
async def ask(app_instance):
    """`await ask("message")` runs the bot's synchronous handler in a worker thread, while the SDK's HTTP
    calls are executed on the test's own event loop (the one the database connections belong to)."""
    from pramaan import Pramaan

    loop = asyncio.get_running_loop()

    class ToAppOnMainLoop(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            async def go():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_instance), base_url="http://test") as c:
                    r = await c.request(request.method, str(request.url), headers=request.headers, content=request.content)
                    return httpx.Response(r.status_code, headers=r.headers, content=r.content)

            return asyncio.run_coroutine_threadsafe(go(), loop).result(timeout=60)

    sdk = Pramaan(base_url="http://test", http_client=httpx.Client(transport=ToAppOnMainLoop()))

    async def _ask(text: str, site: str = "https://site.example"):
        return await asyncio.to_thread(handle_text, text, sdk, site)

    return _ask


async def test_bot_verifies_codes_in_any_phrasing(ask, client, make_user):
    _, _, _, cert = await _approved_profile_with_cert(client, make_user)
    code = cert["code"]
    for msg in (code, code.lower(), f"/verify {code}", f"hey is {code} real?", f"/verify@PramaanBot {code}"):
        out = await ask(msg)
        assert out and "Authentic" in out and "Meera Iyer" in out, msg
    assert "log entry #" in out


async def test_bot_rejects_unknown_and_malformed(ask):
    out = await ask("PRM-ZZZZZZZZZZ")
    assert "Cannot be verified" in out and "No certificate" in out
    assert "Send a code" in await ask("/verify not-a-code")


async def test_bot_commands_and_silence(ask):
    assert "Pramaan bot" in await ask("/start")
    assert "Pramaan bot" in await ask("/help@PramaanBot")
    assert "What are you looking for" in await ask("/search")
    assert await ask("good morning everyone") is None  # never chatters in group chats
    assert await ask("") is None


async def test_bot_search_links_and_escapes_user_controlled_text(ask, client, make_user):
    admin, _ = await make_user(promote_to_admin=True)
    evil = "<img src=x onerror=alert(1)> Zorblax solar pioneer"
    await _approved(client, make_user, admin, name="Zorblax Tester", sector="Energy", state="Goa",
                    headline=evil, claim="Zorblax solar award")
    out = await ask("/search Zorblax solar pioneer")
    assert "https://site.example/p/" in out
    assert "<img" not in out and "&lt;img" in out  # Telegram HTML mode: user text must be escaped
    assert await ask("/search qqqq zzzz") is not None
