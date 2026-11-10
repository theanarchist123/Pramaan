from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


async def migrate() -> None:
    """Apply Alembic migrations (additive and idempotent). Runs in a thread: alembic's env.py starts its own loop."""
    import asyncio

    from alembic import command
    from alembic.config import Config

    from app.config import BACKEND_DIR

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    await asyncio.to_thread(command.upgrade, cfg, "head")


# Dev-only conveniences. Production schemas are owned by Alembic (backend/migrations): run
# `alembic upgrade head` on deploy (the Dockerfile does) — never rely on create_all there.
async def init_db() -> None:
    """Local dev / tests: enable pgvector, create tables and the plugin views straight from the models.
    Outside local development the schema must already be migrated; we only check that it is."""
    from sqlalchemy import text

    from app import models  # noqa: F401  (register tables)
    from app.public_views import VIEW_SQL

    if not get_settings().is_local:
        if get_settings().auto_migrate:
            await migrate()
        async with get_engine().connect() as conn:
            try:
                head = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("Database is not migrated: run `alembic upgrade head` in backend/ (or set AUTO_MIGRATE=true) before starting the API") from exc
        if head is None:
            raise RuntimeError("Database is not migrated: run `alembic upgrade head` in backend/ (or set AUTO_MIGRATE=true) before starting the API")
        return

    async with get_engine().begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in LOCAL_PATCHES:
            await conn.execute(text(stmt))
        for stmt in VIEW_SQL:
            await conn.execute(text(stmt))


# Columns added after a developer's local database was first created (create_all never alters tables).
LOCAL_PATCHES = [
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS decision_basis VARCHAR(12) NOT NULL DEFAULT ''",
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS wikidata_qid VARCHAR(20) NOT NULL DEFAULT ''",
    "ALTER TABLE code_changes ADD COLUMN IF NOT EXISTS run_id UUID",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS kind VARCHAR(30) NOT NULL DEFAULT 'custom'",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS to_email VARCHAR(255) NOT NULL DEFAULT ''",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS error VARCHAR(300) NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_valid_after TIMESTAMPTZ",
]


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine, _sessionmaker = None, None
