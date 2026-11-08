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


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    get_signer()  # create/load the signing key at boot so failures surface early
    if get_settings().plugins_enabled:
        from app.plugins_loader import load_all

        load_all(app)
    scheduler = None
    if get_settings().outreach_scheduler:
        import asyncio

        from app.services.outreach import scheduler_loop

        scheduler = asyncio.create_task(scheduler_loop())  # sends only messages an admin SCHEDULED
    yield
    if scheduler:
        scheduler.cancel()
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
    allow_origins=[settings.public_base_url, "tauri://localhost", "http://tauri.localhost"],
    # Any local port in development (web dev server, desktop shell, examples).
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
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
    llm = get_llm()
    from app.services.embeddings import get_embedder

    return {"status": "ok", "llm_mode": llm.mode, "llm_provider": llm.provider,
            "models": llm.model_names, "embeddings": get_embedder().kind}


@app.get("/.well-known/pramaan-keys.json", tags=["meta"])
async def public_keys():
    """Anyone can verify a certificate offline using this Ed25519 public key."""
    signer = get_signer()
    return {
        "keys": [
            {
                "kid": signer.key_id,
                "kty": "OKP",
                "crv": "Ed25519",
                "x": signer.public_key_b64,
                "use": "sig",
            }
        ]
    }
