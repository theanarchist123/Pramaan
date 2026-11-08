"""AI-authorship ledger: how much of this repository was written by AI agents?

Two independent measures, both computed from git so they can't be hand-waved:

1. Commits that carry a `Co-Authored-By:` trailer naming an AI model (the convention used by Claude Code).
2. Surviving lines of code (`git blame`) whose originating commit carries such a trailer.

Usage:  python scripts/ai_stats.py [--json]
Needs at least one commit. Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AI_TRAILER = re.compile(r"^Co-Authored-By:\s*(?P<who>.*(?:claude|anthropic|gemini|gpt|copilot|openai).*)$", re.I | re.M)
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".sql", ".html", ".yml", ".yaml", ".md", ".json", ".toml", ".dockerfile"}
SKIP_PARTS = {"node_modules", ".venv", ".next", "dist", "__pycache__", "pnpm-lock.yaml", "package-lock.json", "uv.lock"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout


def commits() -> list[tuple[str, str]]:
    """(sha, full message) for every commit."""
    out = git("log", "--format=%H%x1f%B%x1e")
    rows = []
    for rec in out.split("\x1e"):
        rec = rec.strip("\n")
        if "\x1f" in rec:
            sha, msg = rec.split("\x1f", 1)
            rows.append((sha.strip(), msg))
    return rows


def tracked_code_files() -> list[str]:
    files = git("ls-files").splitlines()
    return [
        f for f in files
        if (Path(f).suffix.lower() in CODE_EXT or Path(f).name.lower() == "dockerfile")
        and not (SKIP_PARTS & set(Path(f).parts)) and Path(f).name not in SKIP_PARTS
        and not f.endswith(("schema.d.ts", ".min.js"))
    ]


def blame_lines(path: str) -> Counter:
    """sha -> number of surviving lines in `path`."""
    try:
        out = git("blame", "--line-porcelain", "-w", "HEAD", "--", path)
    except subprocess.CalledProcessError:
        return Counter()
    return Counter(line.split()[0] for line in out.splitlines() if re.match(r"^[0-9a-f]{40} \d+ \d+", line))


def main() -> int:
    try:
        rows = commits()
    except subprocess.CalledProcessError:
        rows = []
    if not rows:
        print("No commits yet — commit your work first, then re-run.", file=sys.stderr)
        return 1

    ai_shas: dict[str, str] = {}
    models: Counter = Counter()
    for sha, msg in rows:
        m = AI_TRAILER.search(msg)
        if m:
            who = re.sub(r"\s*<[^>]*>", "", m.group("who")).strip()
            ai_shas[sha] = who
            models[who] += 1

    total_lines = ai_lines = 0
    for f in tracked_code_files():
        for sha, n in blame_lines(f).items():
            total_lines += n
            if sha in ai_shas:
                ai_lines += n

    pct = lambda a, b: round(100 * a / b, 1) if b else 0.0  # noqa: E731
    result = {
        "commits": len(rows),
        "ai_coauthored_commits": len(ai_shas),
        "ai_commit_share_pct": pct(len(ai_shas), len(rows)),
        "surviving_lines": total_lines,
        "ai_authored_surviving_lines": ai_lines,
        "ai_line_share_pct": pct(ai_lines, total_lines),
        "models": dict(models),
    }
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2))
    else:
        print("Pramaan — AI authorship ledger")
        print(f"  commits:                  {result['commits']}")
        print(f"  with an AI co-author:     {result['ai_coauthored_commits']}  ({result['ai_commit_share_pct']}%)")
        print(f"  surviving lines of code:  {result['surviving_lines']:,}")
        print(f"  written in AI commits:    {result['ai_authored_surviving_lines']:,}  ({result['ai_line_share_pct']}%)")
        for who, n in models.most_common():
            print(f"    {n:>4} × {who}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
