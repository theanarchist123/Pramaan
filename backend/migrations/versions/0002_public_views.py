"""Read-only, approved-data-only views that plugins are allowed to query."""
from alembic import op

revision = "0002_public_views"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.public_views import VIEW_SQL

    for stmt in VIEW_SQL:
        op.execute(stmt)


def downgrade() -> None:
    for view in ("public_certificates", "public_evidence", "public_claims", "public_profiles"):
        op.execute(f"DROP VIEW IF EXISTS {view}")
