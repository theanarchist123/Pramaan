"""llm_calls: one row per live model call (latency, tokens, run) for the admin agent-runs view."""
from alembic import op

revision = "0006_llm_calls"
down_revision = "0005_job_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["llm_calls"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_calls")
