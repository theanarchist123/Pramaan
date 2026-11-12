"""Identity bindings (TRU-04): a new table only. Additive; nothing existing is touched."""
from alembic import op

revision = "0014_identity_bindings"
down_revision = "0013_certificate_status_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["identity_bindings"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS identity_bindings")
