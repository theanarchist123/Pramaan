"""The sandbox, tested with REAL Docker. Hostile code is run directly inside the container (bypassing the
static guard on purpose) to prove the container itself is the second wall."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from app.agents.schemas import PluginProposal
from app.llm import mock
from app.services import sandbox

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="module")
def docker_ready():
    ok, why = asyncio.run(sandbox.available())
    if not ok:
        pytest.skip(f"sandbox unavailable: {why}")


def good_files():
    p = mock.respond(PluginProposal, {"request": "members by state"})
    return p.slug, {f.path: f.content for f in p.files}


async def probe(code: str, timeout: float = 30) -> tuple[int, str]:
    """Run arbitrary python inside the sandbox exactly as plugin tests are run."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "plugins").mkdir()
        return await sandbox._in_container(Path(d), ["python", "-c", code], timeout)


async def test_a_good_plugin_passes_lint_scan_and_tests(docker_ready):
    slug, files = good_files()
    r = await sandbox.run_checks(slug, files)
    assert r["ran"] and r["passed"], r
    assert [s["name"] for s in r["steps"]] == ["lint (ruff)", "security scan (bandit)", "tests (pytest)"]
    assert "2 passed" in r["steps"][2]["output"]


async def test_a_failing_test_blocks_the_change(docker_ready):
    slug, files = good_files()
    files[f"plugins/test_{slug}.py"] += "\n\ndef test_wrong():\n    assert summarise([('A', 1)])[0]['count'] == 99\n"
    r = await sandbox.run_checks(slug, files)
    assert r["ran"] and not r["passed"]
    assert r["steps"][-1]["name"] == "tests (pytest)" and not r["steps"][-1]["ok"]
    assert "assert" in r["steps"][-1]["output"]


async def test_lint_errors_stop_before_tests_run(docker_ready):
    slug, files = good_files()
    files[f"plugins/{slug}.py"] = "import json\n" + files[f"plugins/{slug}.py"]  # unused import (F401)
    r = await sandbox.run_checks(slug, files)
    assert not r["passed"] and len(r["steps"]) == 1 and "F401" in r["steps"][0]["output"]


async def test_the_security_scanner_catches_what_it_should(docker_ready):
    slug, files = good_files()
    files[f"plugins/{slug}.py"] += "\n\ndef load(blob):\n    import pickle  # noqa\n    return pickle.loads(blob)\n"
    r = await sandbox.run_checks(slug, files)
    scan = next(s for s in r["steps"] if s["name"].startswith("security"))
    assert not scan["ok"] and "pickle" in scan["output"].lower()


async def test_the_container_has_no_network(docker_ready):
    code, out = await probe(
        "import socket\n"
        "for host, port in (('1.1.1.1', 53), ('host.docker.internal', 5432), ('localhost', 5432)):\n"
        "    try:\n        socket.create_connection((host, port), timeout=3); print('REACHED', host)\n"
        "    except OSError as e: print('blocked', host)\n"
    )
    assert "REACHED" not in out and out.count("blocked") == 3, out


async def test_the_filesystem_is_read_only_and_the_plugin_mount_is_immutable(docker_ready):
    code, out = await probe(
        "for path in ('/work/plugins/evil.py', '/work/app/evil.py', '/etc/evil', '/usr/evil', '/evil'):\n"
        "    try:\n        open(path, 'w').write('x'); print('WROTE', path)\n"
        "    except OSError: print('refused', path)\n"
    )
    assert "WROTE" not in out and out.count("refused") == 5, out


async def test_runs_unprivileged_with_no_capabilities(docker_ready):
    code, out = await probe(
        "import os\nprint('uid', os.getuid())\n"
        "print('caps', [l.split()[1] for l in open('/proc/self/status') if l.startswith('CapEff')])\n"
    )
    assert "uid 10001" in out and "caps ['0000000000000000']" in out, out


async def test_host_secrets_and_files_are_invisible(docker_ready):
    os.environ["SANDBOX_CANARY_SECRET"] = "super-secret-canary"
    try:
        code, out = await probe(
            "import os\nprint('env', 'SANDBOX_CANARY_SECRET' in os.environ, 'ANTHROPIC_API_KEY' in os.environ, 'GEMINI_API_KEY' in os.environ)\n"
            "print('dotenv', os.path.exists('/work/.env'), os.path.exists('/work/../.env'))\n"
            "print('data', os.path.exists('/work/data'))\n"
        )
    finally:
        del os.environ["SANDBOX_CANARY_SECRET"]
    assert "env False False False" in out and "dotenv False False" in out and "data False" in out, out


async def test_runaway_code_is_killed_and_the_container_removed(docker_ready):
    code, out = await probe("while True:\n    pass\n", timeout=3)
    assert code == 124
    await asyncio.sleep(1.5)
    ps = await sandbox._run("docker", "ps", "-a", "--filter", "name=pramaan-sbx-", "--format", "{{.Names}}", timeout=15)
    assert ps[1].strip() == "", f"leftover sandbox containers: {ps[1]}"


async def test_memory_bombs_are_contained(docker_ready):
    code, out = await probe("x = bytearray(2 * 1024 * 1024 * 1024)\nprint('ALLOCATED')\n", timeout=30)
    assert "ALLOCATED" not in out and code != 0, (code, out)


async def test_fork_bombs_are_contained(docker_ready):
    code, out = await probe(
        "import os\nn = 0\n"
        "try:\n    for _ in range(2000):\n        if os.fork() == 0:\n            import time; time.sleep(5); os._exit(0)\n        n += 1\n"
        "except OSError:\n    pass\nprint('forked', n)\n",
        timeout=40,
    )
    forked = int(out.split("forked")[-1].split()[0]) if "forked" in out else 0
    assert forked < 200, f"pids-limit did not hold ({forked} forks)"
