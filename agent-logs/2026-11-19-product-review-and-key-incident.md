# 2026-11-19: product review and the signing-key incident

## Incident: 41 of 42 live certificates failed verification
- Found while reviewing the live site: /verify/PRM-M24PSTAEEA showed "Does not match its signature. It may have been edited."
- Every live certificate was checked against /v1/verify. 41 were signed with key `407e647871b4520b`, 1 (issued 2026-11-19 09:13Z) with `d83ef535dbf91560`. The server
  publishes only `d83e...`. The production SIGNING_KEY_B64 was changed on 2026-11-19, probably while environment variables were edited for email, and the old public key was
  never added to SIGNING_RETIRED_PUBLIC_KEYS.
- The original seed (kid `407e...`) is still in the repo-root `.env` (checked by computing the key id only; the seed was not printed).
- Owner action (needs the human; Render env): set SIGNING_KEY_B64 back to the value in `.env`, and set SIGNING_RETIRED_PUBLIC_KEYS=RoGxA0OJoZhjntR7nM7U8xHGaBK6fI2CCxWuoMe_qpU
  so PRM-5D84XWWKWX (signed today with the new key) keeps verifying.

## Code changes
- certificates.py: an unknown signing key now gives its own reason ("Signed with a key this registry no longer publishes...") instead of claiming the content changed;
  `unknown_signing_keys()` counts unrevoked certificates signed by keys the server cannot check.
- main.py: start-up logs an ERROR per unknown key with the count and the fix.
- web: new verdict "unconfirmed" ("Cannot be confirmed right now", caution tone) for that reason.
- web: the home trust strip and the verify banner no longer squeeze their text into a one-word column on phones (flex: 1 1 16rem).
- Tests: test_key_rotation.py (reason wording; unknown key counting).

## Review
Brutally honest product review delivered in chat (member site + staff console, against the blueprint and the Wildcatter deck).

## Demo-readiness plan, member side built the same day (docs/plans/2026-11-19-demo-readiness.md)
Owner asked for everything in one day, then said: do not implement or fix anything for the admin console, finish the member side only.
- Committed: member-site tasks (see the plan's status section). Tests added: test_directory (is_demo in list, proof counts), test_bio_pronouns, test_nominations
  (I-5, I-7), test_sanitize (I-7: phone numbers and bare domains), test_key_rotation (start-up check, unknown key).
- Found: `doot.sanitize` removed links and emails but not phone numbers or bare domains although `invite_message` promised it did; fixed.
- Found and fixed: the start-up key check I added earlier used an undefined logger and would have crashed the server at boot exactly when a key was missing.
- Found: my earlier claim "no live profile has is_demo set" was wrong. The database flag was set; `ProfileSummary` just did not return it.
- Test change, with reason: `apps/web/scripts/smoke-directory.mjs` now clicks the person's link instead of the first text with her name, because the new "Searching for ..." line
  also contains the name. The product behaviour was right; the locator was ambiguous.
- Left uncommitted, in `git stash`: all admin-console work (Registry page, document viewer, confidence and clear cases, nav, Settings, Traction) and its backend
  (`review.py`, `admin.py`, `review_triage.py` and their tests). Those touch always-human-review paths, so they need review before they are used.
- No migration was added (nominations reuse the outbox). `packages/sdk` and the Postman collection were regenerated from the member-side backend only.
