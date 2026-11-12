"""Search quality on a golden set of English, Hindi and Hinglish queries over a small fictional corpus (AGT-08).

    python -m evals.search_eval                                   # the offline hash embedder: checks the plumbing only
    python -m evals.search_eval --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
    python -m evals.search_eval --model intfloat/multilingual-e5-small --hybrid

No database: documents are embedded in memory and ranked by cosine similarity, optionally blended with a word-overlap score the way production search blends in
Postgres full-text (`directory.combine`). Prints recall@1, recall@3 and MRR per language. A model that this fastembed version does not support is reported, not guessed.
The production index is 384-dimensional: bge-m3 and multilingual-e5-large (1024) would need a migration of the vector column before they could be used.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).parent


def load() -> dict:
    return json.loads((HERE / "search_golden.json").read_text(encoding="utf-8"))


def doc_text(p: dict) -> str:
    return f"{p['name']}. {p['sector']}. {p['state']}. {p['text']}. {p['text_hi']}"


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)) or 1.0, math.sqrt(sum(x * x for x in b)) or 1.0
    return sum(x * y for x, y in zip(a, b)) / (na * nb)


def words(t: str) -> set[str]:
    return set(re.findall(r"[\wऀ-ॿ]{2,}", t.lower()))


def lexical(q: str, doc: str) -> float:
    qw = words(q)
    return len(qw & words(doc)) / len(qw) if qw else 0.0


def ranks(scores: dict[str, float], expect: str) -> int:
    order = sorted(scores, key=lambda k: -scores[k])
    return order.index(expect) + 1


def metrics(results: list[tuple[str, int]]) -> dict:
    """results: (language, rank of the expected profile). Returns per-language and overall recall@1, recall@3 and MRR."""
    out: dict = {}
    for lang in sorted({l for l, _ in results}) + ["all"]:
        rs = [r for l, r in results if lang == "all" or l == lang]
        out[lang] = {"n": len(rs), "recall@1": round(sum(r == 1 for r in rs) / len(rs), 3), "recall@3": round(sum(r <= 3 for r in rs) / len(rs), 3),
                     "mrr": round(sum(1 / r for r in rs) / len(rs), 3)}
    return out


def evaluate(embed, golden: dict | None = None, hybrid: bool = False) -> dict:
    """`embed(list[str]) -> list[list[float]]`."""
    g = golden or load()
    docs = {p["id"]: doc_text(p) for p in g["corpus"]}
    dvec = dict(zip(docs, embed(list(docs.values()))))
    results = []
    for q in g["queries"]:
        qv = embed([q["q"]])[0]
        scores = {}
        for pid, text in docs.items():
            s = max(0.0, cosine(qv, dvec[pid]))
            scores[pid] = (0.7 * s + 0.3 * lexical(q["q"], text)) if hybrid else s
        results.append((q["lang"], ranks(scores, q["expect"])))
    return metrics(results)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="hash", help="a fastembed model name, or 'hash' for the offline plumbing check")
    ap.add_argument("--hybrid", action="store_true", help="blend in word overlap, like production full-text")
    a = ap.parse_args()
    if a.model == "hash":
        from app.services.embeddings import hash_embed

        embed = lambda texts: [hash_embed(t) for t in texts]  # noqa: E731
    else:
        try:
            from fastembed import TextEmbedding

            m = TextEmbedding(a.model)
            embed = lambda texts: [list(map(float, v)) for v in m.embed(texts)]  # noqa: E731
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"Could not load {a.model}: {type(exc).__name__}: {exc}. This fastembed version may not support it.")
    res = evaluate(embed, hybrid=a.hybrid)
    print(f"model: {a.model}  hybrid: {a.hybrid}")
    for lang, m in res.items():
        print(f"  {lang:<9} n={m['n']:<3} recall@1 {m['recall@1']:.2f}  recall@3 {m['recall@3']:.2f}  MRR {m['mrr']:.2f}")
    if a.model == "hash":
        print("\n(the hash embedder is lexical, not semantic: this only checks the plumbing. Run a real model to compare.)")


if __name__ == "__main__":
    main()
