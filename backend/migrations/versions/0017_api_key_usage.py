"""Per-key daily usage counts (API-10): a new table only. Additive; nothing existing is touched."""
from alembic import op

revision = "0017_api_key_usage"
down_revision = "0016_setu_edges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["api_key_usage"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_key_usage")
