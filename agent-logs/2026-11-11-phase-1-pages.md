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

# Visual review of the remaining pages (screenshots, light/dark/390px)
Looked at: Profile, certificate result, Transparency, Agent Floor, Developers (dark), Home (mobile). Found and fixed:
1. Mobile header overflowed at 390px: Sign in and the theme toggle were cut off. Install now shows from md, the language button is icon-only on
   phones, and large-text/reduce-motion toggles show from sm (phones keep the OS-level settings). Measured: Sign in right edge 374 of 390, no
   horizontal scroll.
2. Agent Floor: Khoji-Pehle used the old "indigo", which now equals the stamp purple, so it matched Saathi. Gave it its own colour.
Not changed / noted: the Developers code block is a light panel in dark mode (readable, a little jarring); the certificate keeps its
tracked all-caps label (it is the artwork, not UI chrome); Profile leaves empty space under a short claim list (the sticky rail is fine).
Not yet reviewed: Directory (light), Onboarding signed in, staff console in the new composition, the other phone pages beyond Home.

# Visual review, second batch
Reviewed (screenshots): Directory + certificate result + Agent Floor at 390px; signed-in Onboarding consent + chat/profile on desktop and phone.
Fixed: (1) Agent Floor pipeline wrapped badly on phones (a dangling connector, a second row with none): now a vertical list with vertical
connectors under sm, horizontal from sm up. (2) Onboarding stepper showed a half-spinner on "Tell us about yourself", which reads as loading;
only the checking stage spins now, the current stage gets a still marker. Pages smoke 7/7 after the changes.
Still not reviewed visually: the staff console in the new composition; Transparency/Developers/Profile at 390px individually; Hindi layout.

# Home rebuilt to the section 6.1 layout (v2/pg-16-visual-theme)
User was right (twice): section 6 specifies a different LAYOUT and signature interaction per page (I had only recoloured and added bits), and
section 4.9 specifies live Unsplash API images on sector tiles / shelf headers / cover bands (the SectorImage component and backend service exist
but NO page used them).
Done for Home: editorial hero with a REAL certificate on a desk and an editable name (change a letter: the registry's /v1/verify/check says the
signature is broken and the seal cracks, "NOT VALID"); bento "Browse by field" (14 tiles, two large, SectorImage with duotone + attribution,
link to /directory?sector=X which now pre-selects the field); the step-by-step proof table moved below.
Unsplash facts, checked in the docs on 2026-11-11: the API needs the application's access key (Authorization: Client-ID ...) for every request
(users need no login); photos are hotlinked from images.unsplash.com. UNSPLASH_ACCESS_KEY is EMPTY in .env and the approved-image set is empty
(/v1/images/sector/Science returns []), so tiles show the sector-colour pattern until a key is set and a person approves photos one at a time
(spec: no bulk import). The staff console has NO page for that approval yet (endpoints exist): to build.
Bugs found by the new tests/screenshots and fixed: certificate (1123px) forced the page wider than a phone (grid column min-width); tablet header
overflowed at 768 (compact header until lg); Verify code boxes overflowed at 360 and were 21px (now 26-30px, "PRM-" prefix hidden below 440px).
New permanent test step: no page scrolls sideways at 360/390/768/1024/1280 (pages smoke 8/8). Verify smoke 12/12.
Known: Verify still overflows by 11px at 320px wide (not in the test widths). Hindi strings for the new Home text are not written (English only).
Not yet redesigned to section 6: Directory (cover-band shelves + separate search mode), Profile (dossier with cover band + "Show what's proven"),
Onboarding (fact capture), Agent Floor (stage with travelling tokens), Transparency (ledger tape), the header (compress on scroll, account menu,
mobile bottom tab bar), the command palette.

