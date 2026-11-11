# Pattern note: Transparency (PG-13)  -  SPEC-DERIVED

- The chain is **re-computed in the browser** (WebCrypto SHA-256, same rule as `core/signing.py::chain_hash`), not taken from the server's
  verdict. The old server-side `/v1/transparency/verify` banner is no longer used by this page.
- "Alter an entry (demo)" changes one fingerprint in memory only; the first mismatch and every entry after it are flagged
  (icon + text + border), showing why rewriting history is visible.
- Covers up to 500 newest entries. If the window does not start at the genesis value the banner does not claim "from the first entry".
- **Not done:** signed checkpoints / Merkle proofs (TRU-09), virtualised tape for very long logs, animated link-draw between entries.
