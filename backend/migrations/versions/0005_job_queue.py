"""The Postgres job queue (Procrastinate): its tables, functions and triggers. Idempotent."""
from alembic import op

revision = "0005_job_queue"
down_revision = "0004_decision_basis_wikidata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app import jobs

    jobs.ensure_schema_sync()  # a separate connection: the queue's schema is applied by its own library


def downgrade() -> None:
    """Remove the queue's tables, functions and types. DESTROYS any queued or finished jobs (they live only in these tables)."""
    op.execute(r"""
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'procrastinate\_%' LOOP
                EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', r.tablename);   -- takes their triggers with them
            END LOOP;
            FOR r IN SELECT format('%I(%s)', p.proname, pg_get_function_identity_arguments(p.oid)) AS f
                       FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                      WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate\_%' LOOP
                EXECUTE 'DROP FUNCTION IF EXISTS ' || r.f || ' CASCADE';
            END LOOP;
            FOR r IN SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                      WHERE n.nspname = 'public' AND typname LIKE 'procrastinate\_%' AND typtype = 'e' LOOP
                EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', r.typname);
            END LOOP;
        END $$
    """)
