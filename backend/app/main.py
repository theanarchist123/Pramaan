from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, agents, apikeys, auth, badges, builder, directory, fields, onboarding, outreach, profiles, verify, webhooks
from app.config import get_settings
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
    import logging

    from app.services.embeddings import get_embedder

    s, log = get_settings(), logging.getLogger("pramaan.startup")
    if s.embeddings.lower() != "hash" and get_embedder().kind == "hash":
        log.warning("Semantic search is DEGRADED: fastembed not available, using the lexical hash fallback")
    if not s.wikimedia_contact.strip():
        log.warning("WIKIMEDIA_CONTACT is empty: Wikipedia may refuse lookups (set an email or project URL)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    _warn_if_degraded()
    get_signer()  # create/load the signing key at boot so failures surface early
    if get_settings().plugins_enabled:
        from app.plugins_loader import load_all

        load_all(app)
    worker = None
    if get_settings().worker_inline:
        import asyncio

        from app.worker import run_forever

        # Webhook retries + scheduled email (only messages an admin SCHEDULED). The Docker sandbox is NOT run
        # here: the API image has no Docker, so those jobs wait for `python -m app.worker`.
        worker = asyncio.create_task(run_forever(sandbox=False))
    yield
    if worker:
        worker.cancel()
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
    allow_origins=[settings.public_base_url],
    # Any local port, only when the site itself is served locally (dev).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if settings.is_local else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (
    auth.router, profiles.router, onboarding.router, agents.router, directory.router,
    verify.router, apikeys.router, webhooks.router, badges.router, fields.router, builder.router, outreach.router, admin.router,
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
