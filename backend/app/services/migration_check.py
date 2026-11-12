"""Checks for an AI-proposed database migration (AGT-10, tier T3, spec 8.4). Nothing here applies a migration to a real database.

1. `lint`: the source must be an EXPAND-only Alembic migration: add tables, nullable or defaulted columns, and indexes that cannot lock. It must chain from the current head,
   have a real downgrade, and use nothing but alembic and sqlalchemy. Destructive or locking changes (drops, renames, type changes, NOT NULL without a default, plain
   CREATE INDEX on an existing table, data rewrites) are refused: a CONTRACT step is written by a person, in a later migration, once no code reads what it removes.
2. `rehearse`: build a scratch database at the current head, apply the migration, check the schema change is purely additive, roll it back, and check the schema is
   identical to before. The scratch database is dropped. (A rehearsal on a copy of production data is `scripts/migration_rehearsal.py`, which needs your database.)
Two different people then approve it, and a person puts the file into `migrations/` through a pull request (a protected path); the app never runs it.
"""
from __future__ import annotations

import ast
import asyncio
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
VERSIONS = BACKEND / "migrations" / "versions"
REV_RE = re.compile(r"^\d{4}_[a-z0-9_]{3,40}$")
ALLOWED_IMPORTS = ("alembic", "sqlalchemy")
FORBIDDEN_NAMES = {"exec", "eval", "open", "compile", "__import__", "subprocess", "os", "sys", "shutil", "socket"}


def current_head() -> str:
    revs, downs = {}, set()
    for f in VERSIONS.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        r = re.search(r'^revision\s*=\s*"([^"]+)"', src, re.M)
        d = re.search(r'^down_revision\s*=\s*"([^"]+)"', src, re.M)
        if r:
            revs[r.group(1)] = f
        if d:
            downs.add(d.group(1))
    heads = [r for r in revs if r not in downs]
    return sorted(heads)[-1] if heads else ""


def filename(revision: str) -> str:
    if not REV_RE.match(revision or ""):
        raise ValueError("revision must look like 0021_short_name")
    return f"{revision}.py"


