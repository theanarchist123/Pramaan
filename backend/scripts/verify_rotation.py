"""Step 6 of docs/security/key-rotation.md, as a command. Run it against staging (or production) right after a signing-key rotation.

    python scripts/verify_rotation.py --api https://api.example.org --old-code PRM-OLDCODE --old-kid <kid before> [--new-code PRM-NEWCODE]

It prints each check and exits 1 if any fails. It only READS the public API (no key, no write). The checks:
  1. the published keys list the OLD kid and a different current kid, and none is marked compromised unless you expect it;
  2. the did:web document lists both keys;
  3. an OLD certificate still verifies, under its OLD key id;
  4. (if --new-code) a NEW certificate verifies under a key id that is not the old one;
  5. the transparency checkpoint is signed by a key the registry publishes, and the signature verifies.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def _b64d(t: str) -> bytes:
    return base64.urlsafe_b64decode(t + "=" * (-len(t) % 4))


def run_checks(get, old_code: str, old_kid: str, new_code: str = "") -> list[tuple[str, bool, str]]:
    """`get(path) -> dict`. Returns [(check, ok, detail)]. Pure apart from `get`, so it is tested with a fake."""
    out: list[tuple[str, bool, str]] = []
    keys = {k["kid"]: k for k in get("/.well-known/pramaan-keys.json")["keys"]}
    out.append(("old key is still published", old_kid in keys, old_kid))
    current = [k for k in keys if k != old_kid]
    out.append(("a different, current key is published", bool(current), ", ".join(current)))
    out.append(("no published key is marked compromised", not any("compromised_since" in k for k in keys.values()), ""))
    try:
        did = get("/.well-known/did.json")
        methods = {m.get("id", "").rsplit("#", 1)[-1] for m in did.get("verificationMethod", [])}
        out.append(("did:web lists both keys", old_kid in methods and bool(set(current) & methods), ", ".join(sorted(methods))))
    except Exception as exc:  # noqa: BLE001
        out.append(("did:web lists both keys", False, f"could not read did.json: {type(exc).__name__}"))
    old = get(f"/v1/verify/{old_code}")
    out.append(("old certificate still verifies", old.get("valid") is True, old.get("reason", "")))
    out.append(("old certificate is under its old key id", old.get("key_id") == old_kid, str(old.get("key_id"))))
    if new_code:
        new = get(f"/v1/verify/{new_code}")
        out.append(("new certificate verifies", new.get("valid") is True, new.get("reason", "")))
        out.append(("new certificate uses a new key id", new.get("key_id") not in (None, old_kid), str(new.get("key_id"))))
    cp = get("/v1/transparency/checkpoint")
    pub = keys.get(cp.get("key_id"))
    ok = False
    if pub:
        try:
            Ed25519PublicKey.from_public_bytes(_b64d(pub["x"])).verify(_b64d(cp["signature"]), hashlib.sha256(cp["text"].encode()).digest())
            ok = True
        except (InvalidSignature, ValueError, KeyError):
            ok = False
    out.append(("checkpoint is signed by a published key and verifies", ok, str(cp.get("key_id"))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--old-code", required=True)
    ap.add_argument("--old-kid", required=True)
    ap.add_argument("--new-code", default="")
    a = ap.parse_args()
    base = a.api.rstrip("/")

    def get(path: str) -> dict:
        with urllib.request.urlopen(base + path, timeout=20) as r:  # noqa: S310 - the operator supplies the URL
            return json.loads(r.read())

    results = run_checks(get, a.old_code.strip().upper(), a.old_kid.strip(), a.new_code.strip().upper())
    for name, ok, detail in results:
        print(f"[{'ok' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
