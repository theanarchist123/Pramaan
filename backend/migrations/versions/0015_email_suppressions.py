"""Email suppression list (AGT-09): a new table only. Additive; nothing existing is touched."""
from alembic import op

revision = "0015_email_suppressions"
down_revision = "0014_identity_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["email_suppressions"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_suppressions")
