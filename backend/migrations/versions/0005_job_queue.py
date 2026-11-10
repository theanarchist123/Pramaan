"""The Postgres job queue (Procrastinate): its tables, functions and triggers. Idempotent."""
revision = "0005_job_queue"
down_revision = "0004_decision_basis_wikidata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import jobs

    jobs.ensure_schema_sync()  # a separate connection: the queue's schema is applied by its own library


def downgrade() -> None:
    raise NotImplementedError("Drop the procrastinate_* objects by hand if you really want the queue gone.")
