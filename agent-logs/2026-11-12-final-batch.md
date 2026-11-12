# 2026-11-12 final batch (branch v2/final-batch)

Done (tests first, each its own commit):
- AGT-12: `evals/gate.py` release gate (no false support, no obeyed injection, issuer rule intact, no unscored run; live runs also fail on an
  accuracy drop vs `evals/baseline-live.json`, which does not exist yet: the owner must record one from a live run). Nightly workflow
  `.github/workflows/evals-nightly.yml` (live only if the `ANTHROPIC_API_KEY` secret is set).
- AGT-01 (partial): `agents_paused` governed kill switch; verification then escalates to a human without any model call. Budgets and a supervisor
  agent are NOT done. Note: if the settings read fails, `governed.get` falls back to the default (not paused), so the switch fails open on a DB outage.
- API-03 (partial): ETag / If-None-Match on anonymous public GETs. Idempotency keys, problem+json and rate-limit headers are NOT done.

Verification: new unit tests pass; the DB-backed tests (including the ETag round-trip) were skipped because Docker was down. The full backend suite
and browser suites were NOT re-run on this branch. Not merged to main for that reason.

Still open: AGT-02/04/05/07/08/10/11/13, API-01/02/05/06/07/09/10, DSK-02..06, MOB, owner-only items listed in earlier logs.

## Later the same day (Docker back up)
- Full backend suite on the merged tip: 395 passed. Two ETag tests I wrote were calling the async client synchronously; fixed (my bug, not the code).
- API-01 (partial): read-only `pk_test_` keys (creation refuses write scopes; authentication clamps scopes again). No migration needed.
- API-05 NOT done on purpose: replaying a delivery needs the payload stored, which needs a migration (always-human-review path) and
  stores personal data in a table that today holds none. Decision for the owner: store payload hash + event id and rebuild on replay, or store payloads.
