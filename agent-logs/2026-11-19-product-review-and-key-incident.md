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
