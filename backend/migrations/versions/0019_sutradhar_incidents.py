"""Sutradhar and Nigrani (AGT-01, AGT-13): two additive columns on agent_runs and one new table. Nothing existing is changed or dropped."""
from alembic import op

revision = "0019_sutradhar_incidents"
down_revision = "0018_oauth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(160)")
    op.execute("ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS versions JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_agent_runs_idempotency_key ON agent_runs (idempotency_key)")
    Base.metadata.tables["incidents"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS incidents")
    op.execute("DROP INDEX IF EXISTS ix_agent_runs_idempotency_key")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS versions")
    op.execute("ALTER TABLE agent_runs DROP COLUMN IF EXISTS idempotency_key")
