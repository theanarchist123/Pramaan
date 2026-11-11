# Phase 1 pages (no moodboard; spec-derived), 2026-11-11

Branches are stacked: v2/hardening -> pg-05-verify -> pg-08-onboarding -> pg-09-profile -> pg-10-directory -> pg-11-home ->
pg-12-agent-floor -> pg-13-transparency -> pg-14-developers. One commit per page. Not merged.

| Page | Branch | What changed |
|---|---|---|
| Verify | v2/pg-05-verify | five verdicts (new "replaced" from the backend), code boxes, QR scan, offline file check, forge mode on the one certificate, cascade M-04, seal M-01 |
| Onboarding | v2/pg-08-onboarding | status stepper from server enum, fact capture M-03 |
| Profile | v2/pg-09-profile | **I-9 fix**: public-source claims no longer counted as verified; paper-slip evidence M-10 |
| Directory | v2/pg-10-directory | field shelves, FLIP M-09 |
| Home | v2/pg-11-home | proof-table hero = live check of the newest real certificate |
| Agent Floor | v2/pg-12-agent-floor | Working/Idle text, motion-safe pulse only |
| Transparency | v2/pg-13-transparency | chain re-computed in the browser + in-memory tamper demo |
| Developers | v2/pg-14-developers | deep links + ARIA tab keyboard |

## Verification actually done
- `tsc --noEmit` and `eslint src` clean on every branch; `next build` passes on the stacked tip (pg-14).
- Backend: new `test_an_older_certificate_says_it_has_been_replaced_but_stays_genuine` passed. Full backend suite NOT re-run
  (nothing else in the backend changed).
## NOT verified (be honest)
- **No page has been exercised in a browser.** `apps/web/scripts/smoke-verify.mjs` is written but has never passed a run: the
  local API and Docker Desktop died mid-run. The other pages have no browser test at all.
- Chain verification in the browser was not run against a real log.
- Motion reduced-variants are written but not visually checked.
## Mistake and fix
- Commit 9863d33 accidentally included `apps/web/.next-smoke` build output (86 files). Removed in 5b56a21 and gitignored; history not rewritten.
## Not built (see docs/design/polish-queue.md)
Dossier two-column profile, search-mode directory, floor layout with handoff lines, ledger tape on Home, docs shell for Developers,
signed checkpoints, Hindi review of new strings. PG-13 polish pass still pending the moodboard.

# Phase 3
- **TRU-02** was already complete from Phase 0a (year/number guard in pariksha.py, confirmed-QID-only Wikidata, tests in test_phase0a.py). No change.
- **TRU-03** (v2/tru-03-forensics, off pg-14): `services/doc_forensics.py` deterministic signals (PDF incremental updates, editor
  producer, modified-vs-created date; image EXIF editor) + duplicate-document hash across profiles. Flags block the automatic claim
  upgrade (I-2). 6 pure tests pass. NOT verified: the Lipik integration + duplicate query against a real DB (Docker down; SQL
  compiles). NOT built: QR decode + issuer-endpoint verification (needs a decoder dependency and per-issuer endpoints; a decision for
  the owner), image re-compression/ELA heuristics (unreliable, deliberately skipped), font/layout anomalies.
- **TRU-09** (v2/tru-09-merkle, off tru-03): `core/merkle.py` RFC 6962/9162 root, inclusion and consistency proofs with verifiers;
  `/v1/transparency/checkpoint` (signed `pramaan-log-checkpoint-v1`), `/proof/{code}`, `/consistency?first=n`. 24 pure tests pass,
  exhaustive over sizes 1..19 plus a rewrite-detection test. NOT verified: the three endpoints against a real DB (Docker down).
  NOT built: daily independent publication and the RFC 3161 timestamp (needs a chosen external TSA/publisher: an ADR + owner
  decision, and a **(verify)** of the vendor), browser/verify-js consumption of proofs, witness cosigning.
  Note the existing hash chain is kept; the Merkle tree is a second, additive view over the same entries.

# Phase 1 finish (v2/pg-15-phase1-finish)
Built: Profile two-column dossier with sticky identity rail; Agent Floor handoff pipeline (M-11, moves only on real handoff events,
reduced-motion variant); Home ledger strip of real log entries. Verified only by tsc + eslint (Docker still down; no browser run).
Still not built in Phase 1: directory search mode, Developers docs shell, the other 23 motions, Hindi review, moodboard polish.

# Verification run (Docker up)
- test_agents.py 17 passed (new duplicate-document test included); the new Merkle endpoint test passes (checkpoint signature checked
  against the published key; inclusion and consistency proofs verified independently).
- **Verify browser test now PASSES: 12/12 steps, no browser errors** (five verdicts, forge mode, code input, recent checks, offline
  file check altered + genuine, reduced motion). It found two real bugs, fixed: (1) the "newer certificate" link was a Button rendered
  as a link and was not exposed as a link; (2) a mistyped 0/O produced no suggestion, which hid the whole explanation.
