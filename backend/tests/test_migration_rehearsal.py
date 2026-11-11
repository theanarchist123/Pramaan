"""The migration rehearsal (scripts/migration_rehearsal.py) as a test: upgrade, repeat, downgrade, on a scratch database."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "migration_rehearsal.py"


async def test_upgrade_then_downgrade_leaves_the_schema_and_every_row_exactly_as_they_were():
    try:
        conn = await asyncpg.connect("postgresql://pramaan:pramaan@localhost:5432/postgres", timeout=3)
        await conn.close()
    except Exception:
        pytest.skip("Postgres not reachable")
    out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stdout[-2500:] + out.stderr[-1500:]
    assert "existing rows unchanged after upgrade: True" in out.stdout
    assert "schema identical to the starting point: True" in out.stdout
    assert "existing rows unchanged after downgrade: True" in out.stdout
