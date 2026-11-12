# Changelog

Notable changes to the public API and behaviour, newest first. This is written for people who build on Pramaan; internal work is in `agent-logs/`.

## Unreleased

### Added
- `POST /v1/verify/batch`: check up to 50 certificate codes in one call. Each answer is exactly what `GET /v1/verify/{code}` says.
- `GET /v1/certificates/{code}/vc`, `GET /.well-known/did.json`, `GET /v1/status/revocation/1`: certificates as W3C Verifiable Credentials 2.0
  (`eddsa-jcs-2022`), the registry's `did:web` document, and a signed revocation list. See `docs/adr/0003-verifiable-credentials.md`
  (did:web is a community draft, not a standard; interoperability with third-party verifiers is not yet verified).
- `GET /v1/transparency/checkpoint`, `/v1/transparency/proof/{code}`, `/v1/transparency/consistency`: a signed Merkle view of the public log (RFC 9162).
- `GET /v1/agents/replay`: a recorded real verification run on a fictional demo profile, for the public Agent Floor.
- `<pramaan-verify>` web component and the `@pramaan/verify` package: verify a certificate in the visitor's own browser.
- Certificates may now carry the claim status `issuer` (only with a complete issuer evidence record; nothing can create one yet).
- Graph links of type `collab`: a stated working connection, whose `why` is the person's own words.
- Every email carries a system-made unsubscribe link (`GET /v1/outreach/unsubscribe`).

### Changed
- A profile can now be `suspended` (hidden from every public listing until restored). Clients that switch on `status` should handle it.
- Staff sign-in requires an authenticator or recovery code once an authenticator is enrolled.
- The public site's count of "confirmed" claims counts only document, issuer and reviewer confirmations; public-source claims are shown separately.

### Notes
- Deprecations: none.
