"""Pramaan Telegram bot (long polling). A third-party app built only on the public SDK.

    export TELEGRAM_BOT_TOKEN=123456:ABC...       # from @BotFather (free)
    export PRAMAAN_API_URL=http://localhost:8000
    export PRAMAAN_SITE_URL=http://localhost:3100  # for profile links in replies
    python bot.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "sdk" / "python"))
from pramaan import Pramaan, PramaanError  # noqa: E402

from handlers import handle_text  # noqa: E402

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API = f"https://api.telegram.org/bot{TOKEN}"
SITE = os.environ.get("PRAMAAN_SITE_URL", "http://localhost:3100")


def main() -> None:
    if not TOKEN:
        sys.exit("Set TELEGRAM_BOT_TOKEN (create a bot with @BotFather).")
    sdk = Pramaan(os.environ.get("PRAMAAN_API_KEY"), base_url=os.environ.get("PRAMAAN_API_URL", "http://localhost:8000"))
    offset = 0
    print("Pramaan bot running. Ctrl+C to stop.")
    with httpx.Client(timeout=40) as tg:
        while True:
            try:
                updates = tg.get(f"{API}/getUpdates", params={"timeout": 30, "offset": offset}).json().get("result", [])
            except httpx.HTTPError:
                time.sleep(3)
                continue
            for u in updates:
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                try:
                    reply = handle_text(msg.get("text", ""), sdk, SITE)
                except PramaanError as e:
                    reply = "The registry is busy, please try again in a minute." if e.status == 429 else "Sorry, something went wrong."
                if reply:
                    tg.post(f"{API}/sendMessage", json={
                        "chat_id": msg["chat"]["id"], "text": reply, "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    })


if __name__ == "__main__":
    main()
