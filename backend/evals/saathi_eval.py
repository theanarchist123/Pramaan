"""Saathi across languages (AGT-11): after one spoken or typed turn, did the draft profile get the right name, state and field?

    python -m evals.saathi_eval            # the offline mock: checks the plumbing only
    python -m evals.saathi_eval --live     # the real model from .env: the numbers that mean something

Scored per language and per field with exact match after the same normalisation the app uses (state and sector names go through normalize_state / normalize_sector).
A name that is not exactly what was said counts as wrong: a misheard or mistranslated name must never become a recorded fact.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
FIELDS = ("full_name", "state", "sector")


def load() -> dict:
    return json.loads((HERE / "saathi_golden.json").read_text(encoding="utf-8"))


def score_case(delta: dict, expect: dict) -> dict:
    from app.services.onboarding import normalize_sector, normalize_state

    def norm(field: str, v):
        if v is None:
            return None
        v = str(v).strip()
        return normalize_state(v) if field == "state" else normalize_sector(v) if field == "sector" else v

    return {f: norm(f, delta.get(f)) == expect[f] for f in FIELDS}


def summarise(rows: list[tuple[str, dict]]) -> dict:
    by: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for lang, res in rows:
        for f, ok in res.items():
            by[lang][f].append(ok)
            by["all"][f].append(ok)
    return {lang: {f: round(sum(v) / len(v), 2) for f, v in fs.items()} | {"n": len(next(iter(fs.values())))} for lang, fs in by.items()}


async def run(live: bool) -> dict:
    os.environ["LLM_MODE"] = "live" if live else "mock"
    from app.agents import saathi
    from app.llm.client import LLMError, LLMRefusal, get_llm
    from app.services.onboarding import profile_context

    if live and get_llm().mode != "live":
        raise SystemExit("--live needs LLM_MODE=live and an API key in .env")
    from types import SimpleNamespace

    blank = SimpleNamespace(full_name="New Profile", headline="", sector="", state="", city="", bio="", institutions=[], custom={}, claims=[])

    class _Quiet:  # the eval needs no database: agent events are simply dropped
        async def emit(self, *a, **kw):
            return None

    ctx = _Quiet()
    rows, errors = [], 0
    for c in load()["cases"]:
        try:
            turn = await saathi.interview_turn(ctx, profile=profile_context(blank), history=[], user_text=c["say"])
            delta = turn.profile_delta.model_dump()
        except (LLMError, LLMRefusal):
            errors += 1
            delta = {}
        rows.append((c["language"], score_case(delta, c["expect"])))
    out = summarise(rows)
    out["api_errors"] = errors
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    res = asyncio.run(run(a.live))
    print(f"mode: {'live' if a.live else 'mock (plumbing only)'}")
    for lang, m in res.items():
        if lang == "api_errors":
            continue
        print(f"  {lang:<9} n={m['n']:<3} name {m['full_name']:.2f}  state {m['state']:.2f}  field {m['sector']:.2f}")
    if res["api_errors"]:
        print(f"  model errors (counted as wrong): {res['api_errors']}")
    if not a.live:
        print("\n(offline mock: only checks the plumbing. Run with --live for model quality.)")


if __name__ == "__main__":
    main()
