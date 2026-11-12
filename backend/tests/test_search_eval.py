from evals import search_eval as se
from app.services.embeddings import hash_embed


def test_the_golden_set_is_well_formed_and_multilingual():
    g = se.load()
    ids = {p["id"] for p in g["corpus"]}
    assert len(g["queries"]) >= 30 and {q["lang"] for q in g["queries"]} == {"en", "hi", "hinglish"}
    assert all(q["expect"] in ids for q in g["queries"])
    assert len({q["id"] for q in g["queries"]}) == len(g["queries"])


def test_metrics_math():
    m = se.metrics([("en", 1), ("en", 3), ("hi", 5), ("hi", 2)])
    assert m["en"] == {"n": 2, "recall@1": 0.5, "recall@3": 1.0, "mrr": round((1 + 1 / 3) / 2, 3)}
    assert m["all"]["n"] == 4 and m["hi"]["recall@3"] == 0.5


def test_the_hash_baseline_runs_and_the_hybrid_blend_does_not_hurt_it():
    emb = lambda ts: [hash_embed(t) for t in ts]  # noqa: E731
    base, hyb = se.evaluate(emb), se.evaluate(emb, hybrid=True)
    assert base["all"]["n"] == hyb["all"]["n"] >= 30
    assert hyb["all"]["mrr"] >= base["all"]["mrr"] - 0.05   # lexical evidence must not make a lexical baseline worse
    assert hyb["en"]["recall@3"] >= 0.5                    # English keyword queries are findable even by the offline embedder
