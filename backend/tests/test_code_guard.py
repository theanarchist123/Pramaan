"""The guard is the first wall against AI-written code: test that it refuses the dangerous and allows the useful."""

from __future__ import annotations

import pytest

from app.llm import mock
from app.agents.schemas import PluginProposal
from app.services.code_guard import check_files, check_source

SLUG = "demo_plugin"
HEAD = '''from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.models import Profile

router = APIRouter(prefix="/v1/plugins/demo_plugin")
'''


def plugin(body: str, head: str = HEAD) -> list[str]:
    return check_source("plugins/demo_plugin.py", head + body, SLUG)


def test_allowed_sql_functions_still_work():
    assert plugin("x = func.count()\ny = func.lower(Profile.sector)\nz = func.round(func.avg(Profile.id), 2)\n") == []


def test_the_offline_proposal_passes_the_guard():
    p = mock.respond(PluginProposal, {"request": "members by state"})
    assert check_files(p.slug, {f.path: f.content for f in p.files}) == []


def test_a_useful_read_only_plugin_is_allowed():
    assert plugin('''
def top(rows):
    return sorted(rows, key=lambda r: -r[1])[:5]

@router.get("")
async def go(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Profile.sector, func.count()).group_by(Profile.sector))).all()
    return top(rows)
''') == []


@pytest.mark.parametrize("snippet, fragment", [
    ("import os\n", "import of 'os'"),
    ("import subprocess\n", "import of 'subprocess'"),
    ("import socket\n", "import of 'socket'"),
    ("import importlib\n", "import of 'importlib'"),
    ("import os.path\n", "import of 'os.path'"),
    ("from os import system\n", "import from 'os'"),
    ("from app.config import get_settings\n", "import from 'app.config'"),
    ("from app.models import User\n", "'User' may not be imported"),
    ("from app.models import ApiKey, Webhook\n", "may not be imported"),
    ("from sqlalchemy import text\n", "'text' may not be imported"),
    ("from sqlalchemy import delete\n", "'delete' may not be imported"),
    ("from fastapi import *\n", "star imports"),
    ("from . import x\n", "relative imports"),
    ("x = eval('1')\n", "'eval'"),
    ("exec('1')\n", "'exec'"),
    ("f = open('/etc/passwd')\n", "'open'"),
    ("m = __import__('os')\n", "'__import__'"),
    ("x = getattr(object, 'x')\n", "'getattr'"),
    ("x = ().__class__.__bases__\n", "reflection"),
    ("x = [].__class__.__subclasses__()\n", "reflection"),
    ("def f(s):\n    s.commit()\n", ".commit"),
    ("def f(s):\n    s.add(1)\n", ".add"),
    ("def f(s):\n    s.delete(1)\n", ".delete"),
    ("def f(p):\n    p.write_text('x')\n", ".write_text"),
    ("while True:\n    pass\n", "'while'"),
    ("def f():\n    global X\n", "'global'"),
    ("s = '__import__'\n", "dunder names in strings"),
    # SQL escape hatches: arbitrary functions, aliasing `func`, climbing to other tables
    ("x = func.pg_read_file('/etc/passwd')\n", "'func' may only be used"),
    ("x = func.pg_sleep(100)\n", "'func' may only be used"),
    ("f = func\nx = f.pg_read_file('/etc/passwd')\n", "'func' may only be used"),
    ("x = [func][0]\n", "'func' may only be used"),
    ("x = Profile.metadata.tables['users']\n", ".metadata"),
    ("def f(s):\n    return s.get_bind()\n", ".get_bind"),
    ("def f(s):\n    return s.connection()\n", ".connection"),
    ("x = Profile._sa_class_manager\n", "private/reflection"),
])
def test_dangerous_constructs_are_refused(snippet, fragment):
    violations = plugin(snippet)
    assert any(fragment in v for v in violations), (snippet, violations)


def test_router_prefix_is_enforced_so_a_plugin_cannot_shadow_core_routes():
    bad = HEAD.replace("/v1/plugins/demo_plugin", "/v1/verify")
    assert any("router must be" in v for v in plugin("", bad))
    missing = HEAD.replace('router = APIRouter(prefix="/v1/plugins/demo_plugin")\n', "")
    assert any("must define `router" in v for v in plugin("", missing))


def test_syntax_errors_and_oversized_files():
    assert any("syntax error" in v for v in check_source("plugins/x.py", "def (:\n", SLUG))
    assert any("larger than" in v for v in check_source("plugins/x.py", "x = 1\n" * 10000, SLUG))


def test_file_set_and_slug_are_strict():
    ok = {f"plugins/{SLUG}.py": HEAD, f"plugins/test_{SLUG}.py": "def test_x():\n    assert True\n"}
    assert check_files(SLUG, ok) == []
    assert check_files(SLUG, {**ok, "plugins/evil.py": "x=1"})  # extra file
    assert check_files(SLUG, {"app/main.py": "x=1", f"plugins/test_{SLUG}.py": ""})  # path traversal-ish
    assert check_files("../x", ok) and check_files("Bad", ok) and check_files("__init__", ok)
    assert check_files(SLUG, {"plugins/../app/main.py": "x", f"plugins/test_{SLUG}.py": ""})


def test_tests_may_import_pytest_and_their_own_plugin_but_not_the_world():
    t = lambda src: check_source(f"plugins/test_{SLUG}.py", src, SLUG)  # noqa: E731
    assert t("import pytest\nfrom plugins.demo_plugin import router\n") == []
    assert t("from fastapi.testclient import TestClient\n") == []
    assert t("import os\n")
    assert t("from plugins.other import x\n")  # only the plugin under test
    # pytest is not available to production plugin code
    assert plugin("import pytest\n")
