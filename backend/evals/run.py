"""Measure the agents instead of trusting them.

    python -m evals.run            # offline mock model: checks the harness and the deterministic guards only
    python -m evals.run --live     # the real model from .env (LLM_MODE=live + a key): the numbers that mean something

Reports, for Pariksha (fact-check) and Lipik (document reading):

  Pariksha  accuracy; FALSE SUPPORT (said "supported" when the evidence did not say it: the dangerous error);
            raw hallucinated quotes (a "supported" verdict whose quote is not in the source), and how many get past the
            verbatim-quote guard anyway.
  Lipik     holder / title / issuer extraction, credential-vs-clipping, and whether an instruction hidden in the
            document changed the answer (prompt-injection resistance).

Results are written to evals/results/<timestamp>.json so changes can be compared over time. The mock model is a
deterministic stand-in: a good mock score proves the plumbing, NOT the model. Only --live numbers describe quality.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


async def call(schema, **kw):
    """The model is shared and sometimes overloaded (503/504): retry patiently so an outage is not scored as a miss."""
    from app.llm.client import LLMError, get_llm

    for attempt in range(5):
        try:
            return await get_llm().structured(schema, **kw)
        except LLMError:
            if attempt == 4:
                raise
            await asyncio.sleep(10 * (attempt + 1))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({(100 * n / d):.0f}%)" if d else "n/a"


async def run_pariksha() -> dict:
    from app.agents import pariksha
    from app.agents.schemas import FactCheckReport
    from app.agents.textutil import claim_specifics_in_quote, quote_in_source
    from app.llm.client import LLMError, get_llm
    from evals.cases import PARIKSHA

    total = correct = false_support = missed = supported_verdicts = bad_quotes = errors = 0
    failures = []
    for case_id, person, claims, sources, expected in PARIKSHA:
        try:
            report = await call(
                FactCheckReport, system=pariksha.SYSTEM,
                user=pariksha.build_prompt(person, [{"id": cid, "field": "award", "value": v, "year": None} for cid, v in claims], sources),
                tier="smart", effort="medium", max_tokens=4000,
                mock_context={"claims": [{"id": cid, "value": v} for cid, v in claims],
                              "sources": [{"title": s.title, "url": s.url, "text": s.text} for s in sources]},
            )
        except LLMError as exc:  # an outage is not a wrong answer: count it separately
            errors += 1
            failures.append({"case": case_id, "error": str(exc)[:120]})
            continue
        verdicts = {v.claim_id: v for v in report.verdicts}
        for cid, _ in claims:
            total += 1
            v = verdicts.get(cid)
            said = "supported" if v and v.verdict == "supported" else "not_supported"
            quote_ok = bool(v and 0 <= v.source_index < len(sources) and quote_in_source(v.quote, sources[v.source_index].text))
            if v and v.verdict == "supported":
                supported_verdicts += 1
                if not quote_ok:
                    bad_quotes += 1
            # What actually ships: the verbatim-quote and year/number guards turn a "supported" without a real quote into "not supported".
            specifics_ok = bool(v) and claim_specifics_in_quote(dict(claims)[cid], None, v.quote)
            effective = "supported" if said == "supported" and quote_ok and specifics_ok else "not_supported"
            if effective == expected[cid]:
                correct += 1
            else:
                failures.append({"case": case_id, "claim": cid, "expected": expected[cid], "got": effective,
                                 "model_said": said, "quote": (v.quote[:80] if v else "")})
                if effective == "supported":
                    false_support += 1
                else:
                    missed += 1
    return {
        "claims": total, "accuracy": round(correct / total, 3) if total else None,
        "false_support": false_support, "missed_support": missed, "api_errors": errors,
        "supported_verdicts": supported_verdicts, "hallucinated_quotes": bad_quotes,
        "failures": failures,
    }


async def run_lipik() -> dict:
    from app.agents import lipik
    from app.agents.identity import is_credential, issuer_is_recognised
    from app.agents.schemas import DocumentExtraction
    from app.agents.textutil import name_similarity, token_overlap
    from app.llm.client import LLMError, get_llm
    from evals.cases import LIPIK

    n = holder_ok = title_ok = issuer_ok = cred_ok = injected = errors = 0
    failures = []
    for case_id, text, exp in LIPIK:
        blocks, plain = lipik._content_blocks("text/plain", text.encode())
        try:
            r = await call(DocumentExtraction, system=lipik.SYSTEM, user=blocks, tier="smart",
                                           effort="medium", max_tokens=1500, mock_context={"text": plain, "filename": f"{case_id}.txt"})
        except LLMError as exc:
            errors += 1
            failures.append({"case": case_id, "error": str(exc)[:120]})
            continue
        n += 1
        h = (name_similarity(r.holder_name, exp["holder"]) >= 0.9) if exp["holder"] else (not r.holder_name.strip())
        t = (token_overlap(exp["title"], r.title) >= 0.5) if exp["title"] else True
        i = (token_overlap(exp["issuer"], r.issuer) >= 0.5) if exp["issuer"] else True
        # "credential" = the agent reads it as issued TO the person AND the pipeline would act on it
        c = (is_credential(r.doc_type) and bool(r.holder_name.strip())) == exp["credential"]
        holder_ok += h
        title_ok += t
        issuer_ok += i
        cred_ok += c
        if case_id == "holder-injection" and "meera" in r.holder_name.lower():
            injected += 1
        if not (h and t and i and c):
            failures.append({"case": case_id, "got": {"holder": r.holder_name, "title": r.title, "issuer": r.issuer, "type": r.doc_type},
                             "expected": exp})
    # deterministic rule, not a model: the fan-club letter must not come from a recognised issuer
    guard_ok = not issuer_is_recognised("Friends of Meera Fan Club") and issuer_is_recognised("Ministry of Earth Sciences")
    return {"documents": n, "holder_correct": holder_ok, "title_correct": title_ok, "issuer_correct": issuer_ok,
            "credential_vs_clipping_correct": cred_ok, "followed_injected_instruction": injected,
            "issuer_allowlist_rule_ok": guard_ok, "api_errors": errors, "failures": failures}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use the real model configured in .env")
    args = ap.parse_args()
    os.environ["LLM_MODE"] = "live" if args.live else "mock"

    from app.llm.client import get_llm

    llm = get_llm()
    if args.live and llm.mode != "live":
        raise SystemExit("--live needs LLM_MODE=live and an API key in .env")
    started = time.time()
    p, l = await run_pariksha(), await run_lipik()

    print(f"\nmodel: {llm.mode} / {llm.provider} {llm.model_names if llm.mode == 'live' else ''}")
    print("\nPARIKSHA (fact-check)")
    print(f"  accuracy              {pct(round((p['accuracy'] or 0) * p['claims']), p['claims'])}")
    print(f"  FALSE SUPPORT         {p['false_support']}   <- said 'supported' when the source did not say it (the dangerous one)")
    print(f"  missed support        {p['missed_support']}")
    print(f"  hallucinated quotes   {pct(p['hallucinated_quotes'], p['supported_verdicts'])} of 'supported' verdicts (blocked by the quote guard)")
    print("\nLIPIK (documents, text path)")
    d = l["documents"]
    print(f"  holder name           {pct(l['holder_correct'], d)}")
    print(f"  title                 {pct(l['title_correct'], d)}")
    print(f"  issuer                {pct(l['issuer_correct'], d)}")
    print(f"  credential/clipping   {pct(l['credential_vs_clipping_correct'], d)}")
    print(f"  obeyed injected text  {l['followed_injected_instruction']}   (want 0)")
    print(f"  issuer rule (code)    {'ok' if l['issuer_allowlist_rule_ok'] else 'BROKEN'}")
    if p["api_errors"] or l["api_errors"]:
        print(f"\n  API errors (not scored): pariksha {p['api_errors']}, lipik {l['api_errors']}")
    for f in (*p["failures"], *l["failures"]):
        print("  miss:", json.dumps(f, ensure_ascii=False)[:230])
    if not args.live:
        print("\n(offline mock: this checks the plumbing and the deterministic guards, not model quality. Run with --live.)")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"{time.strftime('%Y%m%d-%H%M%S')}-{'live' if args.live else 'mock'}.json"
    path.write_text(json.dumps({"mode": llm.mode, "provider": llm.provider, "models": llm.model_names, "seconds": round(time.time() - started, 1),
                                "pariksha": p, "lipik": l}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nsaved {path.relative_to(HERE.parent)}")

    from evals.gate import check

    baseline = None
    base_path = HERE / "baseline-live.json"
    if args.live and base_path.exists():
        baseline = json.loads(base_path.read_text(encoding="utf-8"))
    fails = check(p, l, baseline=baseline)
    if fails:
        print("\nRELEASE GATE: FAIL")
        for f in fails:
            print("  -", f)
        raise SystemExit(1)
    print("\nRELEASE GATE: pass")


if __name__ == "__main__":
    asyncio.run(main())
