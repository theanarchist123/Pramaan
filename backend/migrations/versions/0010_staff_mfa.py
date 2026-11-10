"""Staff MFA: encrypted TOTP secret, enrolment time and the step-up window."""
from alembic import op

revision = "0010_staff_mfa"
down_revision = "0009_review_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret_enc VARCHAR(300)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enrolled_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS stepup_until TIMESTAMPTZ")


def downgrade() -> None:
    for col in ("stepup_until", "mfa_enrolled_at", "totp_secret_enc"):
        op.execute(f"ALTER TABLE users DROP COLUMN IF EXISTS {col}")
