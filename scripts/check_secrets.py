"""Blocks secrets from reaching git. Run by the pre-commit hook; also usable by hand:

    python scripts/check_secrets.py            # scan what is staged (the default for the hook)
    python scripts/check_secrets.py --all      # scan everything git would track (staged + untracked, minus ignored)

Fails (exit 1) if it finds
  * a real .env / key file about to be committed,
  * any secret VALUE from your local .env inside a file, or
  * text shaped like a Gemini / Anthropic / Pramaan API key.
Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_NAME = re.compile(r"KEY|SECRET|TOKEN|PASSWORD|SIGNING|DATABASE_URL", re.I)
PATTERNS = {
    "Google/Gemini API key": re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    "Gemini key (AQ. format)": re.compile(r"AQ\.[0-9A-Za-z_\-]{30,}"),
    "Anthropic key": re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}"),
    "Pramaan API key": re.compile(r"pk_live_[0-9a-f]{8}_[0-9A-Za-z]{20,}"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "database URL with password": re.compile(r"postgres(?:ql)?(?:\+asyncpg)?://[^\s:@/]+:(?!pramaan@)[^\s@/]{6,}@(?!localhost|db[:/]|host\.docker)"),
}
FORBIDDEN_PATH = re.compile(r"(^|/)\.env($|\.(?!example$))|\.pem$|(^|/)signing\.key$|\.key$")


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "ignore")
    return [f for f in out.split("\0") if f]


def local_secret_values() -> list[tuple[str, str]]:
    env = ROOT / ".env"
    if not env.exists():
        return []
    found = []
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        placeholder = value.startswith(("http://localhost", "postgresql+asyncpg://pramaan:pramaan@", "change-me", "dev-only-"))
        if SECRET_NAME.search(name) and len(value) >= 12 and not placeholder:  # placeholders are public by design
            found.append((name.strip(), value))
    return found


def main() -> int:
    scan_all = "--all" in sys.argv
    files = (
        git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
        if scan_all
        else git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    )
    values = local_secret_values()
    problems: list[str] = []
    for f in files:
        if FORBIDDEN_PATH.search(f.replace("\\", "/")):
            problems.append(f"{f}: this kind of file must never be committed")
            continue
        path = ROOT / f
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        text = path.read_bytes().decode("utf-8", "ignore")
        for name, value in values:
            if value in text:
                problems.append(f"{f}: contains the value of {name} from your .env")
        for label, pat in PATTERNS.items():
            if pat.search(text):
                problems.append(f"{f}: looks like a {label}")
    if problems:
        print("SECRETS CHECK FAILED - nothing was committed:\n", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        print("\nRemove the secret (keep it in .env, which is git-ignored) and try again.", file=sys.stderr)
        return 1
    print(f"OK secrets check: {len(files)} file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
