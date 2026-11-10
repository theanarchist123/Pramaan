"""Staff roles, the append-only audit log (with its immutability trigger) and four-eyes approval requests."""
from alembic import op

revision = "0008_rbac_audit_approvals"
down_revision = "0007_image_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base
    from app.services.audit import TRIGGER_SQL

    bind = op.get_bind()
    for t in ("user_roles", "admin_audit_log", "approval_requests"):
        Base.metadata.tables[t].create(bind, checkfirst=True)
    for stmt in TRIGGER_SQL:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approval_requests")
    op.execute("DROP TABLE IF EXISTS admin_audit_log")
    op.execute("DROP FUNCTION IF EXISTS admin_audit_log_immutable()")
    op.execute("DROP TABLE IF EXISTS user_roles")