def _const(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kw(call: ast.Call, name: str):
    return next((k.value for k in call.keywords if k.arg == name), None)


def _is_op(call: ast.Call, name: str) -> bool:
    f = call.func
    return isinstance(f, ast.Attribute) and f.attr == name and isinstance(f.value, ast.Name) and f.value.id == "op"


def _sql_problems(sql: str) -> list[str]:
    s = " ".join(sql.upper().split())
    out = []
    if re.search(r"\bDROP\s+(TABLE|COLUMN|INDEX|CONSTRAINT|SCHEMA|TYPE)\b", s):
        out.append("drops something (destroys data or breaks running code): a contract step is written by a person")
    if re.search(r"\bRENAME\b", s):
        out.append("renames something: old code still running would break (expand a new name, move over, then contract)")
    if re.search(r"\bALTER\s+COLUMN\s+\S+\s+(SET\s+DATA\s+)?TYPE\b", s):
        out.append("a type change rewrites the table and locks it")
    if re.search(r"\bSET\s+NOT\s+NULL\b", s):
        out.append("SET NOT NULL on an existing column scans and locks the table (add it nullable or with a default)")
    if re.search(r"\bCREATE\s+(UNIQUE\s+)?INDEX\b", s) and not re.search(r"\bCREATE\s+(UNIQUE\s+)?INDEX\s+CONCURRENTLY\b", s):
        out.append("a plain CREATE INDEX locks writes: use CREATE INDEX CONCURRENTLY inside an autocommit block")
    if re.search(r"\b(DELETE\s+FROM|TRUNCATE|UPDATE\s+\S+\s+SET)\b", s):
        out.append("rewrites or removes data: backfills are batched jobs, not migrations")
    return out


def lint(source: str) -> list[str]:
    if not (source or "").strip():
        return ["the migration is empty"]
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["the migration could not be read as Python"]
    problems: list[str] = []
    values = {t.id: _const(n.value) for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    rev = values.get("revision")
    if not rev or not REV_RE.match(rev):
        problems.append("the migration needs a revision id like 0021_short_name")
    head = current_head()
    if values.get("down_revision") != head:
        problems.append(f"down_revision must be the current head, {head}")
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "upgrade" not in fns:
        problems.append("there is no upgrade()")
        return problems
    down = fns.get("downgrade")
    real = [s for s in (down.body if down else []) if not (isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)))]
    if not real:
        problems.append("the downgrade must really undo the upgrade (it is empty)")
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] not in ALLOWED_IMPORTS for a in n.names):
            problems.append("only alembic and sqlalchemy may be imported")
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] not in ALLOWED_IMPORTS:
            problems.append("only alembic and sqlalchemy may be imported")
        if isinstance(n, ast.Name) and n.id in FORBIDDEN_NAMES:
            problems.append(f"'{n.id}' is not allowed in a migration")
    created = {_const(c.args[0]) for c in ast.walk(fns["upgrade"]) if isinstance(c, ast.Call) and _is_op(c, "create_table") and c.args}
    for c in [x for x in ast.walk(fns["upgrade"]) if isinstance(x, ast.Call)]:
        if _is_op(c, "drop_table") or _is_op(c, "drop_column") or _is_op(c, "drop_index") or _is_op(c, "drop_constraint"):
            problems.append("drops something (destroys data or breaks running code): a contract step is written by a person")
        if _is_op(c, "rename_table"):
            problems.append("renames a table: old code still running would break")
        if _is_op(c, "alter_column"):
            if _kw(c, "new_column_name") is not None:
                problems.append("renames a column: old code still running would break")
            if _kw(c, "type_") is not None:
                problems.append("a type change rewrites the table and locks it")
            nn = _kw(c, "nullable")
            if isinstance(nn, ast.Constant) and nn.value is False and _kw(c, "server_default") is None:
                problems.append("NOT NULL on an existing column without a default locks the table")
        if _is_op(c, "add_column"):
            col = next((a for a in c.args if isinstance(a, ast.Call)), None)
            if col is not None:
                nn = _kw(col, "nullable")
                if isinstance(nn, ast.Constant) and nn.value is False and _kw(col, "server_default") is None:
                    problems.append("a NOT NULL column needs a server_default (add it nullable or with a default)")
        if _is_op(c, "create_index"):
            table = _const(c.args[1]) if len(c.args) > 1 else None
            if table not in created and not (isinstance(_kw(c, "postgresql_concurrently"), ast.Constant) and _kw(c, "postgresql_concurrently").value):
                problems.append("an index on an existing table locks writes: create it CONCURRENTLY")
        if _is_op(c, "execute"):
            sql = _const(c.args[0]) if c.args else None
            if sql is None:
                problems.append("write op.execute() SQL as a plain string so it can be checked")
            else:
                problems += _sql_problems(sql)
    return list(dict.fromkeys(problems))


