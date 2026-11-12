# Signing-key rotation runbook (TRU-11)

This is a human-review path (`docs/security/`). It is backed by `backend/tests/test_key_rotation.py`, which performs exactly this rotation against the real code and passes.

## What a rotation does and does not do
- Certificates and credentials are signed with an Ed25519 key. Each one records the **key id** (`kid` = first 16 hex of SHA-256 of the public key).
- Verification looks the `kid` up in the **public keyring**: the current key plus every key listed in `SIGNING_RETIRED_PUBLIC_KEYS`.
- So after a rotation, **old certificates stay valid only while the old PUBLIC key stays in the keyring.** Dropping it makes every certificate it signed unverifiable (proved by `test_forgetting_the_old_public_key_is_what_breaks_old_certificates`).
- Rotation is routine (hygiene, staff change, a suspected exposure of a *copy* of the key). It is **not** the answer to a confirmed compromise: see "If the key is compromised".

## Routine rotation
1. **Announce and freeze.** Pick a quiet window. Pause issuing (no certificate or credential requests in flight).
2. **Record the old public key.** `GET /.well-known/pramaan-keys.json` and save the current `kid` and public key `x` somewhere other than the server.
3. **Generate the new key** somewhere that is not the web server (a workstation or, later, a KMS/HSM). Keep the 32-byte seed secret; it must never be pasted into a ticket, chat or log (invariant I-6). Derive and record its public key and `kid`.
4. **Set the environment** on the API host:
   - `SIGNING_KEY_B64` = the NEW seed (base64url, no padding).
   - `SIGNING_RETIRED_PUBLIC_KEYS` = the old public key, appended to any existing comma-separated list. **Public keys only.**
5. **Restart the API.** (The signer is cached for the life of the process.)
6. **Verify immediately** (this is the dry run's assertions, done for real):
   - `GET /.well-known/pramaan-keys.json` lists the old `kid` and the new `kid`.
   - `GET /.well-known/did.json` lists both as verification methods.
   - `GET /v1/verify/<an old certificate code>` is `valid: true` with the OLD `key_id`.
   - Issue a test certificate: `GET /v1/verify/<new code>` is `valid: true` with the NEW `key_id`.
   - `GET /v1/transparency/checkpoint` is signed by the new key and verifies against the published key.
7. **Tell verifiers.** Desktop and `@pramaan/verify` users who pin keys must be given the new public key before the old one is retired from their pins.
8. **Keep the retired public key forever** (or for as long as any certificate it signed can still be presented). There is no expiry for this.
9. Write the rotation into the audit record: who, when, old and new `kid`, the verification evidence from step 6.

## Rollback
If step 6 fails: restore the previous `SIGNING_KEY_B64` and the previous `SIGNING_RETIRED_PUBLIC_KEYS`, restart, re-run step 6. Nothing is lost because no certificate is re-signed during a rotation.

## If the key is compromised (read this before you need it)
A leaked private key means anyone can mint signatures that verify. The defence that survives a key leak is the transparency log: a thief holding only the key cannot write into the log.
1. Stop issuing. Rotate as above so new certificates use a clean key.
2. **Mark the old key.** Set `SIGNING_COMPROMISED_KEYS=<old kid>=<UTC time from which you no longer trust it>` (for example `a1b2c3d4e5f60708=2026-11-10T14:00:00Z`, always with a time zone) and restart.
   - Certificates by that key that were logged BEFORE that time keep verifying; anything logged at or after it verifies as invalid ("do not rely on it"), and a certificate with no log entry never verifies.
   - The key can no longer issue anything. A malformed value stops the app from starting (a safety setting is never silently ignored).
   - `/.well-known/pramaan-keys.json` publishes `compromised_since` for that key, so outside verifiers can apply the same rule together with the log.
3. Pick the time carefully: too late trusts forgeries made in the gap; too early invalidates honest certificates (revoke and re-issue those from the affected list).
4. Revoke and re-issue the affected certificates; publish the incident.
Not built: a re-signing batch job (re-issuing is manual).

## KMS / HSM
`backend/app/core/kms.py` holds the private key in AWS KMS or Google Cloud KMS; the key never enters this process. Set `SIGNING_PROVIDER=aws_kms` (or `gcp_kms`) and `SIGNING_KMS_KEY` (AWS key id/ARN, or the full Google key VERSION name), and leave `SIGNING_KEY_B64` empty (setting both is refused).
- Facts checked in the providers' documentation on 2026-11-12: AWS KMS key spec `ECC_NIST_EDWARDS25519` with algorithm `ED25519_SHA_512` and message type RAW (pure Ed25519, 0-4096 bytes); Google Cloud KMS `EC_SIGN_ED25519` (PureEdDSA). Both verify with every existing verifier. Do NOT use AWS `ED25519_PH_SHA_512`: it is Ed25519ph and does not verify as Ed25519.
- The signer checks every signature against the key's own public key before using it and refuses to start if its self-test fails; an outage is an error, never a fallback to another key.
- **Moving to KMS is a rotation**: the KMS key has a new key id. Follow the routine rotation steps with the KMS public key as the "new" key, and add the old public key to `SIGNING_RETIRED_PUBLIC_KEYS`.
- **Tested here only with a fake provider.** The real AWS and Google adapters have not been run (no cloud account here): first do a staging run and `python scripts/verify_rotation.py`.

## Dry run in staging
Run `pytest backend/tests/test_key_rotation.py` (needs the local database) before any production rotation, then perform steps 1 to 9 in staging with a copy of production data and record the evidence. **No staging rotation has been done: only the automated tests.** After a real rotation run `python scripts/verify_rotation.py --api <url> --old-code <code> --old-kid <kid> [--new-code <code>]`: it performs the step 6 checks against the live API and exits non-zero if any fails.
