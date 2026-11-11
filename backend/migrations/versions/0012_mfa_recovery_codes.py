"""MFA recovery codes (hashed, single-use)."""
from alembic import op

revision = "0012_mfa_recovery_codes"
down_revision = "0011_governed_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["mfa_recovery_codes"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mfa_recovery_codes")
