"""Governed settings and their change history."""
from alembic import op

revision = "0011_governed_settings"
down_revision = "0010_staff_mfa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    for t in ("governed_settings", "governed_setting_changes"):
        Base.metadata.tables[t].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS governed_setting_changes")
    op.execute("DROP TABLE IF EXISTS governed_settings")
