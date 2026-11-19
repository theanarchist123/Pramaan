# Demo-readiness plan (DR)

Written 2026-11-19, from the product review of the live site and staff console against the "AI-Native Who's Who India Registry" brief and
Wildcatter's product ethos (launch fast, strong design, real traction).

**Goal:** in four weeks, a registry the Sir can open on his phone and trust in 30 seconds. Real people with faces, certificates that check,
no test data, no waiting for a sleeping server, and 30 to 50 real members from one community.

**Rules:** AGENTS.md applies to every task. One PR per task ID, tests first, invariants I-1..I-10 hold. Tasks marked **human review** touch
always-human-review paths. Tasks marked **owner** need you, not an agent: accounts, money, people, or a product decision.

Size: S = under half a day, M = 1 to 2 days, L = 3 or more days.

---

## Phase 0: today (stop the bleeding)

| ID | Task | Who | Done when |
|---|---|---|---|
| DR-00a | On Render, restore `SIGNING_KEY_B64` to the value in the repo-root `.env` (key id `407e647871b4520b`) and set `SIGNING_RETIRED_PUBLIC_KEYS=RoGxA0OJoZhjntR7nM7U8xHGaBK6fI2CCxWuoMe_qpU`. | owner | All 42 live certificates verify (agent re-runs the check). The startup log has no "SIGNING KEY PROBLEM" line. |
| DR-00b | Push `main` (contains the unknown-key fix and the phone layout fix). Let Vercel and Render redeploy. | owner | The live verify page shows the new "Cannot be confirmed right now" verdict only if a key is missing. |
| DR-00c | Confirm email: staff console, "Send test email". Then request a code on /onboard with a normal account. | owner | The code arrives. If not, the bracketed reason in the error says what to fix. |
| DR-00d | Write down where the signing key lives (password manager), so it is never lost or overwritten again. | owner | One sentence added to `docs/security/key-rotation.md` about where the owner keeps the backup (not the key itself). |

---

## Phase 1: first impression (week 1)

What the Sir sees in the first 30 seconds: a sleeping server, test profiles with green ticks, and no faces.

| ID | Task | Why | Where | Done when | Size |
|---|---|---|---|---|---|
| DR-01 | **Clean the registry data.** A script that lists every profile with its kind (seeded / real / test) and, with `--apply`, marks seeded people `is_demo=true`. Test profiles go through DR-02. | No live profile has `is_demo` set, so all 41 invented or test people show as real. The "Fictional demo" label already exists in the UI. It just never fires. | `backend/scripts/curate_registry.py` | Dry run lists all 42 with a proposed action. After `--apply`, every seeded person shows "Fictional demo" on cards and profiles. Test: seeded profile flagged, real profile untouched. | S |
| DR-02 | **Staff action: take a profile off the directory.** Needs a reason. Revokes its certificates with that reason, hides the profile, writes the audit log, and is refused on your own profile (I-10). | Today the only way to remove a profile is the person deleting their own data. Staff cannot remove "Mansory Deal". | `backend/app/api/admin.py`, console People page. **human review** (RBAC) | Test: removed profile disappears from search and `/p/...`, its certificate verifies as "Revoked", the audit row exists, own-profile attempt returns 403. | M |
| DR-03 | **Decide on the real profiles that exist** (Nikhil Rajesh Kadam, Arunima Nikhil Kadam, Roshan Yadav): keep, or take off with DR-02. | Keep real people only if they are complete and presentable. | owner decision | List decided. | S |
| DR-04 | **No sleeping server.** Either move the API to an always-on Render instance (paid), or add a scheduled ping to `/healthz` every 10 minutes. | The first visit took about 19 s. A demo cannot start with a spinner. | `.github/workflows/keep-warm.yml` or Render plan. **owner** picks. **(verify)** Render's current free-instance sleep and monthly-hours rules and paid price on render.com, recorded in `docs/adr/`. | Cold first load under 3 s on three checks spread over a day. | S |
| DR-05 | **Connection banner that doesn't look broken.** Wait about 4 s before showing it. Say "Waking up the server…" with a progress line, not "We can't reach the server". Never cover the logo or the menu. | On desktop it overlaps the logo and the nav on the first visit. | `apps/web/src/components/...` (connection banner), `floating-nav.tsx` | Playwright: with the API delayed 8 s, the banner appears after 4 s, below the nav, and disappears once the API answers. | S |
| DR-06 | **Faces.** Ask for a photo at the end of onboarding and on "My page" (upload already exists: `POST /v1/profiles/{id}/photo`). Show photos on cards, profiles and certificates. Demo people keep illustrated field avatars: never stock photos of people (AGENTS.md). | A who's-who with only initials feels like a database. | `components/onboarding/photo-upload.tsx`, `result-card.tsx`, `p/[slug]/page.tsx` | A member who uploads a photo sees it on their card, profile and next certificate. A profile without a photo shows a designed field avatar, not two letters. | M |
| DR-07 | **Bios without guessed gender.** The bio writer uses the person's name, or the pronouns they gave. It never guesses "he" or "she" from a name. | The live profile bio guessed "He". | Saathi/bio prompt, `evals/` | New eval cases: no gendered pronoun appears unless the person stated one. Live eval passes. | S |
| DR-08 | **English-only screens.** Hide the language switcher (desktop menu and phone sheet), default to English, keep the Hindi files unused. Hindi typed into search and Saathi keeps working. | Unreviewed Hindi on a trust product is a risk, and the early users read English. | `floating-nav.tsx`, `mobile-shell.tsx`, `lib/i18n.tsx`, `AGENTS.md`, `docs/adr/0012-english-only-ui.md` | No switcher anywhere. Hindi search ("सौर ऊर्जा वैज्ञानिक") still returns results. ADR says what brings Hindi back (a native reviewer signs off `docs/review/hindi-copy-review.md`). | S |

