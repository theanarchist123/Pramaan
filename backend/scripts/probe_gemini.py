"""Probe which Gemini models answer for the key in .env (each call has a hard 90s timeout)."""
import re
import sys

from google import genai
from google.genai import types

key = next(l.split("=", 1)[1].strip() for l in open("../.env", encoding="utf-8") if l.startswith("GEMINI_API_KEY="))
client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=90000))
models = sys.argv[1:] or ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"]
for m in models:
    try:
        r = client.models.generate_content(model=m, contents="Reply with the single word: OK")
        print("WORKS ", m, "->", (r.text or "").strip()[:20], flush=True)
    except Exception as e:  # noqa: BLE001
        s = str(e)
        lim = re.search(r"'quota_limit_value': '(\d+)'", s)
        detail = f"quota_limit_value={lim.group(1)}" if lim else re.sub(r"\s+", " ", s)[:150]
        print("FAILED", m, getattr(e, "code", type(e).__name__), detail, flush=True)
