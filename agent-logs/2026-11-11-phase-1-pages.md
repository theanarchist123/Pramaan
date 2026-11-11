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
