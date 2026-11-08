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


# Idempotent patches for databases created before a column existed (create_all never alters tables).
# Real migrations (Alembic) replace this once the schema settles.
SCHEMA_PATCHES = [
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS kind VARCHAR(30) NOT NULL DEFAULT 'custom'",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS to_email VARCHAR(255) NOT NULL DEFAULT ''",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS error VARCHAR(300) NOT NULL DEFAULT ''",
]


async def init_db() -> None:
    """Dev/bootstrap: enable pgvector and create tables. Alembic owns real migrations."""
    from sqlalchemy import text

    from app import models  # noqa: F401  (register tables)

    async with get_engine().begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in SCHEMA_PATCHES:
            await conn.execute(text(stmt))


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine, _sessionmaker = None, None
