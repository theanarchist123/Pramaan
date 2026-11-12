"""Turn a fixer proposal into a pull request (AGT-13). RUN BY A PERSON: the agent itself never does this.

    python scripts/incident_to_pr.py <incident id> [--push]

It reads the proposed diff from the incident, re-checks it against the current files (the same check the fixer used), applies it on a NEW branch with `git apply`,
commits it (with a trailer saying it was AI-proposed) and, with --push, pushes the branch and opens a pull request with `gh`. CI then runs the full test and eval
suites; merging needs human code review (T4). It refuses to run on a dirty working tree and never touches main.
"""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import fixer  # noqa: E402
from app.db import dispose_engine, get_sessionmaker  # noqa: E402
from app.models import Incident  # noqa: E402


def sh(*args: str, input_: str | None = None) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, input=input_, cwd=fixer.REPO_ROOT).stdout.strip()


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("incident")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()
    try:
        async with get_sessionmaker()() as s:
            inc = await s.get(Incident, uuid.UUID(args.incident))
            if inc is None or not (inc.proposal or {}).get("diff"):
                print("No checked patch on that incident.")
                return 1
            proposal = dict(inc.proposal)
    finally:
        await dispose_engine()
    if sh("git", "status", "--porcelain"):
        print("Your working tree has changes. Commit or stash them first.")
        return 1
    files = fixer._read(proposal.get("files", []))
    problems = fixer.check_diff(proposal["diff"], files)
    if problems:
        print("The patch no longer applies cleanly:", *problems, sep="\n  ")
        return 1
    branch = f"fix/incident-{args.incident[:8]}"
    sh("git", "checkout", "-b", branch)
    sh("git", "apply", "--whitespace=nowarn", "-", input_=proposal["diff"] + "\n")
    sh("git", "add", "-A")
    title = proposal.get("title", "Fix a recurring agent failure")
    sh("git", "commit", "-m", f"fix: {title}\n\nProposed by the fixer agent from incident {args.incident}. Needs human code review (T4).\n"
                              f"Rationale: {proposal.get('rationale', '')}\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
    print(f"Committed on {branch}. Add a regression test before you push (the fixer may not write tests).")
    if args.push:
        sh("git", "push", "-u", "origin", branch)
        print(sh("gh", "pr", "create", "--title", f"fix: {title}", "--body",
                 f"Proposed by the fixer agent for incident {args.incident}.\n\n{proposal.get('rationale', '')}\n\n"
                 "Needs human code review. Do not merge without a regression test.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
