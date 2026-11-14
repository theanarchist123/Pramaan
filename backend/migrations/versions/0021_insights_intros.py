"""Profile day counters and introduction requests (v3 Phase 4): two new tables only. Additive; nothing existing is touched."""
from alembic import op

revision = "0021_insights_intros"
down_revision = "0020_view_specs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["profile_day_stats"].create(op.get_bind(), checkfirst=True)
    Base.metadata.tables["intro_requests"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS intro_requests")
    op.execute("DROP TABLE IF EXISTS profile_day_stats")
