# Pramaan Telegram bot

A complete third-party app built **only** on the public SDK — no access to our database or internals.
Send it a certificate code and it tells you whether it is genuine; ask it to find verified people.

1. Create a bot with [@BotFather](https://t.me/BotFather) (free) and copy the token.
2. Run the Pramaan API, then:

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...
export PRAMAAN_API_URL=http://localhost:8000
export PRAMAAN_SITE_URL=http://localhost:3100
python bot.py
```

| You send | Bot replies |
|---|---|
| `PRM-ABCDEFGHJK` | ✅ Authentic — name, certified claims, when signed — or ❌ with the reason |
| `/search clean-energy innovators in Karnataka` | up to 3 verified people with *why they matched* |
| `/help` | usage |

`handlers.py` holds all the message logic as pure functions (tested without Telegram); `bot.py` is just the
long-polling transport. Replies use Telegram's HTML mode and escape everything user-controlled.
