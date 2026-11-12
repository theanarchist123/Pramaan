"""Setu edges (AGT-03): a new table only. Additive; nothing existing is touched."""
from alembic import op

revision = "0016_setu_edges"
down_revision = "0015_email_suppressions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["setu_edges"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS setu_edges")
