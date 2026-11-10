"""Print fresh production secrets:  python backend/scripts/gen_secrets.py

Keep SIGNING_KEY_B64 safe and backed up: it signs every certificate. Losing it, or changing it without
listing the old public key in SIGNING_RETIRED_PUBLIC_KEYS, makes every certificate issued so far fail to verify.
"""

import base64
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()
seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")  # noqa: E731

print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
print(f"SIGNING_KEY_B64={b64(seed)}")
print(f"# public key (for SIGNING_RETIRED_PUBLIC_KEYS when you later rotate away from this one): {b64(pub)}")
