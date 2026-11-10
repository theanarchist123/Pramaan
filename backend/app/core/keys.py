import hashlib
from functools import lru_cache

from app.config import get_settings
from app.core.signing import Signer, _b64d


@lru_cache
def get_signer() -> Signer:
    s = get_settings()
    if not s.signing_key_b64 and not s.is_local:
        # A lost volume would silently mint a new key and invalidate every certificate ever issued.
        raise RuntimeError("SIGNING_KEY_B64 must be set outside local development")
    return Signer.load(seed_b64=s.signing_key_b64, key_path=s.data_dir / "signing.key")


def key_id_for(public_key_b64: str) -> str:
    return hashlib.sha256(_b64d(public_key_b64)).hexdigest()[:16]


def public_keyring() -> dict[str, str]:
    """kid -> public key (b64): the current key plus retired ones (SIGNING_RETIRED_PUBLIC_KEYS)."""
    ring = {}
    for pub in get_settings().signing_retired_public_keys.split(","):
        if pub.strip():
            ring[key_id_for(pub.strip())] = pub.strip()
    signer = get_signer()
    ring[signer.key_id] = signer.public_key_b64
    return ring