---

## Phase 2: page polish (weeks 1 to 2)

| ID | Task | Done when | Size |
|---|---|---|---|
| DR-09 | **Home: real proof.** Replace generic copy below the hero with three recently verified real members and "N people verified this month". Hide the strip while fewer than three real members exist. | Shows live data. Shows nothing invented. | S |
| DR-10 | **Directory search feedback.** While searching: skeleton cards plus the text "Searching for …". The button stays the brand colour and shows a spinner. Results say how many matched and why. | Playwright: the text appears within 100 ms of pressing Search. | S |
| DR-11 | **Network view: fix or remove.** Today it is a few dots in a corner. Either full width, centred, with names on hover, or removed until there are 50+ real people. **owner** picks. | Decision made. If kept, the graph fills its panel at 1440 and 412 widths. | S/M |
| DR-12 | **Onboarding consent.** Explain why "Start" is disabled ("Tick the box above to start"). Web research becomes opt-in (unticked by default) with one line on what it does. | Test: the default request sends `consent_web_research=false`. Disabled button has a visible reason. | S |
| DR-13 | **Verify on desktop.** Replace "this browser can't scan" with "Scan the QR with your phone camera, or type the code". | Copy changed. Smoke test updated. | S |
| DR-14 | **Transparency in plain words.** Top: "42 certificates published. None altered. Last checked: …". The hash table moves under "Technical log". Remove the empty row of boxes. | A non-technical reader understands the first screen. The empty boxes are gone at all widths. | S |
| DR-15 | **Developers out of the main menu.** Footer link only (desktop), and inside "More" on phone. | Main nav: Find people, Get listed, Check, Sign in. | S |
| DR-16 | **Catch squeezed text automatically.** Extend `scripts/phone-audit.mjs`: flag any text block narrower than 120 px holding more than 20 characters (the bug fixed on 2026-11-19 overflowed nothing, so the audit missed it). | The audit fails on the old home strip and passes now. | S |

---

## Phase 3: staff console for real reviewers (week 2)

| ID | Task | Done when | Size |
|---|---|---|---|
| DR-17 | **See the document while judging it.** Open the uploaded file beside the claims (image or PDF). Each opening is logged with the reviewer and time. Watermark the view with the reviewer's name. **human review** (document access). | Reviewer sees the file without leaving the case. The audit log shows each opening. Non-reviewers get 403. | M |
| DR-18 | **Plain language in the console.** Reason dropdowns show labels ("Evidence checked"), not codes (`EVIDENCE_CHECKED`). Remove the "Your permissions: …" line. Move "Send test email" and "Reindex search" to a Settings page. | No raw code appears in any dropdown. Review home has no developer buttons. | S |
| DR-19 | **Show confidence in the queue.** Each case shows the confidence score. A "Clear cases" filter shows cases where every claim has document or issuer evidence and confidence is at least 95 %. A person still clicks approve (I-1). | Score visible and sortable. The filter's rule is a deterministic function with tests. | M |
| DR-20 | **Fewer sections.** Primary: Review, People, Follow-ups. Everything else (registry, builder, calibration, incidents, images, security) goes under "Advanced". | Nav shows three items plus "Advanced". | S |

