"""A risk score for a read-only plugin (AGT-10, tier T1): how much data could it touch, and how much could it return?

It only INFORMS the human who approves a plugin. It cannot approve anything and it never loosens the guard or the sandbox. Unreadable input is high risk.
"""
from __future__ import annotations

import ast

VIEWS = {"PublicProfile", "PublicClaim", "PublicEvidence", "PublicCertificate"}


def _high(reason: str) -> dict:
    return {"score": 100, "level": "high", "tables": [], "joins": 0, "bounded": False, "reasons": [reason]}


def assess(files: dict[str, str]) -> dict:
    main = next((src for path, src in files.items() if "test_" not in path.rsplit("/", 1)[-1]), None)
    if not main:
        return _high("No plugin code to assess")
    try:
        tree = ast.parse(main)
    except SyntaxError:
        return _high("The code could not be read")
    tables = sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in VIEWS})
    joins = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("join", "outerjoin"))
    selects = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "select")
    aggregates = any(isinstance(n, ast.Attribute) and n.attr in ("group_by", "count") for n in ast.walk(tree)) or any(
        isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "func" for n in ast.walk(tree))
    bounded = any(isinstance(n, ast.Attribute) and n.attr in ("limit", "fetchmany") for n in ast.walk(tree)) or aggregates

    score, reasons = 10 * len(tables) + 15 * joins + 5 * max(0, selects - 1), []
    if not tables:
        reasons.append("It does not read any public view")
    if len(tables) >= 3:
        reasons.append(f"It reads {len(tables)} different views")
    if joins:
        reasons.append(f"It joins {joins} time(s)")
    if not bounded:
        score += 40
        reasons.append("Nothing limits how many rows it returns (no limit and no aggregate)")
    score = min(100, score)
    return {"score": score, "level": "low" if score < 40 else "medium" if score < 70 else "high", "tables": tables, "joins": joins,
            "bounded": bounded, "reasons": reasons}
