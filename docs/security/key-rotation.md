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
A leaked private key means anyone can mint certificates that verify. The current system has **no way to mark a key as untrusted**: the keyring only lists keys, it does not distinguish "retired" from "compromised". **That is a known gap, not a solved problem.** Until it is built:
1. Stop issuing. Rotate as above so new certificates use a clean key.
2. Treat every certificate signed by the compromised key as suspect. The transparency log records every legitimate issuance with its digest, so a forged certificate can be recognised as *absent from the log* (the log is the check that survives a key leak). Verify certificates against the log, not only the signature.
3. Revoke and re-issue the affected certificates; publish the incident.
4. **To build (needs a decision):** a `compromised_since` marker per retired key so verification can refuse signatures made after a given time by that key, and a re-signing batch job.

## KMS / HSM (not built)
The `Signer` object is the only place a private key is used (`sign_digest`, `sign_raw`, `public_key_b64`, `key_id`). A KMS-backed signer would implement the same four members and never expose the key. **Not built**, because it needs a cloud account and a choice of provider, and because Ed25519 support differs by provider and version **(verify against the provider's current documentation before choosing)**. Until then the seed lives in the host's environment: protect it as such (secrets manager, no logs, restricted access).

## Dry run in staging
Run `pytest backend/tests/test_key_rotation.py` (needs the local database) before any production rotation, then perform steps 1 to 9 in staging with a copy of production data and record the evidence. **This session has not done a staging rotation: only the automated test.**
