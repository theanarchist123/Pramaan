from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


_DEV_JWT_SECRET = "dev-only-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # "development" = running on your machine (even if PUBLIC_BASE_URL/DATABASE_URL point at a live site);
    # "production" = a deployment; "auto" (default) decides from PUBLIC_BASE_URL.
    environment: str = "auto"
    llm_provider: str = "gemini"  # "gemini" | "claude"
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    llm_mode: str = "mock"  # "live" | "mock"
    # Comma-separated chains: tried in order when a model is overloaded (503), rate-limited (429)
    # or slow (timeout). The newest models are great but flap under demand, so the chain ends on
    # the lite model that has been consistently available.
    llm_model_smart: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-3.1-flash-lite"
    llm_model_fast: str = "gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    llm_timeout_seconds: int = 25
    # Webhooks may not target private/loopback addresses (SSRF) unless enabled for local dev.
    webhook_allow_private: bool = False
    # AI-written plugins (Shilpkar). Off unless enabled: approved plugins run inside the API process.
    plugins_enabled: bool = False
    plugins_dir: str = ""  # default: backend/plugins
    # Outreach email. Without SMTP_HOST, "sending" is a recorded dry run.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Pramaan <no-reply@pramaan.local>"
    outreach_scheduler: bool = True
    # Background work (webhook retries, scheduled email, AI-code sandbox) runs in a worker loop. By default the
    # API runs it too (WORKER_INLINE=true); in production run `python -m app.worker` separately and set it false.
    worker_inline: bool = True
    # Redis: ONLY for rate-limit counters, short locks, small caches and live-event fan-out (never source of truth).
    # Empty = in-process only. Set but unreachable = in-process fallback plus an alert in the logs.
    redis_url: str = ""
    # Background jobs. "inline" runs them in this process (dev, tests); "procrastinate" queues them in Postgres for
    # `python -m app.worker`, so they survive restarts and run on any replica.
    job_backend: str = "inline"
    job_inline_wait: bool = False  # tests: run the job before the request returns, like a background task
    # OpenTelemetry: an OTLP/HTTP collector URL. Empty = tracing is a no-op.
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "pramaan-api"
    # LangGraph checkpoints (a paused review survives a restart). "postgres" | "memory"
    checkpoint_backend: str = "postgres"
    # Run `alembic upgrade head` when the API starts (outside localhost, where the schema is otherwise only checked).
    # The Docker image already migrates before starting; this is for running the API directly against a real database.
    auto_migrate: bool = False
    # Where the Docker sandbox for AI-written code may run: "inline" (this API process, local dev only) or
    # "worker" (queued; only `python -m app.worker` on a host that has Docker picks it up). "auto" = inline when
    # the site is local, worker otherwise: a deployed API image has no Docker and must not pretend to.
    sandbox_mode: str = "auto"
    # Per-IP limits on login/register/search etc. Tests switch this off (they hammer one address).
    ip_rate_limits: bool = True
    # Applicants must prove they control their email (one-time code) before submitting a profile.
    require_email_verification: bool = True
    # Human approval for every owner's first public listing: Prahari may only auto-approve people who already
    # have a profile a human approved. Until identity checks beyond email exist, keep this on.
    human_approval_first_listing: bool = True
    # Session cookie SameSite: "auto" = lax locally, none (cross-site web + API hosts) in production.
    # Award claims earn the highest trust, so a human confirms them (turn off only once issuers are checked at source).
    award_claims_need_human: bool = True
    # Raising a claim to "confirmed by a reviewer" needs a second person (off by default so existing reviewer workflows keep working; a
    # governed setting, so turning it on or off is itself a four-eyes change).
    claim_override_four_eyes: bool = False
    # Extra issuer names to accept for documents, comma-separated (e.g. "Kerala Sahitya Akademi,Tata Trusts").
    trusted_issuers_extra: str = ""
    # Staff must enrol an authenticator app, and sensitive staff actions need a fresh code (step-up). OFF by default: turn it
    # on only after every staff member has enrolled and saved recovery codes (enrolment and recovery work either way).
    staff_mfa_required: bool = False
    stepup_minutes: int = 10
    # Origin of the separate staff console (apps/admin). Empty = same as PUBLIC_BASE_URL (local dev).
    admin_base_url: str = ""
    admin_session_minutes: int = 30  # staff sessions are short; sign in again
    cookie_samesite: str = "auto"
    # "auto" tries the local multilingual model, falling back to a lexical hash; "hash" forces it.
    embeddings: str = "auto"

    database_url: str = "postgresql+asyncpg://pramaan:pramaan@localhost:5432/pramaan"

    @model_validator(mode="after")
    def _no_default_secret_in_public(self):
        """The placeholder JWT secret is public (it is in the source). Anyone could forge logins with it,
        so a deployment on a real address must set its own."""
        local = self.is_local
        weak = self.jwt_secret == _DEV_JWT_SECRET or self.jwt_secret.startswith("change-me") or len(self.jwt_secret) < 32
        if not local and weak:
            raise ValueError("JWT_SECRET is a public placeholder or too short: set a strong random JWT_SECRET (32+ chars)")
        return self

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        """Hosts (Railway, Heroku…) hand out plain postgres:// URLs; the app needs the asyncpg driver."""
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                v = "postgresql+asyncpg://" + v[len(prefix):]
                break
        # libpq-style `sslmode=require` (what Supabase etc. show) is spelled `ssl=` for asyncpg.
        return v.replace("sslmode=", "ssl=")

    public_base_url: str = "http://localhost:3000"
    # Where the backend itself reaches the web app to render certificates. Differs from public_base_url when
    # both run in containers (e.g. http://web:3000); empty means "same as public_base_url".
    render_base_url: str = ""
    api_base_url: str = "http://localhost:8000"
    # Host of the registry's did:web identity (did:web:<host>), which must serve /.well-known/did.json. Empty = the host of api_base_url.
    did_web_host: str = ""
    jwt_secret: str = _DEV_JWT_SECRET
    signing_key_b64: str = ""
    # Comma-separated base64 public keys of past signing keys, so old certificates keep verifying after rotation.
    signing_retired_public_keys: str = ""

    # Unsplash API for SECTOR imagery on experience pages (spec 4.9, services/images.py): server-side only, hotlinked,
    # attributed, human-curated. Certificates never use it: they use the frozen local photos.
    unsplash_access_key: str = ""
    unsplash_app_name: str = "pramaan"
    # Wikidata as a second public source next to Wikipedia (structured awards/occupation/education; no key needed).
    wikidata_enabled: bool = True
    # Wikimedia's bot policy requires a real contact (email or URL) in the User-Agent.
    # Without one, lookups are refused (403) and Pariksha simply finds no public evidence.
    wikimedia_contact: str = ""

    @property
    def is_local(self) -> bool:
        """Development mode: localhost CORS/origins, SameSite=lax cookie, optional signing key, create_all.
        ENVIRONMENT=development|production forces it; "auto" guesses from PUBLIC_BASE_URL."""
        if self.environment in ("development", "production"):
            return self.environment == "development"
        return self.public_base_url.startswith(("http://localhost", "http://127.0.0.1"))

    @property
    def sandbox_in_api(self) -> bool:
        return self.sandbox_mode == "inline" or (self.sandbox_mode == "auto" and self.is_local)

    @property
    def data_dir(self) -> Path:
        path = BACKEND_DIR / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
