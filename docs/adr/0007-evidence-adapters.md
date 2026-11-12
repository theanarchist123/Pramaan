# ADR 0007: evidence adapters and the entailment check (AGT-05)

Status: accepted (2026-11-12).

## Decision
Public evidence comes from pluggable adapters (`backend/app/evidence/`): Wikipedia, Wikidata (only the item the applicant confirmed), and OpenAlex (publications and co-authors).
Each document carries its source, retrieval time (UTC) and a SHA-256 of exactly the text used, plus a reliability prior. A source's reliability caps the confidence it can give a claim,
and web evidence never exceeds 0.9. Adapters have timeouts and a circuit breaker; a failing source means less evidence, never an error and never an approval.

Pariksha then applies fixed guards in order: the quote is verbatim in the source, the claim's numbers and distinctive names appear in it, the namesake defence passes for common names,
and a separate model call judges `supports | contradicts | unrelated`. That call can only refuse or contradict: `unrelated` and any failure leave the claim for a person (I-1, I-2).

## What was checked (official source: https://help.openalex.org/api/authentication, read 2026-11-12)
- OpenAlex basic use needs no key; a free key (sent as `api_key` or a bearer token) raises the daily budget. Limits: 10 requests per second without a key, 30 with one; `429` means wait.
  We send an optional `OPENALEX_API_KEY` and a contact in the User-Agent when `WIKIMEDIA_CONTACT` is an email.
- An author is used only when their last known institution matches one the applicant gave: no institution, no OpenAlex evidence (namesake defence).

## Not done
- Official honour lists, gazette notifications, institutional pages and company registries: each needs its terms checked first.
- The entailment model has not been measured against a labelled set with a live model. The offline mock only checks the plumbing (`python -m evals.run --live` is the real test).
- The stored retrieval time is the evidence row's creation time; a separate column would need a migration.
