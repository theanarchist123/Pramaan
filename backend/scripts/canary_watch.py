"""Judge a canary release (AGT-13). Prints the decision; exits 0 for promote, 2 for wait, 1 for rollback, so a deploy pipeline can act on it.

    python scripts/canary_watch.py --baseline-errors 3 --baseline-total 4200 --canary-errors 9 --canary-total 260 [--waited 12]

The numbers come from whatever your platform reports (request and 5xx counts per release). This script only decides; it deploys and rolls back nothing.
When it cannot tell (too little traffic for too long) it says rollback.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.canary import decide  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-errors", type=int, required=True)
    ap.add_argument("--baseline-total", type=int, required=True)
    ap.add_argument("--canary-errors", type=int, required=True)
    ap.add_argument("--canary-total", type=int, required=True)
    ap.add_argument("--min-requests", type=int, default=100)
    ap.add_argument("--waited", type=float, default=0.0, help="minutes since the canary started")
    ap.add_argument("--max-wait", type=float, default=30.0)
    a = ap.parse_args()
    d = decide(baseline_errors=a.baseline_errors, baseline_total=a.baseline_total, canary_errors=a.canary_errors, canary_total=a.canary_total,
               min_requests=a.min_requests, waited_minutes=a.waited, max_wait_minutes=a.max_wait)
    print(f"{d.action}: {d.reason}")
    return {"promote": 0, "wait": 2, "rollback": 1}[d.action]


if __name__ == "__main__":
    raise SystemExit(main())
