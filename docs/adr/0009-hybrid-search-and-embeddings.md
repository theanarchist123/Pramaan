# ADR 0009: hybrid search, and which embedding model (AGT-08)

Status: accepted for hybrid search; the embedding model stays as is (2026-11-12).

## Decision
Search now blends embedding similarity (70%) with Postgres full-text (30%, `ts_rank_cd` over name, headline, bio, sector, state, city, institutions and claim text, `simple` config, OR of the query's words),
then a small re-rank (a person asked for by full name goes first; an inferred sector only nudges). Hard filters (state, sector) apply to both sides. A lexical-only hit says "Matches the words you typed".

## Evidence (`python -m evals.search_eval`, 24 fictional people, 32 queries: 18 English, 9 Hindi, 5 Hinglish; one run on 2026-11-12, small, treat as indicative)
| model | mode | recall@1 | MRR (hi) | MRR (hinglish) |
|---|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 (current, 384-dim) | dense only | 0.94 | 0.89 | 0.82 |
| same | hybrid | 1.00 | 1.00 | 1.00 |
Hybrid fixed the Hindi and Hinglish misses that dense-only had. The offline hash embedder is lexical only and checks the plumbing.

## Licences checked (Hugging Face hub metadata, read 2026-11-12)
`intfloat/multilingual-e5-small`: MIT. `intfloat/multilingual-e5-large`: MIT. `BAAI/bge-m3`: MIT.

## Not done
- `intfloat/multilingual-e5-small` (384-dim, a drop-in size) is NOT supported by the installed fastembed, so it could not be compared. `bge-m3` and `multilingual-e5-large` are 1024-dim: using them needs a migration of the vector column and a re-embed.
  Do that only if a larger real golden set (not 32 fictional queries) shows the current model failing.
- No cross-encoder re-ranker (a licence and size decision for later).
