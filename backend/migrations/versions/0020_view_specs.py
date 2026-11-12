"""View specs (AGT-10, tier T2): a new table only. Additive; nothing existing is touched."""
from alembic import op

revision = "0020_view_specs"
down_revision = "0019_sutradhar_incidents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["view_specs"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS view_specs")
