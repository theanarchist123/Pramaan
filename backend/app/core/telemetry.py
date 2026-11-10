"""Observability: OpenTelemetry traces plus a queryable record of every model call.

* Traces: set OTEL_EXPORTER_OTLP_ENDPOINT (an OTLP/HTTP collector, e.g. Grafana/Tempo/Langfuse's OTEL endpoint) and the
  API's requests and every LLM call become spans. Without it the tracer is a no-op: zero cost, nothing exported.
* `llm_calls` table: one row per live model call (provider, model, tier, schema, latency, tokens, error, and the agent
  run it belonged to), written fire-and-forget so telemetry can never slow or break an agent. GET /v1/admin/agent-runs
  aggregates it per run.

Cost is deliberately NOT computed: prices change and differ per model; tokens are recorded so cost is a query away once
the current price list is confirmed.
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import logging
import uuid
from collections.abc import Iterator
from typing import Any

from app.config import get_settings

log = logging.getLogger("pramaan.telemetry")

# The agent run the current task is working for (set by RunContext) and the token usage of the model call in progress.
current_run_id: contextvars.ContextVar[uuid.UUID | None] = contextvars.ContextVar("current_run_id", default=None)
usage: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar("llm_usage", default=None)

_tracer: Any = None
_pending: set[asyncio.Task] = set()


def setup(app=None) -> bool:
    """Configure OTLP export if an endpoint is set. Returns whether tracing is active."""
    global _tracer
    endpoint = get_settings().otel_exporter_otlp_endpoint.strip()
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": get_settings().otel_service_name}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("pramaan")
        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        log.info("OpenTelemetry tracing enabled -> %s", endpoint)
        return True
    except Exception:  # noqa: BLE001 - observability must never stop the app from starting
        log.exception("could not enable OpenTelemetry tracing")
        return False


@contextlib.contextmanager
def span(name: str, **attrs: Any) -> Iterator[Any]:
    """A trace span (a no-op unless tracing is configured)."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as sp:
        for k, v in attrs.items():
            if v is not None:
                sp.set_attribute(f"pramaan.{k}", v if isinstance(v, (str, int, float, bool)) else str(v))
        yield sp


def note_usage(input_tokens: int | None, output_tokens: int | None) -> None:
    """Called by the model adapters when the provider reports token counts."""
    usage.set({"input": int(input_tokens or 0), "output": int(output_tokens or 0)})


def record_llm_call(*, provider: str, model: str, tier: str, schema: str, latency_ms: int, ok: bool, error: str = "") -> None:
    """Persist one model call, fire-and-forget."""
    u = usage.get() or {}
    run_id = current_run_id.get()

    async def _write() -> None:
        try:
            from app.db import get_sessionmaker
            from app.models import LlmCall

            async with get_sessionmaker()() as session:
                session.add(LlmCall(
                    run_id=run_id, provider=provider, model=model, tier=tier, schema_name=schema, latency_ms=latency_ms,
                    ok=ok, error=error[:300], input_tokens=u.get("input", 0), output_tokens=u.get("output", 0),
                ))
                await session.commit()
        except Exception:  # noqa: BLE001
            log.debug("could not record llm call", exc_info=True)

    try:
        t = asyncio.get_running_loop().create_task(_write())
    except RuntimeError:
        return
    _pending.add(t)
    t.add_done_callback(_pending.discard)


async def settle() -> None:
    """Wait for in-flight telemetry writes (tests, shutdown)."""
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)
