"""Per-claim review decisions with reason codes, case locking and SLA columns."""
from alembic import op

revision = "0009_review_decisions"
down_revision = "0008_rbac_audit_approvals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    op.execute("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS assigned_to UUID")
    op.execute("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ")
    op.execute("ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMPTZ")
    Base.metadata.tables["review_decisions"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS review_decisions")
    for col in ("sla_due_at", "locked_until", "assigned_to"):
        op.execute(f"ALTER TABLE review_queue DROP COLUMN IF EXISTS {col}")
