"""Run checks on AI-written plugin code inside a locked-down, network-less Docker container.

The code is NEVER imported or executed on the host here. It is written to a temp directory and
checked by ruff (lint), bandit (security scan) and pytest — all inside the container:

    --network none          no DNS, no database, no internet
    --read-only + tmpfs     nothing persists, nothing can be modified
    --cap-drop ALL, no-new-privileges, non-root uid 10001
    --memory 512m --cpus 1 --pids-limit 128, hard wall-clock timeout per step

If Docker or the image is unavailable the result is "could not verify", and a plugin that was not
verified can never be applied.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

IMAGE = "pramaan-sandbox"
OUTPUT_LIMIT = 4000


async def _run(*args: str, timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return proc.returncode or 0, out.decode("utf-8", "replace")
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "timed out"
    except FileNotFoundError:
        return 127, "docker is not installed"


async def available() -> tuple[bool, str]:
    code, out = await _run("docker", "image", "inspect", IMAGE, timeout=20)
    if code == 0:
        return True, ""
    if code == 127:
        return False, "Docker is not installed or not running."
    return False, f"Sandbox image missing. Build it once: docker build -t {IMAGE} sandbox/"


async def _in_container(workdir: Path, command: list[str], timeout: float) -> tuple[int, str]:
    name = f"pramaan-sbx-{uuid.uuid4().hex[:10]}"
    args = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,size=64m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
        "--user", "10001:10001",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONPATH=/work",
        "-v", f"{workdir / 'plugins'}:/work/plugins:ro",
        "-v", f"{BACKEND_DIR / 'app'}:/work/app:ro",
        "-w", "/work", IMAGE, *command,
    ]
    code, out = await _run(*args, timeout=timeout)
    if code == 124:  # the client was killed, the container may not have been
        await _run("docker", "rm", "-f", name, timeout=15)
    return code, out


async def run_checks(slug: str, files: dict[str, str]) -> dict[str, Any]:
    ok, why = await available()
    if not ok:
        return {"ran": False, "passed": False, "reason": why, "steps": []}

    tmp = Path(tempfile.mkdtemp(prefix="pramaan-plugin-"))
    started = time.time()
    try:
        plug = tmp / "plugins"
        plug.mkdir()
        (plug / "__init__.py").write_text("")
        for rel, src in files.items():
            (tmp / rel).write_text(src, encoding="utf-8")

        steps_spec = [
            # Pinned rules (syntax/real errors + pyflakes) so the verdict never depends on a ruff version's
            # defaults — nor on file modes, which Windows bind-mounts report as executable.
            ("lint (ruff)", ["ruff", "check", "--isolated", "--no-cache", "--select", "E4,E7,E9,F",
                             f"plugins/{slug}.py", f"plugins/test_{slug}.py"], 60),
            ("security scan (bandit)", ["bandit", "-q", "-ll", f"plugins/{slug}.py"], 60),
            ("tests (pytest)", ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"plugins/test_{slug}.py"], 90),
        ]
        steps = []
        for name, cmd, timeout in steps_spec:
            code, out = await _in_container(tmp, cmd, timeout)
            steps.append({"name": name, "ok": code == 0, "output": out.strip()[-OUTPUT_LIMIT:]})
            if code != 0:
                break  # no point running the tests of code that failed the scan
        return {
            "ran": True, "passed": len(steps) == len(steps_spec) and all(s["ok"] for s in steps),
            "steps": steps, "seconds": round(time.time() - started, 1),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
