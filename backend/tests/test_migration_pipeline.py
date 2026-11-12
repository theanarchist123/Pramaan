"""Shilpkar tier T3 (AGT-10, spec 8.4): an agent may PROPOSE an Alembic migration; it is linted for expand-only changes, rehearsed on a scratch copy (apply, check
the schema change is additive, roll back, check the schema is identical), and then needs TWO people. The app never applies a migration itself."""
import pytest

from app.services import migration_check as mc

HEAD = mc.current_head()

GOOD = f'''"""Expand: a notes table (additive)."""
from alembic import op
import sqlalchemy as sa

revision = "9999_builder_notes"
down_revision = "{HEAD}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("builder_notes", sa.Column("id", sa.Integer, primary_key=True), sa.Column("body", sa.Text, nullable=True))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS builder_notes")
'''


def bad(upgrade_body, downgrade_body='    op.execute("DROP TABLE IF EXISTS builder_notes")', head=HEAD, extra=""):
    return GOOD.replace('op.create_table("builder_notes", sa.Column("id", sa.Integer, primary_key=True), sa.Column("body", sa.Text, nullable=True))', upgrade_body) \
               .replace('    op.execute("DROP TABLE IF EXISTS builder_notes")', downgrade_body).replace(f'down_revision = "{HEAD}"', f'down_revision = "{head}"') + extra


def test_the_head_is_found_from_the_files():
    assert HEAD and HEAD.startswith("00")


def test_a_clean_expand_migration_passes_the_lint():
    assert mc.lint(GOOD) == []


@pytest.mark.parametrize("upgrade_body,why", [
    ('op.execute("ALTER TABLE profiles DROP COLUMN bio")', "drop"),
    ('op.drop_table("claims")', "drop"),
    ('op.drop_column("profiles", "bio")', "drop"),
    ('op.execute("ALTER TABLE profiles RENAME COLUMN bio TO about")', "rename"),
    ('op.rename_table("claims", "assertions")', "rename"),
    ('op.alter_column("profiles", "bio", type_=sa.Integer())', "type change"),
    ('op.execute("ALTER TABLE profiles ALTER COLUMN bio TYPE integer")', "type change"),
    ('op.add_column("profiles", sa.Column("x", sa.Text, nullable=False))', "not null"),
    ('op.execute("ALTER TABLE profiles ALTER COLUMN bio SET NOT NULL")', "not null"),
    ('op.create_index("ix_x", "profiles", ["bio"])', "index"),
    ('op.execute("CREATE INDEX ix_y ON profiles (bio)")', "index"),
    ('op.execute("DELETE FROM profiles")', "data"),
    ('op.execute("UPDATE profiles SET bio = \'\'")', "data"),
    ('op.execute("TRUNCATE claims")', "data"),
])
def test_destructive_or_locking_changes_are_refused_in_an_expand_migration(upgrade_body, why):
    problems = mc.lint(bad(upgrade_body))
    assert problems and any(why in p.lower() for p in problems), problems


def test_a_not_null_column_with_a_default_is_acceptable_and_concurrent_indexes_are_too():
    ok_default = bad('op.add_column("profiles", sa.Column("x", sa.Text, nullable=False, server_default=""))')
    assert mc.lint(ok_default) == []
    ok_index = bad('with op.get_context().autocommit_block():\n        op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_z ON profiles (bio)")')
    assert mc.lint(ok_index) == []
    new_table_index = bad('op.create_table("builder_notes", sa.Column("id", sa.Integer, primary_key=True))\n    op.create_index("ix_n", "builder_notes", ["id"])')
    assert mc.lint(new_table_index) == []  # an index on a table created in the same migration has nothing to lock


def test_structure_is_checked():
    assert any("down_revision" in p for p in mc.lint(bad('op.execute("SELECT 1")', head="0001_something_else")))
    assert any("downgrade" in p.lower() for p in mc.lint(bad('op.execute("SELECT 1")', downgrade_body="    pass")))
    assert any("revision" in p.lower() for p in mc.lint("def upgrade():\n    pass\n"))
    assert mc.lint("def (") and mc.lint("")


def test_the_file_name_is_derived_and_never_trusted():
    assert mc.filename("9999_builder_notes") == "9999_builder_notes.py"
    with pytest.raises(ValueError):
        mc.filename("../../evil")


async def test_rehearsal_applies_checks_additive_and_rolls_back_cleanly(client):
    r = await mc.rehearse(GOOD)
    assert r.ok, r.problems
    assert r.tables_added == ["builder_notes"] and r.rollback_restored and r.seconds < 60


async def test_rehearsal_catches_a_downgrade_that_does_not_restore_the_schema(client):
    broken = bad('op.create_table("builder_notes", sa.Column("id", sa.Integer, primary_key=True))', downgrade_body="    pass")
    r = await mc.rehearse(broken, skip_lint=True)
    assert not r.ok and any("roll" in p.lower() for p in r.problems)


async def test_rehearsal_catches_a_migration_that_fails_to_apply(client):
    broken = bad('op.execute("SELECT * FROM table_that_does_not_exist")')
    r = await mc.rehearse(broken, skip_lint=True)
    assert not r.ok and any("did not apply" in p.lower() for p in r.problems)


async def test_the_pipeline_proposes_checks_and_needs_two_people_and_the_app_never_applies_it(client, make_user, monkeypatch):
    from app.agents import shilpkar

    async def fake(ctx, request, head):
        return shilpkar.MigrationProposal(summary="Adds a notes table.", source=GOOD)

    monkeypatch.setattr(shilpkar, "propose_migration", fake)
    a, _ = await make_user(promote_to_admin=True)
    b, _ = await make_user(promote_to_admin=True)
    r = await client.post("/v1/admin/builder/migrations", headers=a, json={"request": "add a notes table for the builder"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "ready" and body["checks"]["lint"] == [] and body["checks"]["rehearsal"]["ok"] is True
    cid = body["id"]
    applied = await client.post(f"/v1/admin/builder/changes/{cid}/apply", headers=a)
    assert applied.status_code == 409 and "never" in applied.json()["detail"].lower()  # the app does not run migrations
    first = await client.post(f"/v1/admin/builder/migrations/{cid}/approve", headers=a)
    assert first.status_code == 200 and first.json()["status"] == "ready"           # the author cannot be the only approver
    same = await client.post(f"/v1/admin/builder/migrations/{cid}/approve", headers=a)
    assert same.status_code == 409                                                  # the same person twice is still one person
    second = await client.post(f"/v1/admin/builder/migrations/{cid}/approve", headers=b)
    assert second.status_code == 200 and second.json()["status"] == "approved_for_release"
    assert "9999_builder_notes.py" in second.json()["checks"]["release_note"]


async def test_a_migration_that_fails_the_lint_is_stopped_before_anything_runs(client, make_user, monkeypatch):
    from app.agents import shilpkar

    async def fake(ctx, request, head):
        return shilpkar.MigrationProposal(summary="Drops stuff.", source=bad('op.drop_table("claims")'))

    monkeypatch.setattr(shilpkar, "propose_migration", fake)
    a, _ = await make_user(promote_to_admin=True)
    r = await client.post("/v1/admin/builder/migrations", headers=a, json={"request": "remove the claims table please"})
    assert r.status_code == 201 and r.json()["status"] == "checks_failed" and r.json()["checks"]["lint"] and "rehearsal" not in r.json()["checks"]
