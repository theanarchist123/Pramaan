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
