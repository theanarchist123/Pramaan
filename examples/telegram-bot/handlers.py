"""Message logic for the Pramaan Telegram bot — pure functions, no Telegram or network code, so it is
easy to test. Built ONLY on the public Pramaan SDK (`pramaan`): no database, no server internals.

Replies use Telegram's HTML parse mode, so everything user-controlled is escaped.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any, Protocol

CODE_RE = re.compile(r"\bPRM-[A-Z0-9]{6,12}\b", re.I)

HELP = (
    "<b>Pramaan bot</b> — check who's who, with proof.\n\n"
    "• Send a certificate code like <code>PRM-ABCDEFGHJK</code> to check it\n"
    "• <code>/verify CODE</code> — same thing\n"
    "• <code>/search clean-energy innovators in Karnataka</code> — find verified people (any language)\n"
)


class Registry(Protocol):  # the slice of the SDK this bot uses
    def verify(self, code: str) -> dict[str, Any]: ...
    def search(self, query: str, *, limit: int = ...) -> dict[str, Any]: ...


def verify_reply(sdk: Registry, code: str) -> str:
    v = sdk.verify(code)
    payload = v.get("payload") or {}
    if v["valid"]:
        claims = "\n".join(f"  • {escape(c['value'])}" for c in payload.get("claims", [])[:4])
        return (
            f"✅ <b>Authentic</b> — {escape(payload.get('full_name', ''))}\n{claims}\n\n"
            f"Signed {escape(v['issued_at'])} · log entry #{v.get('log_position')}"
        )
    if v.get("revoked"):
        return "⚠️ <b>Revoked</b> — this certificate was withdrawn by the registry."
    return f"❌ <b>Cannot be verified</b>\n{escape(v['reason'])}\nTreat the document as unverified."


def search_reply(sdk: Registry, query: str, site_url: str) -> str:
    results = sdk.search(query, limit=3)["results"]
    if not results:
        return "No verified person matches that yet."
    lines = []
    for h in results:
        why = "; ".join(h["reasons"][:2])
        lines.append(
            f"<b>{escape(h['full_name'])}</b> — {escape(h['headline'] or h['sector'])} ({escape(h['state'])})\n"
            + (f"  <i>{escape(why)}</i>\n" if why else "")
            + f"  {escape(site_url)}/p/{escape(h['slug'])}"
        )
    return "\n\n".join(lines)


def handle_text(text: str, sdk: Registry, site_url: str = "http://localhost:3100") -> str | None:
    """Return the reply for a chat message, or None to stay silent."""
    text = (text or "").strip()
    if not text:
        return None
    cmd, _, rest = text.partition(" ")
    cmd = cmd.split("@")[0].lower()  # "/search@PramaanBot" in group chats
    rest = rest.strip()
    if cmd in ("/start", "/help"):
        return HELP
    if cmd == "/verify":
        m = CODE_RE.search(rest)
        return verify_reply(sdk, m.group(0)) if m else "Send a code like <code>PRM-ABCDEFGHJK</code>."
    if cmd == "/search":
        return search_reply(sdk, rest, site_url) if len(rest) >= 2 else "What are you looking for? e.g. <code>/search solar researcher</code>"
    m = CODE_RE.search(text)
    if m:  # a bare code is the most common thing people paste
        return verify_reply(sdk, m.group(0))
    return None
