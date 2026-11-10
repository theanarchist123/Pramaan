"""image_assets: human-approved, hotlinked, attributed sector imagery."""
from alembic import op

revision = "0007_image_assets"
down_revision = "0006_llm_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    Base.metadata.tables["image_assets"].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS image_assets")
