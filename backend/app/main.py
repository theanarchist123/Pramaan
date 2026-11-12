import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import jobs
from app.api import admin, admin_auth, agents, apikeys, auth, badges, builder, directory, fields, images, onboarding, outreach, identity, profiles, registry, review, staff, vc, verify, webhooks
from app.agents.events import relay_from_redis
from app.config import get_settings
from app.core import redis as rd
from app.core.keys import get_signer
from app.db import dispose_engine, init_db
from app.llm.client import get_llm

DESCRIPTION = """
**Pramaan** — *Don't claim it. Prove it.*

A registry of notable people in India where every claim carries evidence and every
certificate is cryptographically signed and publicly verifiable.

* **Public (no key):** directory, profiles, certificate verification, transparency log.
* **Authenticated:** sign in for a JWT, or create an API key (`pk_live_…`) and send it as
  `X-API-Key` or `Authorization: Bearer`. Keys carry scopes and a rate limit.
"""


def _warn_if_degraded() -> None:
    """Fail closed in production: semantic search must not silently become keyword search."""
    import logging

    from app.services.embeddings import get_embedder

    s, log = get_settings(), logging.getLogger("pramaan.startup")
    wanted_model = s.embeddings.lower() != "hash"
    if wanted_model and get_embedder().kind == "hash":
        if not s.is_local:
            raise RuntimeError(
                "Semantic search fell back to the lexical hash (fastembed is missing or failed to load). Refusing to "
                "start in production. Fix the install, or set EMBEDDINGS=hash to choose lexical search deliberately."
            )
        log.warning("Semantic search is DEGRADED: fastembed not available, using the lexical hash fallback")
    if not wanted_model:
        log.warning("EMBEDDINGS=hash: search matches words, not meaning (a deliberate lite configuration)")
    if not s.wikimedia_contact.strip():
        log.warning("WIKIMEDIA_CONTACT is empty: Wikipedia may refuse lookups (set an email or project URL)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    _warn_if_degraded()
    await jobs.start()
    relay = asyncio.create_task(relay_from_redis())
    get_signer()  # create/load the signing key at boot so failures surface early
    if get_settings().plugins_enabled:
        from app.plugins_loader import load_all

        load_all(app)
    worker = queue_worker = None
    if get_settings().worker_inline:
        from app.worker import run_forever

        # Webhook retries + scheduled email (only messages an admin SCHEDULED). The Docker sandbox is NOT run
        # here: the API image has no Docker, so those jobs wait for `python -m app.worker`.
        worker = asyncio.create_task(run_forever(sandbox=False))
        if get_settings().job_backend == "procrastinate":
            queue_worker = asyncio.create_task(jobs.run_worker())  # the Postgres queue, processed by this API too
    yield
    relay.cancel()
    if worker:
        worker.cancel()
    if queue_worker:
        queue_worker.cancel()
    await jobs.stop()
    from app.agents.workflows import dispose_graph

    await dispose_graph()
    await rd.close()
    await dispose_engine()


app = FastAPI(
    title="Pramaan API",
    version="1.0.0",
    description=DESCRIPTION,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in (settings.public_base_url, settings.admin_base_url) if o],
    # Any local port, only when the site itself is served locally (dev).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if settings.is_local else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.core import telemetry  # noqa: E402


@app.middleware("http")
async def conditional_get(request, call_next):
    from app.core import etag

    return await etag.apply(request, call_next)


@app.middleware("http")
async def audit_admin_writes(request, call_next):
    """Every state-changing request under /v1/admin is recorded (who, what, outcome). Handlers that know more (before/after,
    a reason) also write their own richer entries; this is the net that catches everything else."""
    response = await call_next(request)
    if request.url.path.startswith("/v1/admin/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        try:
            from app.core.security import decode_access_token
            from app.db import get_sessionmaker
            from app.deps import SESSION_COOKIE
            from app.services import audit

            auth = request.headers.get("authorization", "")
            token = request.cookies.get(SESSION_COOKIE) or (auth[7:].strip() if auth.lower().startswith("bearer ") else "")
            claims = decode_access_token(token) if token else None
            actor = claims["sub"] if claims and "purpose" not in claims else None
            async with get_sessionmaker()() as s:
                await audit.record(
                    s, actor_id=uuid.UUID(actor) if actor else None, actor_role=(claims or {}).get("role", ""),
                    action=f"http.{request.method}", target_type="path", target_id=request.url.path[:80],
                    after={"status": response.status_code}, ip=request.client.host if request.client else "",
                )
                await s.commit()
        except Exception:  # noqa: BLE001 - auditing must never turn a finished request into an error
            import logging

            logging.getLogger("pramaan.audit").exception("could not write the audit entry")
    return response


telemetry.setup(app)  # OTLP export only if OTEL_EXPORTER_OTLP_ENDPOINT is set

for r in (
    auth.router, profiles.router, onboarding.router, agents.router, directory.router,
    admin_auth.router, review.router, staff.router, images.public, images.admin, verify.router, apikeys.router, webhooks.router, badges.router, fields.router, builder.router, outreach.router, admin.router, registry.router, vc.router, identity.router, outreach.public,
):
    app.include_router(r)


@app.get("/healthz", tags=["meta"])
async def healthz():
    return {"status": "ok"}


@app.get("/.well-known/pramaan-keys.json", tags=["meta"])
async def public_keys():
    """Anyone can verify a certificate offline using this Ed25519 public key."""
    from app.core.keys import public_keyring

    return {
        "keys": [
            {"kid": kid, "kty": "OKP", "crv": "Ed25519", "x": pub, "use": "sig"}
            for kid, pub in public_keyring().items()
        ]
    }