- Existing test fixed, with reason: test_flagged_document_on_a_published_profile... shared a byte-identical file with another test,
  which the new duplicate rule rightly flags; the fixture is now unique, the rule is unchanged.
- Still unverified in a browser: Onboarding, Profile, Directory, Home, Agent Floor, Transparency (chain check), Developers.
- Full backend suite not re-run on the stacked tip yet.

# Pages smoke test (apps/web/scripts/smoke-pages.mjs)
- HOME step PASSED in a browser (proof table, no mock screenshot). It exposed a design flaw: with the newest certificate revoked, the
  hero led with a failed check. The proof table now picks the newest certificate that checks out.
- The remaining steps (Directory, Profile, Transparency chain + tamper demo, Developers keys, Agent Floor pipeline, Onboarding redirect)
  are written but have NOT run: the Docker engine crashed mid-run (pramaan-db and pramaan-redis "Exited (255)"), the API then returned
  500 for DB-backed endpoints. Environmental, not a code result. Re-run once `docker compose up -d db redis` stays up.

# Pages smoke test: PASSES 7/7 (Docker stable)
Home, Directory (shelves), Profile ("confirmed" counts, evidence slip), Transparency (chain re-computed in browser, tamper demo breaks it,
undo restores), Developers (deep link + arrow keys), Agent Floor (five stations, text status), Onboarding signed-out redirect. No
browser console errors. Test fixes were races in the test (waiting for hydration/data), not page bugs.
Still browser-untested: signed-in Onboarding (chat, stepper, fact capture), the QR scanner camera path.

# Full backend suite on the stacked tip (v2/pg-15-phase1-finish)
**311 passed, 0 failed, 0 skipped (5m38s)**, Postgres+pgvector up. (Baseline before this work: 278.) The first full run found 1 failure:
eight tests upload a byte-identical sample credential, which the new TRU-03 duplicate rule correctly flags. The `client` fixture now
clears documents left by earlier tests; the rule is unchanged and has its own test.

# Phase 2: MFA at login (v2/adm-04b-mfa-login, off pg-15)
Staff login (/v1/admin/auth/login) now requires a TOTP or single-use recovery code whenever an authenticator is enrolled; no cookie
is issued without it; a wrong code counts toward the lockout (429); asking for the code does not. Successful MFA login opens the
step-up window. Staff who have not enrolled still sign in with a password so they can enrol. Console login page shows the code field
when the server asks. 4 new tests; test_mfa + test_admin_origin + test_mfa_recovery = 24 passed.
KNOWN GAP: a member-login Bearer token still reaches /v1/admin (the cookie split protects browsers only). With STAFF_MFA_REQUIRED the
enrolment gate and step-up still apply, but an enrolled staff member's password-only Bearer token is not code-checked. Closing it
means binding staff API access to the admin login (a breaking change for API clients/tests): needs an owner decision.

# Phase 2: claim override as four-eyes (v2/adm-07-override-four-eyes, off adm-04b)
Governed setting `claim_override_four_eyes` (default OFF so existing reviewer workflows and tests are unchanged; turning it on is itself
a four-eyes change). When ON, raising a claim to "confirmed by a reviewer" files an approval request (202); a different person with
claim.override approves it, and the approver may not be the profile's owner (I-10). Lowering a claim stays immediate (safe direction).
One function (`apply_claim_override`) changes claim status for both paths; the audit action is `claim.override.approved` for the second.
3 new tests; related suites 63 passed. NOT done: console UI for filing/approving this action (the generic approvals screen may list
it; not checked in a browser), and nothing turns the setting on, that is your decision.

# Phase 2: reviewer workbench (v2/adm-02-workbench, off adm-07)
Backend: GET /v1/admin/review/{id} (case detail: claims+evidence, documents as metadata + forensic flags only, never file/path/hash,
permissions incl. whether you hold the lock), GET /v1/admin/review/{id}/namesakes (Wikidata candidates beside the confirmed item).
Console: /case/[id] with claims + evidence, documents + flags, namesake panel, per-claim decisions (verify requires note + evidence
ref, shown up front), outcome + reason code + note, keyboard shortcuts (j/k, v/h/x, Ctrl+Enter), own-profile refusal.
Tests: 2 new backend tests (review workbench file 8 passed); NEW BROWSER TEST apps/admin/scripts/smoke-case.mjs PASSES 4/4 and checks
the DB (profile approved by reviewer, claim human). Bug found by it and fixed: the console login always sent unenrolled staff to the
security page even when MFA is not required (it would trap deployments that have not enforced MFA); login now returns mfa_required.
NOT done: opening the original document (separate audited step), claim-level evidence side-by-side, command centre, registry,
compliance modules.

# Phase 2: command-centre tiles (v2/adm-03-command-centre, off adm-02)
GET /v1/admin/overview: queue (open, unassigned, held, overdue, oldest hours, counts per reason code) for anyone with review.read;
approvals + registry counts only with approval.read; model call/failure counts only with agent_run.read. Sections a role cannot see
are omitted, not zeroed. Console front page shows them as tiles (warnings are text + number, not colour alone). 1 backend test
(review workbench file: 9 passed); the browser test now also checks the tiles (a reviewer sees Open cases, not Approvals): passes 4/4.
NOT done: trend lines/history (needs stored snapshots), SLA breach notifications, registry and compliance modules.

