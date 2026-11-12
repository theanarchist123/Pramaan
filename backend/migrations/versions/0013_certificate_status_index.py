"""Certificates get a status-list index (Bitstring Status List, TRU-08). Additive and reversible: a nullable column + unique index.

Existing certificates keep a NULL index until they are first requested as a credential (the API assigns a random free one lazily), so
this migration does not rewrite or lock any certificate row.
"""
from alembic import op

revision = "0013_certificate_status_index"
down_revision = "0012_mfa_recovery_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE certificates ADD COLUMN IF NOT EXISTS status_index INTEGER")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS certificates_status_index_key ON certificates (status_index)")


def downgrade() -> None:
    # Dropping the column removes its unique index OR unique constraint, whichever exists: a database built from the models has a
    # constraint of this name, one upgraded from 0012 has an index, and DROP INDEX cannot remove a constraint's index.
    op.execute("ALTER TABLE certificates DROP COLUMN IF EXISTS status_index")
