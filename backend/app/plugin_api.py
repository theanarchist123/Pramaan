"""The only database door plugins get: a read-only session (and, via app.public_views, only public views)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker


async def get_readonly_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        # First statement of the transaction: Postgres itself now refuses any write, whatever the code does.
        await session.execute(text("SET TRANSACTION READ ONLY"))
        await session.execute(text("SET LOCAL statement_timeout = 3000"))  # a plugin can't hog the database
        try:
            yield session
        finally:
            await session.rollback()
