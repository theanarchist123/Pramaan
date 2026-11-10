"""Phase 0a: record HOW a profile was approved, and the Wikidata item the applicant confirmed."""
from alembic import op

revision = "0004_decision_basis_wikidata"
down_revision = "0003_code_change_run_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS decision_basis VARCHAR(12) NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS wikidata_qid VARCHAR(20) NOT NULL DEFAULT ''")
    # Profiles approved before this migration: we cannot tell automation from a person, so they stay blank
    # (the UI shows plain "Approved") rather than overstating either.


def downgrade() -> None:
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS wikidata_qid")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS decision_basis")
