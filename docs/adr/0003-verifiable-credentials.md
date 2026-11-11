# ADR 0003: Verifiable Credentials 2.0, did:web and revocation (TRU-08)

Status: accepted for implementation; interoperability with third-party verifiers is still to be confirmed (see "Not verified").
Date: 2026-11-11. AGENTS.md requires every spec item marked "(verify)" to be checked against the official source first.

## What was checked, and against what (read directly from w3.org on 2026-11-11)

| Item | Official status | Source |
|---|---|---|
| Verifiable Credentials Data Model v2.0 | **W3C Recommendation, 15 May 2025.** Base context `https://www.w3.org/ns/credentials/v2`. Required: `@context`, `type`, `issuer`, `credentialSubject`. `validFrom` / `validUntil` optional. `credentialStatus` is an object (or set) with a required `type`. | https://www.w3.org/TR/vc-data-model-2.0/ |
| Data Integrity EdDSA Cryptosuites v1.0 | **W3C Recommendation, 15 May 2025.** Suite `eddsa-jcs-2022`: JCS (RFC 8785) canonicalisation, SHA-256, Ed25519, proof `type` `DataIntegrityProof`, `proofValue` is multibase base58-btc (`z`), keys are `Multikey`. | https://www.w3.org/TR/vc-di-eddsa/ |
| Bitstring Status List v1.0 | **W3C Recommendation, 15 May 2025.** Entry type `BitstringStatusListEntry` with `statusPurpose`, `statusListIndex` (base-10 string) and `statusListCredential`. List: `encodedList` is multibase base64url (no padding) of the GZIP-compressed bitstring; minimum list size **131,072 entries (16 KB)**; indexes SHOULD be assigned randomly. | https://www.w3.org/TR/vc-bitstring-status-list/ |
| did:web method | **Not a standard.** "A draft of a potential specification. It has no official standing of any kind" (W3C Credentials Community Group). `did:web:host` resolves to `https://host/.well-known/did.json`; with a path to `https://host/path/did.json`; a port is `%3A`-encoded. The document itself warns about DNS spoofing and recommends DNSSEC or secure DNS. | https://w3c-ccg.github.io/did-method-web/ |

The exact signing algorithm was read from the Recommendation text (section 3.3 of vc-di-eddsa). Its published worked example is used as a
conformance test (`backend/tests/test_vc.py`).

- `proofConfig` is the proof options (`type`, `cryptosuite`, `created`, `verificationMethod`, `proofPurpose`) plus `@context` copied from
  the document, with no `proofValue`.
- `hashData = SHA-256(JCS(proofConfig)) || SHA-256(JCS(unsecuredDocument))`. The proof-configuration hash comes FIRST. 64 bytes.
- The signature is Ed25519 over `hashData` directly (it is not hashed again). `proofValue` is `z` + base58-btc(signature).
- A Multikey public key is `z` + base58-btc(`0xed 0x01` followed by the 32-byte key). The Multikey private key header is `0x80 0x26`.

## Decisions

1. **Issue each certificate also as a VC 2.0** secured with an embedded `eddsa-jcs-2022` Data Integrity proof, signed by the registry's
   existing Ed25519 key. The current certificate format stays; the VC is an additional, standard representation of the same facts.
2. **The issuer identity is `did:web:<host>`**, because it needs no registry and reuses the domain people already trust. Because did:web has
   no standing, this is a deliberate and replaceable choice: the verification method is also published in
   `/.well-known/pramaan-keys.json`, so a verifier can pin the key without did:web. Hardening that follows from the spec's own warning:
   HTTPS only with HSTS, and DNSSEC on the registry domain (an operations item, not done here).
3. **Revocation uses a Bitstring Status List** (`statusPurpose: revocation`), one 131,072-entry list, published as a signed
   `BitstringStatusListCredential`. Each certificate gets a unique, randomly assigned index (migration 0013, a human-review path).
4. The status list does not replace the existing `/v1/verify` revocation answer. Both must agree, and a test checks that they do.

## Not verified (do not claim conformance until done)
- Interoperability with an INDEPENDENT third-party verifier (a VC test suite or another vendor's library). The signing code matches the
  Recommendation's published test vector exactly, which is strong evidence but is not an interop test.
- A hosted JSON-LD context for Pramaan-specific terms. The credentials declare them with an inline `@vocab`
  (`https://pramaan.example/ns/v1#`), a placeholder namespace that does not resolve yet. `eddsa-jcs-2022` does not need JSON-LD
  processing, so signing and verification are unaffected, but a JSON-LD processor will treat the terms as belonging to that namespace.
  A real, hosted vocabulary URL has to replace the placeholder before external adoption.
- That did:web resolves identically behind the production CDN (needs a deployed check).
