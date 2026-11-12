"""Regenerates test/fixtures/merkle.json from the BACKEND's own implementation, so the JS verifier is tested against Python vectors.
Run from backend/:  .venv/Scripts/python ../packages/verify-js/test/make-fixtures.py"""
import base64
import hashlib
import json
import pathlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from app.core import merkle

out = pathlib.Path(__file__).parent / "fixtures" / "merkle.json"
leaves = [merkle.leaf_hash(f"entry-{i}".encode()) for i in range(12)]
vec = {"leaves": [l.hex() for l in leaves], "trees": {}}
for n in range(1, 13):
    sub = leaves[:n]
    vec["trees"][str(n)] = {
        "root": merkle.root(sub).hex(),
        "inclusion": [[p.hex() for p in merkle.inclusion_proof(sub, i)] for i in range(n)],
        "consistency": {str(m): [p.hex() for p in merkle.consistency_proof(sub, m)] for m in range(1, n + 1)},
    }
# a signed checkpoint from a throwaway key (the format the registry signs: see backend/app/api/verify.py::checkpoint_text)
key = Ed25519PrivateKey.generate()
raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
pub = base64.urlsafe_b64encode(raw).decode().rstrip("=")
kid = hashlib.sha256(raw).hexdigest()[:16]
text = f"pramaan-log-checkpoint-v1\nsize=12\nroot={vec['trees']['12']['root']}\n"
sig = base64.urlsafe_b64encode(key.sign(hashlib.sha256(text.encode()).digest())).decode().rstrip("=")
vec["checkpoint"] = {"size": 12, "root": vec["trees"]["12"]["root"], "text": text, "key_id": kid, "signature": sig, "keys": {kid: pub}}
out.write_text(json.dumps(vec, indent=1))
print("wrote", out)