# Photograph curation + Unsplash slot tests (v2/pg-16-visual-theme)
- Staff console /images: search Unsplash, look at candidates, approve ONE at a time into a field + slot (tile / cover band / empty state), remove
  approved ones. No bulk import; nothing downloaded or re-hosted. Without UNSPLASH_ACCESS_KEY the search says exactly what to do. Browser test
  apps/admin/scripts/smoke-images.mjs passes 3/3 (sign in, 14 fields, empty approved list, actionable no-key message).
- Public site test (pages smoke step "UNSPLASH SLOTS"): with an approved photo (a clearly fake "Test Photographer", intercepted network; nothing
  written to the DB) the tile hotlinks from images.unsplash.com, keeps the ixid, is sized with w/q/fm params, is fetched by the BROWSER, and the
  credit has two linked, utm-tagged anchors. Passes.
- Bento grid fixed to fill evenly (two large tiles span half the row each on desktop).
- PERFORMANCE: measured. Production build: first API call at 289 ms, proof table done at 2.2 s; Home first-load JS 194 kB. The long-running dev
  server degraded (JS took ~10 s to hydrate and later never finished in 60 s): dev-server slowness, not an app problem. Pages smoke 9/9 passes
  against the production build (next start, port 3013).
- STILL NEEDED FROM THE OWNER: register a free Unsplash app, set UNSPLASH_ACCESS_KEY in the backend .env, restart the API, open the console
  /images and approve photos. Until then tiles show the sector-colour pattern.

# Directory rebuilt to the section 6.2 layout (v2/pg-16-visual-theme)
Two modes in one page. BROWSE: shelves, each with a cover band (SectorImage purpose=cover: approved attributed Unsplash photo with the sector duotone,
else the sector-colour pattern) with the field's icon + name + "See all N", then ONE horizontal snap-scrolling row of people cards.
SEARCH: a ranked ordered list (rank, name, headline, field + place, "Why this person" reasons, match score as number + bar) so no result appears
without a reason. Components: directory/shelf.tsx, directory/result-row.tsx.
Browser test (pages smoke, production build on :3013): 9/9 steps passed on the run that completed: shelves with sideways-scrolling rows; a real
query returns a ranked list, rank 1 first, every top-level result explains itself. Two test bugs of mine were fixed on the way (header "Search"
button was matched instead of the form; nested bullets were counted as results).
CAVEAT, honest: that run still exited non-zero because of console errors. They were CORS-masked HTTP 500s: the API log shows
ConnectionResetError / connection_lost talking to Postgres (engine already has pool_pre_ping=True), and the Docker engine later stopped
responding altogether (`docker info` prints nothing). Environmental (Docker Desktop on this machine), not an app fault, but it means I do not have a
fully green run of the final test file. Re-run after `docker compose up -d db redis`.

# Baseline + Profile / Transparency / Onboarding to spec (v2/pg-16-visual-theme), 2026-11-12
- FULL BACKEND SUITE on the stacked tip with Docker up: **340 passed, 0 failed** (5m16s).
- Pages smoke on the production build: **10/10 pass, no console errors** (first fully green run). Fact-capture smoke 3/3.
- Profile (6.3): cover-band slot (SectorImage, falls back to the gradient) and "Show what's proven": marks only sentences that repeat, word for
  word, a claim the SERVER marks confirmed (document/issuer/reviewer); the legend says exactly that and that unmarked != false. Browser test seeds
  a profile through the real API and asserts exactly one sentence is marked.
- Transparency (6.6): nothing is checked until the button "Verify the whole chain in your browser"; progress bar while this browser re-computes
  every SHA-256 link; ledger tape with a rail and link dots; newest 25 shown + "Show 50 more" (a broken link is always revealed).