# Phase 2: registry + compliance (v2/adm-16-registry, off adm-03)
POST /v1/admin/registry/profiles/{id}/suspend|restore (profile.suspend; written reason 10+ chars; audited; not your own profile; step-up when
MFA is required; state-checked: suspend only from approved, restore only from suspended). Suspension hides the profile from every public
query (they already require status == approved) and from graph/stats; the owner still sees "suspended"; resubmitting cannot undo it.
GET /v1/admin/consents?profile_id= (consent.read, read-only). Web: ProfileStatus gains "suspended" (types, stepper, onboarding message).
4 new backend tests pass (tests/test_registry.py); web tsc + eslint clean.
KNOWN LIMITS: a suspended person's certificates still verify as genuine (a certificate is a signed historical fact; whether suspension
should also flag them is a policy decision, not made here). No console screens for suspend/restore or the consent view yet (API only).
Not done: merge duplicates (profile.merge), correct a profile (profile.correct), takedown processing, DSR export/erasure queue, retention.

# Phase 3: TRU-10 verify-js (v2/tru-10-verify-js, off adm-16)
packages/verify-js (@pramaan/verify): dependency-free WebCrypto ES module: canonical JSON, certificate verification (keys supplied by the
caller; key id must equal the SHA-256 of the key so a key cannot be swapped under another id), RFC 6962/9162 inclusion + consistency
verification, signed-checkpoint verification. TypeScript declarations. 10 tests pass against vectors produced by the BACKEND's Python
code (test/make-fixtures.py regenerates them): every inclusion proof for sizes 1..12, every consistency pair, signed checkpoint, tamper cases.
Web now uses it (lib/offline-verify.ts); Verify browser test still passes 12/12.
NOT done: the <pramaan-verify> web component and docs; moving apps/desktop onto the package (the desktop app is outside the pnpm
workspace and its verifier is synchronous CommonJS; its own 9 vectors still pass but it is a second copy); pinning a key fingerprint
inside the desktop app; checkpoint/revocation sync.

# Phase 3: TRU-08 Verifiable Credentials 2.0 (v2/tru-08-vc, off tru-10)
ADR docs/adr/0003 records what was checked at w3.org on 2026-11-11: VC DM 2.0, Data Integrity EdDSA and Bitstring Status List are W3C
Recommendations (15 May 2025); did:web is a Community Group DRAFT with "no official standing" (so it is a replaceable choice; the key
is also in /.well-known/pramaan-keys.json).
Built: core/vc.py (eddsa-jcs-2022 proofs, Multikey, base58btc, Bitstring Status List), services/credentials.py, api/vc.py:
GET /.well-known/did.json, GET /v1/certificates/{code}/vc, GET /v1/status/revocation/1 (signed). Migration 0013 (certificates.status_index;
human-review path; rehearsal passes). Signer.sign_raw added (core/signing.py is a human-review path: 3 lines).
CONFORMANCE: the signature reproduces the W3C's published eddsa-jcs-2022 worked example byte for byte (hashes + proofValue).
Tests: tests/test_vc.py 14 passed (W3C vector, tamper cases, outsider verification over HTTP using only did.json, revocation list agrees
with /v1/verify, unique indexes). Migration rehearsal passes.
A bug the rehearsal found in MY work, fixed: (1) DROP INDEX cannot remove a unique CONSTRAINT's index (DBs built from models have a constraint,
upgraded DBs an index): downgrade now drops the column; (2) rehearsal's hand-kept ADDED_COLUMNS list lacked the new column.
NOT verified: interoperability with an independent third-party VC verifier (the W3C vector match is strong evidence, not an interop
test); did:web behind the production CDN; DNSSEC (ops). The @vocab namespace is a placeholder that does not resolve.
NOT built: a web UI for "download as verifiable credential"; the VC in the desktop/web verifier (verify-js verifies the legacy
certificate and log proofs, not Data Integrity proofs yet); a second status list when 131,072 certificates are exceeded (the code
refuses with a clear error instead).

# Visual pass (v2/pg-16-visual-theme)
User pointed out nothing had visibly changed. True: the public site kept its own cream/orange palette; only the staff console used the tokens. Now:
colour system mapped to the Seal & Ink tokens (light + dark), paper-object component, stronger Home hero/steps, header underline. Contrast gate
extended (on-stamp, paper inks) and passing. Screenshots reviewed by me for Home (light/dark), Directory (dark), Verify (light).
Found by looking at screenshots: Verify code boxes wrapped; fixed. Tests: pages smoke 7/7 and Verify smoke 12/12 on the new theme; a Verify
step (reduced motion) had a fragile 800 ms timeout, fixed to measure "all checks present once the first appears".
NOT reviewed visually: Profile, Transparency, Developers, Agent Floor, Onboarding, the certificate, mobile widths, the staff console in the
new composition. Typography (typeface) unchanged.
