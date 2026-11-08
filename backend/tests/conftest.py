"""Integration fixtures. Needs Postgres+pgvector (docker compose up -d db).

Uses a separate `pramaan_test` database that is dropped and recreated per test session.
"""

from __future__ import annotations

import os

import asyncpg
import httpx
import pytest
import pytest_asyncio

TEST_DB = "pramaan_test"
ADMIN_DSN = "postgresql://pramaan:pramaan@localhost:5432/postgres"
os.environ["DATABASE_URL"] = f"postgresql+asyncpg://pramaan:pramaan@localhost:5432/{TEST_DB}"
os.environ["LLM_MODE"] = "mock"
os.environ["EMBEDDINGS"] = "hash"
os.environ["WEBHOOK_ALLOW_PRIVATE"] = "false"  # tests assert the SSRF guard; never inherit the dev .env flag


async def _db_available() -> bool:
    try:
        conn = await asyncpg.connect(ADMIN_DSN, timeout=3)
        await conn.close()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def app_instance():
    if not await _db_available():
        pytest.skip("Postgres not reachable — run `docker compose up -d db`")
    conn = await asyncpg.connect(ADMIN_DSN)
    await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    await conn.close()

    from app.db import dispose_engine, init_db
    from app.main import app

    await init_db()
    yield app
    await dispose_engine()


@pytest_asyncio.fixture
async def client(app_instance):
    transport = httpx.ASGITransport(app=app_instance)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def make_user(client):
    """Register a user and return (auth headers, user json)."""
    counter = {"n": 0}

    async def _make(role: str = "person", promote_to_admin: bool = False):
        counter["n"] += 1
        email = f"user{counter['n']}-{os.urandom(3).hex()}@example.com"
        r = await client.post(
            "/v1/auth/register",
            json={"email": email, "password": "password123", "name": "Test User", "role": role},
        )
        assert r.status_code == 201, r.text
        data = r.json()
        if promote_to_admin:
            import uuid

            from sqlalchemy import update

            from app.db import get_sessionmaker
            from app.models import User

            async with get_sessionmaker()() as s:
                await s.execute(
                    update(User).where(User.id == uuid.UUID(data["user"]["id"])).values(role="admin")
                )
                await s.commit()
        return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]

    return _make
