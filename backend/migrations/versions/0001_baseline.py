"""Baseline: the schema as of the move to Alembic.

A snapshot, on purpose: it creates whatever is missing (so it is safe on a database that was built by the old
`create_all`) and adds the columns the old hand-written patches added. From here on, every schema change is its
own explicit revision:  alembic revision -m "what changed"   (or --autogenerate, then read it).
"""
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

PATCHES = [
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS kind VARCHAR(30) NOT NULL DEFAULT 'custom'",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS to_email VARCHAR(255) NOT NULL DEFAULT ''",
    "ALTER TABLE outbox ADD COLUMN IF NOT EXISTS error VARCHAR(300) NOT NULL DEFAULT ''",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS tokens_valid_after TIMESTAMPTZ",
]


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind)  # checkfirst: existing tables are left alone
    for stmt in PATCHES:
        op.execute(stmt)


def downgrade() -> None:
    raise NotImplementedError("The baseline cannot be undone; restore from a backup instead.")
