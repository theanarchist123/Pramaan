"""Static guard for AI-written plugins (Shilpkar). Runs BEFORE anything executes, and again right
before a plugin is loaded.

It is a whitelist, not a blacklist: a plugin may only read the public views (approved, consented, verified
data) through a read-only database session and return JSON. Everything else — files, processes, sockets, reflection, writes,
other tables (users, API keys, webhooks…) — is refused at the syntax-tree level.

This is one layer of three: (1) this guard, (2) tests + a security scan inside a network-less
container, (3) a human reading the diff and clicking approve.
"""

from __future__ import annotations

import ast
import re

MAX_FILE_CHARS = 20_000
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{2,29}$")

# module -> allowed names in `from module import name` (None = any name; module is safe)
ALLOWED_FROM: dict[str, set[str] | None] = {
    "fastapi": {"APIRouter", "Depends", "HTTPException", "Query", "Path"},
    "pydantic": {"BaseModel", "Field"},
    "sqlalchemy": {"select", "func", "and_", "or_", "desc", "asc", "case", "distinct"},
    "sqlalchemy.ext.asyncio": {"AsyncSession"},
    # A read-only session (Postgres refuses writes) and read-only VIEWS of approved, consented, verified data.
    # Deliberately NOT app.models: no drafts, rejected profiles, chat quotes, users, keys or webhooks.
    "app.plugin_api": {"get_readonly_session"},
    "app.public_views": {"PublicProfile", "PublicClaim", "PublicEvidence", "PublicCertificate"},
    "typing": None, "datetime": None, "collections": None, "itertools": None, "statistics": None,
    "decimal": None, "enum": None, "dataclasses": None, "math": None, "re": None, "json": None,
    "string": None, "textwrap": None, "__future__": None,
}
ALLOWED_PLAIN = {"math", "re", "json", "collections", "itertools", "statistics", "datetime", "typing",
                 "decimal", "enum", "dataclasses", "string", "textwrap"}
# Extra modules tests (only) may use.
TEST_FROM: dict[str, set[str] | None] = {"pytest": None, "fastapi.testclient": {"TestClient"}}
TEST_PLAIN = {"pytest"}

# `func.<anything>` can call ANY SQL function (pg_read_file, pg_sleep, dblink…) — so only harmless
# aggregate/scalar functions are reachable, and `func` may not be aliased or passed around.
ALLOWED_FUNCS = {"count", "sum", "avg", "min", "max", "lower", "upper", "coalesce", "round", "length",
                 "abs", "date_trunc", "extract", "concat", "nullif"}
# Ways to climb from an allowed model to the rest of the database.
BANNED_ATTRS_EXTRA = {"metadata", "registry", "mapper", "get_bind", "connection", "bind", "tables",
                      "sorted_tables", "class_", "classes"}

BANNED_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint", "globals", "locals", "vars",
    "getattr", "setattr", "delattr", "exit", "quit", "help", "memoryview", "__builtins__", "__loader__",
}
# Method names that mutate state, touch the OS or the network. The DB path is read-only by construction
# (only `select` is importable), and these are blocked as a second wall.
BANNED_ATTRS = {
    "add", "add_all", "delete", "commit", "flush", "merge", "rollback", "expunge", "refresh",
    "bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings", "run_sync",
    "system", "popen", "spawn", "remove", "unlink", "rmdir", "rmtree", "mkdir", "makedirs",
    "connect", "urlopen", "request", "send", "sendall", "recv", "environ", "getenv", "putenv",
    "write", "writelines", "read_text", "write_text", "read_bytes", "write_bytes", "exec_driver_sql",
}


def _is_test(path: str) -> bool:
    return path.rsplit("/", 1)[-1].startswith("test_")


def check_source(path: str, source: str, slug: str) -> list[str]:
    """Return a list of violations (empty = clean)."""
    out: list[str] = []
    if len(source) > MAX_FILE_CHARS:
        return [f"{path}: file larger than {MAX_FILE_CHARS} characters"]
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [f"{path}: syntax error on line {exc.lineno}"]

    test = _is_test(path)
    plain = ALLOWED_PLAIN | (TEST_PLAIN if test else set())
    from_ok = {**ALLOWED_FROM, **(TEST_FROM if test else {})}

    # `func` is only usable as `func.<allowed_function>(...)` — find every other use of the name.
    ok_func_names = {
        id(n.value) for n in ast.walk(tree)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "func"
        and n.attr in ALLOWED_FUNCS
    }

    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        where = f"{path}:{line}"

        if isinstance(node, ast.Name) and node.id == "func" and isinstance(node.ctx, ast.Load) and id(node) not in ok_func_names:
            out.append(f"{where}: 'func' may only be used as func.<{'|'.join(sorted(ALLOWED_FUNCS))}>(…)")

        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in plain or "." in a.name and a.name not in plain:
                    out.append(f"{where}: import of '{a.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * node.level) + (node.module or "")
            if node.level:
                out.append(f"{where}: relative imports are not allowed")
                continue
            own = test and mod == f"plugins.{slug}"
            if own:
                continue  # a test importing the plugin it tests
            if mod not in from_ok:
                out.append(f"{where}: import from '{mod}' is not allowed")
                continue
            allowed = from_ok[mod]
            for a in node.names:
                if a.name == "*":
                    out.append(f"{where}: star imports are not allowed")
                elif allowed is not None and a.name not in allowed:
                    out.append(f"{where}: '{a.name}' may not be imported from '{mod}'")
        elif isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            out.append(f"{where}: use of '{node.id}' is not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                out.append(f"{where}: access to '{node.attr}' (private/reflection) is not allowed")
            elif node.attr in BANNED_ATTRS_EXTRA:
                out.append(f"{where}: '.{node.attr}' is not allowed (it reaches beyond the plugin's data)")
            elif node.attr in BANNED_ATTRS:
                out.append(f"{where}: '.{node.attr}' is not allowed (plugins are read-only)")
        elif isinstance(node, (ast.While, ast.Global)):
            out.append(f"{where}: '{type(node).__name__.lower()}' is not allowed (use bounded for-loops)")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value and re.search(r"__\w+__", node.value):
            out.append(f"{where}: dunder names in strings are not allowed")

    if not test:
        out += _check_router(path, tree, slug)
    return sorted(set(out))


def _check_router(path: str, tree: ast.Module, slug: str) -> list[str]:
    """A plugin must expose `router = APIRouter(prefix="/v1/plugins/<slug>")` so it can never shadow
    a core route (like /v1/verify)."""
    expected = f"/v1/plugins/{slug}"
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "router" for t in node.targets):
            call = node.value
            if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "APIRouter":
                for kw in call.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and kw.value.value == expected:
                        return []
            return [f"{path}: router must be APIRouter(prefix=\"{expected}\")"]
    return [f"{path}: the plugin must define `router = APIRouter(prefix=\"{expected}\")`"]


def check_files(slug: str, files: dict[str, str]) -> list[str]:
    """Validate a whole proposal: exact file set, then every file."""
    if not SLUG_RE.match(slug) or slug.startswith("__"):
        return [f"slug '{slug}' is invalid (snake_case, 3-30 characters)"]
    expected = {f"plugins/{slug}.py", f"plugins/test_{slug}.py"}
    if set(files) != expected:
        return [f"a proposal must contain exactly these files: {sorted(expected)}; got {sorted(files)}"]
    violations: list[str] = []
    for path, src in files.items():
        violations += check_source(path, src, slug)
    return violations
