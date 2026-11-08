# Isolated environment for checking AI-written plugins. It is only ever run with:
#   --network none --read-only --cap-drop ALL --memory 512m --cpus 1 --pids-limit 128 --user 10001
# and with the plugin source + a read-only copy of backend/app mounted in. Nothing here can reach
# the database, the host's files, secrets, or the network.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install fastapi pydantic pydantic-settings "sqlalchemy[asyncio]" asyncpg pgvector \
        cryptography pyjwt httpx pytest pytest-asyncio ruff bandit

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox
WORKDIR /work
USER 10001