- Onboarding fact capture (M-03): the chat marks the exact words each new fact came from. This needed a BACKEND change, found while building it:
  chat claims stored the model's reworded VALUE as the "chat quote", so with a real model nothing would have matched (the mock hides this because
  its value equals the sentence). ExtractedClaim now has source_quote (the model must copy the person's words), and the server stores it only if
  it is a literal case-insensitive stretch of the person's message (literal_span); otherwise it falls back to the value. 2 new unit tests.
  NOT verified against a real model: whether Saathi follows the instruction well (LLM_MODE=mock here).
- Test infra: bypassCSP in the test context only (Playwright's waitForFunction is blocked by the app's CSP, which is unchanged).
- Still not to spec: Agent Floor (a public replay of RECORDED real runs needs a privacy decision: run messages can contain names), header
  (compress on scroll, account menu, mobile bottom tab bar), command palette people preview, Hindi copy, Unsplash photos (owner step).

# Header to spec 6.0 (v2/pg-16-visual-theme)
Public nav is four places (Directory, Verify, Transparency, Developers); Mission Control and Admin leave the header (staff console is in the account
menu for admins). Account menu (shadcn DropdownMenu): My record / Sign in, dark mode, larger text, reduce motion (checkbox items that report
state and really change the page), Install app (via a new useInstall hook), Sign out. Header compresses on scroll (instant height change: no
animation on layout properties). Phones: a bottom tab bar (Directory, Verify, Get listed or My record, Search) with safe-area padding; main reserves
space so content is never covered. New strings in English AND Hindi (the Hindi object is typed against the English keys; Hindi wording is mine and
needs a native-speaker review). Browser test apps/web/scripts/smoke-header.mjs 6/6 (needs no API). Test bugs of mine fixed on the way (menu stays
open after a checkbox; role queries skip hidden elements; main includes its own padding).
Not done: the command palette's People preview pane and `?` shortcuts overlay (spec M-24), footer strip "Sealed N certificates", offline banner.

# Agent Floor to spec 6.7 (v2/pg-17-agent-floor)
You did not answer the privacy question, so I took the safe default: the public replay may only ever use a run on a profile flagged is_demo (fictional).
GET /v1/agents/replay: latest finished verify_profile run on a demo profile; payload = agent, kind, message, confidence, t_ms offset; NO profile, user
or owner id; outcome sealed / with_reviewer / stopped from the profile's final status; {"available": false} when there is no demo run (it never falls
back to a real person). 2 backend tests incl. "a real profile's run is never returned" and "no identifiers in the payload".
Web: components/agent-floor/replay.tsx: five stations, a token (motion layout) that rests at the acting agent, play/pause/replay, event log, honest
outcome line; reduced motion lists the whole run at once. The dead right-hand panel for non-admins is gone: the roster is full width, the live feed
stays for admins. Browser test: a real run is seeded through the API; pages smoke 11/11 on the production build.
Limits: the replay shows what the demo run emitted (the mock LLM, so it ends "with a reviewer": no Wikipedia match); route is still /mission-control
(spec: /how-it-works/live); Saathi's chat-turn events are filtered out of verify runs by design.

# TRU-05 DigiLocker spike and TRU-11 key-rotation runbook (v2/tru-05-11-adr-runbook)
TRU-05: docs/adr/0004. Read the official DigiLocker partner FAQ + onboarding FAQ. Facts: register on the API Setu partner portal with a DigiLocker
account; apply as Requester with a valid use case + org documents (PoI, authority letter, PAN, GST, incorporation); OAuth 2.0 + OIDC with user
consent; non-India firms need an Indian mobile + a server in India. NOT STATED by the sources (so not assumed): eligibility of a private
registry, fees, sandbox steps, storage/reuse limits, which academic/award issuers publish. Decision: do NOT build (cannot be tested without
partner approval); the `issuer` status seam already exists; next steps are the owner's (eligibility, counsel on DPDP, issuer list).
TRU-11: docs/security/key-rotation.md + tests/test_key_rotation.py (2 pass): after a rotation old certificates verify with the OLD key id, new
ones with the new one, both keys are in pramaan-keys.json AND did.json; dropping the retired PUBLIC key breaks old certificates (the mistake the
runbook warns about). KNOWN GAPS written into the runbook: no compromised-key marker (the transparency log is the fallback check) and no KMS/HSM
signer (provider Ed25519 support must be verified). No staging rotation was performed.

