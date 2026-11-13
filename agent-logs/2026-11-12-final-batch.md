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

## Fifth pass: the remaining agents (AGT-01..13 all built, each with stated limits)
Branch v2/agents-final. Tests first; the full backend suite was green before the last three items (505 passed; the only failures were the not-yet-implemented Doot tests, now passing).
- AGT-05 evidence adapters (Wikipedia, Wikidata, OpenAlex) with provenance, reliability caps, circuit breaker, model entailment that can only refuse. ADR 0007.
- AGT-01/02 Sutradhar + document/dispute/post-approval graphs (migration 0019). ADR 0008. test_infra enqueue test updated with a reason.
- AGT-04 Chitrakar (closed motif vocabulary, validator, audit, web renderer; brief + photo hash signed into the certificate; photo now chosen BEFORE signing).
- AGT-13 Nigrani + fixer (diff proposals only) + canary rule + incident screens + runbook. The fixer may not touch protected paths.
- AGT-09 Doot policy (fixed template, send window, auto-send for welcome only, governed switch default off).
- AGT-08 hybrid search + golden set + licences (ADR 0009). AGT-10 T2 view specs and T3 migration pipeline (migration 0020, ADR 0010). AGT-11 voice confirmation/privacy + Saathi multilingual eval (ADR 0011).
REVIEW NEEDED (always-human paths): migrations 0019, 0020; app/deps.py earlier; the whole of agents/fixer.py's PROTECTED list; services/certificates.py (the signed payload now carries `art`).
FINDING for the owner: live Saathi writes non-Latin names in Latin letters (ADR 0011).
Your local dev database is behind: run `cd backend && alembic upgrade head` (0017-0020 are not applied there; the CLI evals that touch the DB failed on it until I made the eval database-free).

## Sixth pass: the remaining non-agent work
- API-05 DONE (no migration needed: the outbox already stores each delivery's data). Replay keeps the delivery id and adds X-Pramaan-Replay: 1; payloads kept 30 days; deleted on erasure.
- API-06: Go and Kotlin SDKs WRITTEN, NOT COMPILED OR RUN (no toolchains). Python contract tests check their paths against the OpenAPI document and their webhook rule against the server's. First step for you: `go test ./...` in packages/sdk/go, `gradle test` in packages/sdk/kotlin.
- DSK-04 DONE and exercised in real Electron (16 desktop checks): console variant, queue badge.
- DSK-05 WRITTEN, NOT RUN: update channels (tested), per-OS signature checks, update-manifest check, staged-rollout workflow. The first tagged release is the first real test.
- DSK-06: ADR only; the Tauri spike needs a Rust toolchain that is not set up here.
- MOB-02: Capacitor scaffold with a tested safety config; not built on a device. Push needs a server-side token table (migration) and your Firebase files.

## Seventh pass: the "matters for the project" list (2026-11-13)
- Trust core: external-key (KMS) signer (AWS KMS ECC_NIST_EDWARDS25519/ED25519_SHA_512, Google EC_SIGN_ED25519; provider facts checked; fake-provider tests only), compromised-key marker
  (SIGNING_COMPROMISED_KEYS, trusted only for log entries before the reported time; the key stops issuing; published in the keys document), scripts/verify_rotation.py (runbook step 6 against a live API), runbook updated.
  Human review needed: core/keys.py, services/certificates.py, docs/security/key-rotation.md.
- Names are recorded exactly as the person wrote them (literal_name + prompt). Live Saathi eval: names 12/12 (was 6/12), state 12/12, field 8/12 (ADR 0011 updated).
- Hindi copy review sheet generated: docs/review/hindi-copy-review.md (91 strings + the one Saathi sentence in the backend).
- Browser suites re-run on the final code against the local docker database (migrated to head): Verify 12/12, pages 11/11, header 6/6 (test fixed: page grows while scrolling), widget 7/7, fact capture 3/3, case workbench 4/4,
  calibration 2/2, photographs 3/3 (test fixed: passes with or without an Unsplash key configured), plus a NEW smoke-newpages (published view, OAuth consent Allow/Deny/hostile redirect, off-site ?next= ignored) 3/3.
  Backend 606 passed; desktop 16 passed.
- Still not run: Go and Kotlin SDK tests (no Go; a Gradle run left only a problems report, probably the JDK 17 pin I removed), real AWS/Google KMS, a staging key rotation, DigiLocker (needs your partner approval).
