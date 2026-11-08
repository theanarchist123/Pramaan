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
    # "auto" tries the local multilingual model, falling back to a lexical hash; "hash" forces it.
    embeddings: str = "auto"

    database_url: str = "postgresql+asyncpg://pramaan:pramaan@localhost:5432/pramaan"

    @model_validator(mode="after")
    def _no_default_secret_in_public(self):
        """The placeholder JWT secret is public (it is in the source). Anyone could forge logins with it,
        so a deployment on a real address must set its own."""
        local = self.public_base_url.startswith(("http://localhost", "http://127.0.0.1"))
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
    jwt_secret: str = _DEV_JWT_SECRET
    signing_key_b64: str = ""

    unsplash_access_key: str = ""
    # Wikimedia's bot policy requires a real contact (email or URL) in the User-Agent.
    # Without one, lookups are refused (403) and Pariksha simply finds no public evidence.
    wikimedia_contact: str = ""

    @property
    def data_dir(self) -> Path:
        path = BACKEND_DIR / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
