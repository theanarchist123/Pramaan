"""Queued sandbox jobs need to point at the agent run the UI follows."""
from alembic import op

revision = "0003_code_change_run_id"
down_revision = "0002_public_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE code_changes ADD COLUMN IF NOT EXISTS run_id UUID")


def downgrade() -> None:
    op.execute("ALTER TABLE code_changes DROP COLUMN IF EXISTS run_id")