@dataclass
class Rehearsal:
    ok: bool = False
    problems: list[str] = field(default_factory=list)
    tables_added: list[str] = field(default_factory=list)
    columns_added: dict = field(default_factory=dict)
    rollback_restored: bool = False
    seconds: float = 0.0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _snapshot(conn) -> dict:
    cols = conn.execute("""SELECT table_name, column_name, data_type, is_nullable FROM information_schema.columns
                           WHERE table_schema = 'public' ORDER BY 1, 2""").fetchall()
    tables: dict = {}
    for t, c, dt, nullable in cols:
        tables.setdefault(t, {})[c] = (dt, nullable)
    idx = sorted(r[0] for r in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'").fetchall())
    return {"tables": tables, "indexes": idx}


def _run_alembic(ini: Path, db_url: str, *args: str) -> tuple[int, str]:
    env = {**os.environ, "DATABASE_URL": db_url, "ENVIRONMENT": "development", "PYTHONPATH": str(BACKEND)}
    out = subprocess.run([sys.executable, "-m", "alembic", "-c", str(ini), *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)
    return out.returncode, (out.stderr or out.stdout)[-600:]


def _rehearse_sync(source: str) -> Rehearsal:
    import psycopg

    from app.jobs import psycopg_dsn

    result = Rehearsal()
    rev = re.search(r'^revision\s*=\s*"([^"]+)"', source, re.M).group(1)
    base = psycopg_dsn()
    admin_dsn = re.sub(r"/[^/?]+(\?|$)", r"/postgres\1", base, count=1)
    db = f"rehearse_{uuid.uuid4().hex[:10]}"
    scratch_dsn = re.sub(r"/[^/?]+(\?|$)", rf"/{db}\1", base, count=1)
    async_url = scratch_dsn.replace("postgresql://", "postgresql+asyncpg://", 1).replace("sslmode=", "ssl=")
    tmp = Path(tempfile.mkdtemp(prefix="migcheck_"))
    started = time.monotonic()
    admin = psycopg.connect(admin_dsn, autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{db}"')
        shutil.copytree(BACKEND / "migrations", tmp / "migrations", ignore=shutil.ignore_patterns("__pycache__"))
        ini = tmp / "alembic.ini"
        ini.write_text((BACKEND / "alembic.ini").read_text(encoding="utf-8").replace("script_location = migrations", f"script_location = {(tmp / 'migrations').as_posix()}"), encoding="utf-8")
        (tmp / "migrations" / "versions" / filename(rev)).write_text(source, encoding="utf-8")
        head = current_head()
        code, msg = _run_alembic(ini, async_url, "upgrade", head)
        if code:
            result.problems.append(f"the rehearsal database could not be built at the current head: {msg}")
            return result
        with psycopg.connect(scratch_dsn, autocommit=True) as c:
            before = _snapshot(c)
        t0 = time.monotonic()
        code, msg = _run_alembic(ini, async_url, "upgrade", rev)
        result.seconds = round(time.monotonic() - t0, 2)
        if code:
            result.problems.append(f"the migration did not apply: {msg.strip().splitlines()[-1] if msg.strip() else 'unknown error'}")
            return result
        with psycopg.connect(scratch_dsn, autocommit=True) as c:
            after = _snapshot(c)
        result.tables_added = sorted(set(after["tables"]) - set(before["tables"]))
        for t, cols in after["tables"].items():
            if t in before["tables"]:
                added = {k: v[0] for k, v in cols.items() if k not in before["tables"][t]}
                if added:
                    result.columns_added[t] = added
        for t, cols in before["tables"].items():
            if t not in after["tables"]:
                result.problems.append(f"table {t} disappeared: not additive")
                continue
            for k, v in cols.items():
                if k not in after["tables"][t]:
                    result.problems.append(f"column {t}.{k} disappeared: not additive")
                elif after["tables"][t][k] != v:
                    result.problems.append(f"column {t}.{k} changed from {v} to {after['tables'][t][k]}: not additive")
        code, msg = _run_alembic(ini, async_url, "downgrade", head)
        if code:
            result.problems.append(f"the rollback did not run: {msg.strip().splitlines()[-1] if msg.strip() else 'unknown error'}")
            return result
        with psycopg.connect(scratch_dsn, autocommit=True) as c:
            rolled = _snapshot(c)
        result.rollback_restored = rolled == before
        if not result.rollback_restored:
            result.problems.append("the rollback did not restore the schema to exactly what it was before")
        result.ok = not result.problems
        return result
    except Exception as exc:  # noqa: BLE001 - a rehearsal that cannot run is a failed rehearsal, never a pass
        result.problems.append(f"the rehearsal could not run: {type(exc).__name__}")
        return result
    finally:
        try:
            admin.execute(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        finally:
            admin.close()
            shutil.rmtree(tmp, ignore_errors=True)


async def rehearse(source: str, *, skip_lint: bool = False) -> Rehearsal:
    if not skip_lint:
        problems = lint(source)
        if problems:
            return Rehearsal(ok=False, problems=problems)
    elif not re.search(r'^revision\s*=\s*"([^"]+)"', source, re.M):
        return Rehearsal(ok=False, problems=["no revision id"])
    return await asyncio.to_thread(_rehearse_sync, source)