# TRU-07 calibration report (v2/tru-07-calibration, off tru-05-11)
services/calibration.py + GET /v1/admin/calibration (agent_run.read): from CLOSED review cases (approved/rejected by a person): how people decided per
escalation reason code, and a SHADOW RUN: for candidate thresholds from the 0.90 floor up to today's threshold, which past escalated cases would have
been auto-approved and how many of those people actually rejected. It is a REPORT: it applies nothing (I-1: rules decide; the threshold is a governed
setting changed by two people, floor 0.90) and says so in its note; below 30 closed cases it says the numbers are anecdotes. 4 backend tests (exact
numbers, floor respected, role gating). Console page /calibration (shown only with agent_run.read), browser test 2/2 (auditor sees it, reviewer is not
offered it and the API refuses). Reason codes already existed (ADM-06).
NOT done (AGT-07, Phase 4): policy-as-config with versions, a promotion workflow for candidate policies, any automatic use of the numbers.

# TRU-04 identity binding (v2/tru-04-identity-binding, off tru-07)
Two ways to show a person controls something tied to an institution; neither proves WHO they are, neither approves anything.
(1) Institutional email: POST /v1/profiles/{id}/identity/email -> 6-digit code (hashed, 15 min, 5 attempts, 5/hour) -> /email/confirm. Free-mail domains
(Gmail, Yahoo, Outlook...) and IP literals are refused. Only the DOMAIN is kept; the address is never stored or returned.
(2) A code on a page: /identity/page returns a token to publish; /identity/page/check fetches EXACTLY that https URL through the SSRF guard (private/
internal addresses refused, the checked IP pinned, no redirects, size cap) and binds the HOST only if the token is really there.
Reviewers see VERIFIED bindings (kind + domain/host) in the case detail; pending ones are never shown. Prahari is untouched. Phone OTP not built (needs an
SMS provider). Migration 0014 (new table; rehearsal passes). 7 tests.
NOT built: an onboarding UI for it (API only so far), showing a binding publicly, any scoring use of it.

INCIDENT, disclosed: my first identity tests did not turn SMTP off, and the developer's real .env has SMTP configured, so about FIVE test sends went out
through the owner's mail account (a 6-digit "Your Pramaan identity code" message) to made-up addresses meera@iisc.ac.in / a@iisc.ac.in at a REAL
institution's domain. Existing tests were careful (they set smtp_host "" or replace _smtp_send); only these new ones leaked. Fixed at the root:
tests/conftest.py now has an autouse guard that turns SMTP off and makes outreach._smtp_send raise in EVERY test unless the test replaces it itself,
with a test proving it; test addresses are now on the reserved domain uni.example. The owner should check the mail account's Sent folder for those messages.

# Merge to main, 2026-11-12 (done at the owner's explicit request: "merge all the branches... do it urself")
All 24 unmerged v2/* branches (hardening ... tru-04-identity-binding, one linear stack) were merged into main in order with --no-ff, one merge commit per branch
(24 merge commits), no conflicts. Pre-push check: `git diff origin/v2/tru-04-identity-binding main` is EMPTY, i.e. main's tree is exactly the tip that
was tested (backend 357 passed, 0 failed; pages smoke 11/11; header 6/6; fact-capture 3/3; Verify 12/12; calibration 2/2). Pushed with a normal push (no force).
Two generated files blocked the merge and were discarded/removed: apps/admin/tsconfig.tsbuildinfo (untracked build cache) and a one-line change to
apps/admin/next-env.d.ts (rewritten by Next on every build). The remote v2/* branches were NOT deleted. The earlier "do not merge to main" rule was superseded
by this explicit instruction.
