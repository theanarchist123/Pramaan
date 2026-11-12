# ADR 0010: Shilpkar tiers T2 and T3 (AGT-10)

Status: accepted (2026-11-12). T0 (fields) and T1 (read-only plugins, with a risk score) already existed.

- **T2, views as data.** `backend/app/services/viewspec.py`: a view is JSON (title, layout, up to 20 blocks from six components, bindings to five public read endpoints). No script, markup, link or styling is representable.
  The web interpreter (`apps/web/src/lib/viewspec.ts`, page `/v/[slug]`) re-applies the same rules. A draft is public to no one; the person who proposed or last edited a view cannot publish it; the previous version is kept for roll back.
- **T3, migrations.** `backend/app/services/migration_check.py`: lint (expand-only: no drops, renames, type changes, NOT NULL without a default, locking indexes, data rewrites; must chain from the current head and have a real downgrade),
  then a rehearsal on a scratch database (apply, additive-only schema diff, roll back, identical schema). Two different people approve; approval produces a release note. **The app never applies a migration**: a person adds the file through a pull request (migrations/ is a protected path), deploys it as a canary, and keeps `alembic downgrade <head>` as the rollback.
- Both go through Sutradhar's `agent_shilpkar_enabled` switch and budgets.

## Not done
- The rehearsal uses an empty scratch copy at the current head, so it cannot measure lock time on real row counts: use `scripts/migration_rehearsal.py` against a copy of production data before release.
- T1 plugins are still loaded in-process (dev-only per the spec); the out-of-process read-only plugin service is not built.
- T4 (core logic, prompts, policies) is the fixer's pull-request path (AGT-13); there is no separate tier machinery.