---

## Phase 4: traction (weeks 2 to 4)

| ID | Task | Who | Done when | Size |
|---|---|---|---|---|
| DR-21 | **The 3-minute demo script.** Sign up by chatting, profile appears, certificate issued, scan the QR with a phone, then show an edited certificate failing the check. Includes a prepared tampered file and a fallback if the network is slow. | agent writes, **owner** rehearses | `docs/demo/script.md`. Rehearsed twice on the live site on a phone. | S |
| DR-22 | **"Nominate someone".** Anyone can nominate a person (name, email, why). Pramaan sends a fixed-text invitation (I-7: no links or addresses the model added). Nothing is published until the person joins and consents (I-5). | agent | A nomination produces exactly one invitation email. No profile exists until the nominee consents. Tests for I-5 and I-7. | M |
| DR-23 | **WhatsApp-first sharing.** A proper preview image (name, field, "Verified by Pramaan", QR) so a shared link looks good in WhatsApp. "Share on WhatsApp" becomes the main share button on profiles and certificates. | agent | Sharing a profile link in WhatsApp shows the card image and title. | M |
| DR-24 | **Pilot community.** Pick one community you can reach (for example VESIT alumni and faculty). Invite 50, aim for 30 complete profiles in two weeks. | **owner** | 30 real, approved profiles with photos. | owner |
| DR-25 | **Traction page in the console.** Weekly counts only: sign-ups started, finished, approved, certificates checked, links shared, nominations. No personal data. | agent | Page shows the last 8 weeks. Counts match the database in a test. | M |

---

## Phase 5: when there is demand (triggered, not scheduled)

| ID | Task | Trigger |
|---|---|---|
| DR-26 | Approve "Clear cases" automatically by fixed rules (still never the model, I-1), with a daily sample re-checked by a person. Needs the owner's approval and a spec change. | More than 50 cases a week waiting. |
| DR-27 | Bring Hindi screens back. | A native reviewer has signed off `docs/review/hindi-copy-review.md`, or users ask for it. |
| DR-28 | Paid database tier, daily backups, uptime alerts. | Before announcing publicly, or 200+ real members. |

---

## Parked (no new work until someone asks)

Go and Kotlin SDKs, cloud key management (KMS), MCP server, OAuth extensions, Tauri spike, desktop update channels. They work or are scaffolded,
and none of them helps the demo or traction.

---

## Status at the end of 2026-11-19

**Member site (built, tested, committed):** DR-01 (the demo flag now reaches the site; the seeded people were already flagged in the database, the list endpoint just left it
out), DR-04 and DR-05 (keep-warm workflow, ADR 0017; a banner that waits and never covers the logo), DR-06 (photo step in onboarding and on My page), DR-07 (no guessed
pronouns, enforced in code), DR-08 (English only, ADR 0016), DR-09 (proof strip, hidden under 3 real members), DR-10, DR-11 (network fits the connected people), DR-12,
DR-13, DR-14, DR-16, DR-21 (`docs/demo/script.md`), DR-22 (nominations; also closed a gap: the outreach cleaner now strips phone numbers and bare domains), DR-23
(certificate links get a preview card). DR-15 was already true.

**Staff console (on hold at the owner's request, 2026-11-19):** DR-02, DR-17, DR-18, DR-19, DR-20 and DR-25 were built and tested locally, but are NOT committed. They sit in
`git stash` ("admin-side work") and can be brought back with `git stash pop` when the owner wants them.

Owner actions still open (code cannot do these): DR-00a to DR-00d, DR-03, DR-24, and a GitHub repository variable `API_URL` for the keep-warm workflow. Phase 5 stays parked.

---

## Decisions needed from you

1. **DR-04:** pay for an always-on server, or use the free keep-warm ping?
2. **DR-03:** which real profiles stay (yours, Arunima's, Roshan Yadav's)?
3. **DR-11:** keep and fix the network view, or remove it for now?
4. **DR-12:** make web research opt-in (recommended)?
5. **DR-24:** which community to start the pilot with?

## Order

- **Today:** DR-00a to DR-00d.
- **Week 1:** DR-01 to DR-08, then DR-16.
- **Week 2:** DR-09 to DR-15, then DR-17 to DR-20, and DR-21 (the demo is ready at the end of week 2).
- **Weeks 2 to 4:** DR-22 to DR-25, running alongside the pilot.
