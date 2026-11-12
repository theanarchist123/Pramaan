"""OAuth 2.0 + PKCE (API-02): three new tables only. Additive; nothing existing is touched."""
from alembic import op

revision = "0018_oauth"
down_revision = "0017_api_key_usage"
branch_labels = None
depends_on = None

TABLES = ["oauth_clients", "oauth_codes", "oauth_tokens"]


def upgrade() -> None:
    from app import models  # noqa: F401
    from app.db import Base

    for t in TABLES:
        Base.metadata.tables[t].create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for t in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {t}")
