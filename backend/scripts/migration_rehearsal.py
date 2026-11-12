"""Rehearse `alembic upgrade head` (and the downgrade) on a COPY, and report exactly what changes.

    python scripts/migration_rehearsal.py            # needs the local docker database (docker compose up -d db)

It never touches your real database: it creates a scratch database, puts it in the state production is in (schema at revision
0003, with data in it), runs the upgrade, checks that no existing row changed, runs the downgrade back to 0003 and checks that the
schema and the data are exactly what they were. The scratch database is dropped at the end. Exit code 1 if anything differs.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parent.parent
ADMIN = "postgresql://pramaan:pramaan@localhost:5432/{db}"

# Everything the post-0003 revisions add (so a database built by the baseline's create_all can be put back in the
# production-like state before the rehearsal).
ADDED_TABLES = ["llm_calls", "image_assets", "user_roles", "admin_audit_log", "approval_requests", "review_decisions",
                "governed_setting_changes", "governed_settings", "mfa_recovery_codes"]
ADDED_COLUMNS = {"profiles": ["decision_basis", "wikidata_qid"], "review_queue": ["assigned_to", "locked_until", "sla_due_at"],
                 "users": ["totp_secret_enc", "mfa_enrolled_at", "stepup_until"], "certificates": ["status_index"]}


def alembic(db: str, *args: str) -> str:
    env = {**os.environ, "DATABASE_URL": f"postgresql+asyncpg://pramaan:pramaan@localhost:5432/{db}", "ENVIRONMENT": "development"}
    out = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)
    if out.returncode:
        raise SystemExit(f"alembic {' '.join(args)} failed:\n{out.stderr[-1500:]}")
    return out.stdout + out.stderr


def snapshot(conn) -> dict:
    cols = conn.execute("""SELECT table_name, column_name, data_type, is_nullable, column_default FROM information_schema.columns
                           WHERE table_schema = 'public' ORDER BY 1, 2""").fetchall()
    tables: dict = {}
    for t, c, dt, nullable, default in cols:
        tables.setdefault(t, {})[c] = f"{dt} {'NULL' if nullable == 'YES' else 'NOT NULL'}" + (f" DEFAULT {default}" if default else "")
    funcs = sorted(r[0] for r in conn.execute("SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'"))
    trig = sorted(r[0] for r in conn.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))
    types = sorted(r[0] for r in conn.execute("SELECT typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = 'public' AND typtype = 'e'"))
    views = sorted(r[0] for r in conn.execute("SELECT viewname FROM pg_views WHERE schemaname = 'public'"))
    idx = sorted(r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
    return {"tables": tables, "functions": funcs, "triggers": trig, "types": types, "views": views, "indexes": idx}


def row_fingerprint(conn, table: str, columns: list[str]) -> str:
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1").fetchall()  # noqa: S608 - fixed names
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()[:16]


def diff(before: dict, after: dict) -> dict:
    out: dict = {"tables_added": sorted(set(after["tables"]) - set(before["tables"])),
                 "tables_dropped": sorted(set(before["tables"]) - set(after["tables"])), "columns_added": {}, "columns_dropped": {}}
    for t in set(before["tables"]) & set(after["tables"]):
        add = {c: d for c, d in after["tables"][t].items() if c not in before["tables"][t]}
        drop = sorted(c for c in before["tables"][t] if c not in after["tables"][t])
        if add:
            out["columns_added"][t] = add
        if drop:
            out["columns_dropped"][t] = drop
    for key in ("functions", "triggers", "types", "views", "indexes"):
        out[f"{key}_added"] = sorted(set(after[key]) - set(before[key]))
        out[f"{key}_dropped"] = sorted(set(before[key]) - set(after[key]))
    return out


def main() -> int:
    db = f"rehearsal_{uuid.uuid4().hex[:8]}"
    admin = psycopg.connect(ADMIN.format(db="postgres"), autocommit=True)
    admin.execute(f'CREATE DATABASE "{db}"')
    ok = True
    try:
        # 1. Production-like starting point: revision 0003, none of the later tables/columns.
        alembic(db, "upgrade", "0003")
        with psycopg.connect(ADMIN.format(db=db), autocommit=True) as c:
            for t in ADDED_TABLES:
                c.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
            c.execute("DROP FUNCTION IF EXISTS admin_audit_log_immutable() CASCADE")
            for t, cols in ADDED_COLUMNS.items():
                for col in cols:
                    c.execute(f"ALTER TABLE {t} DROP COLUMN IF EXISTS {col}")
            for t in [r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE 'procrastinate%'").fetchall()]:
                c.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
            c.execute("DROP TYPE IF EXISTS procrastinate_job_status CASCADE")
            c.execute("DROP TYPE IF EXISTS procrastinate_job_event_type CASCADE")
            c.execute("DELETE FROM alembic_version")
            c.execute("INSERT INTO alembic_version VALUES ('0003_code_change_run_id')")

            # 2. Real-looking data.
            uid, pid = uuid.uuid4(), uuid.uuid4()
            c.execute("INSERT INTO users (id, email, name, role, password_hash, created_at) VALUES (%s, 'a@example.com', 'A', 'admin', 'x', now())", (uid,))
            c.execute("""INSERT INTO profiles (id, owner_id, slug, full_name, headline, sector, state, city, bio, languages, institutions,
                         photo_url, custom, status, is_demo, created_at, updated_at)
                         VALUES (%s, %s, 'meera-1', 'Meera Iyer', 'h', 'Science', 'Kerala', '', 'bio', '{}', '{}', '', '{}', 'approved', false, now(), now())""", (pid, uid))
            c.execute("INSERT INTO claims (id, profile_id, field, value, status, confidence, created_at) VALUES (gen_random_uuid(), %s, 'award', 'X', 'web', 0.9, now())", (pid,))
            c.execute("INSERT INTO review_queue (id, profile_id, reason, confidence, details, status, created_at) VALUES (gen_random_uuid(), %s, 'r', 0.5, '{}', 'open', now())", (pid,))
            before = snapshot(c)
            fp_before = {"users": row_fingerprint(c, "users", ["id", "email", "role", "password_hash"]),
                         "profiles": row_fingerprint(c, "profiles", ["id", "slug", "full_name", "status", "bio"]),
                         "claims": row_fingerprint(c, "claims", ["id", "value", "status", "confidence"]),
                         "review_queue": row_fingerprint(c, "review_queue", ["id", "reason", "status"])}

        # 3. Upgrade.
        alembic(db, "upgrade", "head")
        with psycopg.connect(ADMIN.format(db=db), autocommit=True) as c:
            after_up = snapshot(c)
            changes = diff(before, after_up)
            fp_up = {"users": row_fingerprint(c, "users", ["id", "email", "role", "password_hash"]),
                     "profiles": row_fingerprint(c, "profiles", ["id", "slug", "full_name", "status", "bio"]),
                     "claims": row_fingerprint(c, "claims", ["id", "value", "status", "confidence"]),
                     "review_queue": row_fingerprint(c, "review_queue", ["id", "reason", "status"])}
            new_cols_on_existing_rows = {
                "profiles.decision_basis": c.execute("SELECT DISTINCT decision_basis FROM profiles").fetchall(),
                "profiles.wikidata_qid": c.execute("SELECT DISTINCT wikidata_qid FROM profiles").fetchall(),
                "review_queue.sla_due_at": c.execute("SELECT DISTINCT sla_due_at FROM review_queue").fetchall(),
                "users.mfa_enrolled_at": c.execute("SELECT DISTINCT mfa_enrolled_at FROM users").fetchall(),
            }
            head = c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        print(f"upgrade head -> {head}")
        print(json.dumps(changes, indent=2, default=str))
        print("values of the new columns on EXISTING rows:", json.dumps(new_cols_on_existing_rows, default=str))
        same_rows = fp_before == fp_up
        print(f"existing rows unchanged after upgrade: {same_rows}")
        ok &= same_rows

        # 4. Upgrade again (idempotent), then downgrade all the way back.
        alembic(db, "upgrade", "head")
        alembic(db, "downgrade", "0003")
        with psycopg.connect(ADMIN.format(db=db), autocommit=True) as c:
            after_down = snapshot(c)
            fp_down = {"users": row_fingerprint(c, "users", ["id", "email", "role", "password_hash"]),
                       "profiles": row_fingerprint(c, "profiles", ["id", "slug", "full_name", "status", "bio"]),
                       "claims": row_fingerprint(c, "claims", ["id", "value", "status", "confidence"]),
                       "review_queue": row_fingerprint(c, "review_queue", ["id", "reason", "status"])}
            rev = c.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        residue = diff(before, after_down)
        clean = not any(residue[k] for k in residue)
        print(f"\ndowngrade -> {rev}; schema identical to the starting point: {clean}")
        if not clean:
            print(json.dumps({k: v for k, v in residue.items() if v}, indent=2, default=str))
        print(f"existing rows unchanged after downgrade: {fp_before == fp_down}")
        ok &= clean and fp_before == fp_down and rev.startswith("0003")
    finally:
        admin.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        admin.close()
    print("\nREHEARSAL " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
