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

## Second pass (same day)
Merged to main, backend suite 418 passed on the tip before the last small merges:
- API-03: problem+json (detail unchanged for clients) and RateLimit-* headers. Idempotency keys and cursor pagination NOT done.
- AGT-07: Prahari policy as versioned data (`agents/policy.py`), behaviour unchanged and pinned by a test, decisions record `policy_version`; shadow helper. prahari.py is an always-human-review path: PLEASE REVIEW that diff.
- AGT-08 (partial): filter chips + model-free fallback plan. Multilingual embedding evaluation NOT done (needs licences + golden set).
- API-09 (partial): read-only MCP server at POST /mcp; ADR 0005 records the spec versions checked.
- API-07 (partial): Postman collection generated from OpenAPI with a test.
- AGT-11 (partial): deterministic onboarding coverage; ready_to_submit needs the required fields. Voice NOT done.
- MOB-01 (partial): share target. DSK-02 (partial): clipboard verifier shortcut. DSK-03 (partial): login-item toggle.
- Admin console: Registry page (consents, suspend/restore).
Tests of mine fixed with reasons: Setu test (50-profile window), ETag tests (async client), Postman test (runtime plugin routes).
Not run: browser suites; desktop test run directly with node (pnpm tried to reinstall).
Deliberately not started (each needs a decision or a migration): API-02 OAuth (auth-code storage = migration), API-05 replay, API-10 usage counts (new table),
AGT-04/05/13 (model-quality or AI-written-code pipelines that need live-model evals and human review), DSK-04..06, MOB-02..03.

## Third pass
- API-10 merged (migration 0017, usage endpoint, admin abuse overview, usage bars, test-key option on Developers page).
- API-02 merged (migration 0018, OAuth code+PKCE, consent screen, grants list). Backend 432 passed, web build ok. REVIEW NEEDED (always-human paths): migrations 0017/0018, app/deps.py (oauth principal + path allowlist), services/oauth.py.
  Also fixed an open redirect risk in the web sign-in page (`?next=` is now same-site paths only).
  Open: no admin screen for registering/revoking OAuth clients by staff; clients are self-registered by any signed-in member (consider requiring review before a client can request profiles:write); no browser test of the consent screen.

## Fourth pass
Merged (backend 439 passed): API-06 (SDK types regenerated + CI staleness job + Python SDK additions + contract test), AGT-10 (plugin risk score, informs the approver only),
DSK-06 desk ADR 0006 (the spike itself NOT done), MOB-03 (shrink >4 MB photos before upload), AGT-05 (claim names must appear in the quote).
Still open: AGT-02 (graph refactor), AGT-04 (Chitrakar), AGT-13 (fixer agent: AI-written-code pipeline, needs human review design), AGT-05 model entailment/adapters,
API-05 replay (your decision), Go/Kotlin SDKs, DSK-04/05, MOB-02, voice, T2/T3 builder tiers, plus owner-only items.
