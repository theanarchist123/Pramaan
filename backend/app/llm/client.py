"""One door to the LLM for every agent.

Providers (LLM_PROVIDER):
* gemini : Google Gemini via google-genai, JSON-schema structured output (default).
* claude : Anthropic Claude via the Anthropic SDK (kept for when credit is available).
* mock   : deterministic offline heuristics (app/llm/mock.py) — used when LLM_MODE=mock
           or the chosen provider has no key, so the whole product and tests run offline.

Agents never see which provider answered: they pass a pydantic schema and get an instance back.
"""

from __future__ import annotations

import base64
import logging
import time
from functools import lru_cache
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm import mock

log = logging.getLogger("pramaan.llm")
T = TypeVar("T", bound=BaseModel)

_CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Circuit breaker: a model that just failed transiently (overload/timeout) is skipped for a few
# minutes, so one slow model costs one slow call — not 25s on every request.
_COOLDOWN_SECONDS = 180
_down_until: dict[str, float] = {}


class LLMError(Exception):
    """transient=True means 'worth retrying on another model' (overload, rate limit, timeout)."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


class LLMRefusal(LLMError):
    """The model declined / was blocked by a safety filter. Agents treat this as 'needs a human'."""


class LLM:
    def __init__(self) -> None:
        s = get_settings()
        self._s = s
        self.provider = s.llm_provider.lower()
        key = s.gemini_api_key if self.provider == "gemini" else s.anthropic_api_key
        self.live = s.llm_mode == "live" and bool(key)
        self._gemini = None
        self._claude = None
        if s.llm_mode == "live" and not key:
            log.warning("LLM_MODE=live but no %s API key is set; falling back to mock mode", self.provider)
        if self.live and self.provider == "gemini":
            from google import genai
            from google.genai import types

            self._gemini = genai.Client(
                api_key=s.gemini_api_key,
                http_options=types.HttpOptions(timeout=s.llm_timeout_seconds * 1000),
            )
        elif self.live:
            import anthropic

            self._claude = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key, max_retries=3, timeout=120.0)

    @property
    def mode(self) -> str:
        return "live" if self.live else "mock"

    def _chain(self, tier: str) -> list[str]:
        raw = self._s.llm_model_smart if tier == "smart" else self._s.llm_model_fast
        return [m.strip() for m in raw.split(",") if m.strip()]

    @property
    def model_names(self) -> dict[str, list[str]]:
        return {"smart": self._chain("smart"), "fast": self._chain("fast")}

    async def structured(self, schema: type[T], **kw) -> T:
        """Every model call goes through here: traced, timed and recorded (see core/telemetry.py)."""
        from app.core import telemetry

        if not self.live:
            return await self._structured(schema, **kw)
        telemetry.usage.set(None)
        t0 = time.monotonic()
        ok, err = True, ""
        with telemetry.span("llm.structured", provider=self.provider, tier=kw.get("tier", "smart"), schema=schema.__name__):
            try:
                return await self._structured(schema, **kw)
            except Exception as exc:
                ok, err = False, f"{type(exc).__name__}: {exc}"
                raise
            finally:
                telemetry.record_llm_call(
                    provider=self.provider, model=",".join(self._chain(kw.get("tier", "smart")))[:80],
                    tier=kw.get("tier", "smart"), schema=schema.__name__,
                    latency_ms=int((time.monotonic() - t0) * 1000), ok=ok, error=err,
                )

    async def _structured(
        self,
        schema: type[T],
        *,
        system: str,
        user: str | list[dict[str, Any]],
        tier: str = "smart",
        effort: str = "medium",
        max_tokens: int = 4096,
        mock_context: dict[str, Any] | None = None,
    ) -> T:
        if not self.live:
            return mock.respond(schema, mock_context or {})
        chain = self._chain(tier)
        if self.provider != "gemini":
            return await self._claude_structured(schema, chain[0], system, user, effort, max_tokens)

        now = time.monotonic()
        # The last model is never skipped: something must always be tried.
        candidates = [m for m in chain[:-1] if _down_until.get(m, 0) <= now] + [chain[-1]]
        last: LLMError | None = None
        for name in candidates:
            try:
                result = await self._gemini_structured(schema, name, system, user, max_tokens)
                _down_until.pop(name, None)
                return result
            except LLMRefusal:
                raise  # a safety decision is not a capacity problem; don't shop for another model
            except LLMError as exc:
                last = exc
                if not exc.transient:
                    raise
                _down_until[name] = time.monotonic() + _COOLDOWN_SECONDS
                log.warning("model %s unavailable (%s); skipping it for %ds", name, exc, _COOLDOWN_SECONDS)
        assert last is not None
        raise last

    # ------------------------------------------------------------------ Gemini
    @staticmethod
    def _to_parts(user: str | list[dict[str, Any]]):
        """Agents describe multimodal input as content blocks (text / image / document)."""
        from google.genai import types

        if isinstance(user, str):
            return [types.Part.from_text(text=user)]
        parts = []
        for block in user:
            if block.get("type") == "text":
                parts.append(types.Part.from_text(text=block["text"]))
            elif block.get("type") in ("image", "document"):
                src = block["source"]
                parts.append(
                    types.Part.from_bytes(data=base64.b64decode(src["data"]), mime_type=src["media_type"])
                )
        return parts

    async def _gemini_structured(self, schema: type[T], model: str, system: str, user, max_tokens: int) -> T:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            max_output_tokens=max_tokens,
        )
        try:
            resp = await self._gemini.aio.models.generate_content(
                model=model, contents=self._to_parts(user), config=config
            )
        except errors.APIError as exc:
            code = getattr(exc, "code", 0) or 0
            raise LLMError(
                f"Gemini {model} failed ({code}): {str(exc)[:160]}", transient=code in (429, 500, 502, 503, 504)
            ) from exc
        except Exception as exc:  # network errors / client-side timeouts
            raise LLMError(f"Gemini {model} unreachable: {type(exc).__name__}", transient=True) from exc

        block = getattr(getattr(resp, "prompt_feedback", None), "block_reason", None)
        if block:
            raise LLMRefusal(f"Gemini blocked the prompt ({block})")
        cands = resp.candidates or []
        reason = str(getattr(cands[0], "finish_reason", "")) if cands else ""
        if cands and any(k in reason for k in ("SAFETY", "PROHIBITED", "BLOCKLIST", "RECITATION")):
            raise LLMRefusal(f"Gemini declined to answer ({reason})")

        from app.core import telemetry

        meta = getattr(resp, "usage_metadata", None)
        telemetry.note_usage(getattr(meta, "prompt_token_count", 0), getattr(meta, "candidates_token_count", 0))
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        try:
            return schema.model_validate_json(resp.text or "")
        except (ValidationError, ValueError) as exc:
            raise LLMError(f"Gemini returned unparseable output (finish_reason={reason})") from exc

    # ------------------------------------------------------------------ Claude
    async def _claude_structured(self, schema: type[T], model, system, user, effort, max_tokens) -> T:
        import anthropic

        kwargs: dict[str, Any] = dict(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema, output_config={"effort": effort},
        )
        try:
            response = await self._claude.beta.messages.parse(
                **kwargs, betas=[_CLAUDE_FALLBACK_BETA], fallbacks="default"
            )
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(exc).lower() and "beta" not in str(exc).lower():
                raise LLMError(f"Bad request to model: {exc}") from exc
            response = await self._claude.beta.messages.parse(**kwargs)
        except anthropic.APIError as exc:
            raise LLMError(f"Model call failed: {exc}") from exc
        from app.core import telemetry

        telemetry.note_usage(getattr(response.usage, "input_tokens", 0), getattr(response.usage, "output_tokens", 0))
        if response.stop_reason == "refusal":
            raise LLMRefusal("Model declined this request")
        if response.parsed_output is None:
            raise LLMError(f"Model returned no parseable output (stop_reason={response.stop_reason})")
        return response.parsed_output


@lru_cache
def _default_llm() -> LLM:
    return LLM()


_override: LLM | None = None


def get_llm() -> LLM:
    return _override or _default_llm()


def set_llm_override(llm: LLM | None) -> None:
    """Tests inject fakes here."""
    global _override
    _override = llm
