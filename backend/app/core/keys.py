import hashlib
from functools import lru_cache

from app.config import get_settings
from app.core.signing import Signer, _b64d


@lru_cache
def get_signer():
    s = get_settings()
    provider = (s.signing_provider or "env").strip().lower()
    if provider in ("aws_kms", "gcp_kms"):
        # The key stays in the provider (I-6). Setting a local seed as well would make it unclear which key signs, so it is refused.
        if s.signing_key_b64:
            raise RuntimeError("SIGNING_PROVIDER uses a KMS key: set SIGNING_KMS_KEY and not both a KMS key and SIGNING_KEY_B64")
        if not s.signing_kms_key:
            raise RuntimeError(f"SIGNING_PROVIDER={provider} needs SIGNING_KMS_KEY")
        from app.core.kms import AwsKmsBackend, GcpKmsBackend, KmsSigner

        return KmsSigner(AwsKmsBackend(s.signing_kms_key) if provider == "aws_kms" else GcpKmsBackend(s.signing_kms_key))
    if provider != "env":
        raise RuntimeError("SIGNING_PROVIDER must be env, aws_kms or gcp_kms")
    if not s.signing_key_b64 and not s.is_local:
        # A lost volume would silently mint a new key and invalidate every certificate ever issued.
        raise RuntimeError("SIGNING_KEY_B64 must be set outside local development")
    return Signer.load(seed_b64=s.signing_key_b64, key_path=s.data_dir / "signing.key")


def compromised() -> dict:
    """kid -> the time from which signatures by that key are no longer trusted. A malformed value is an ERROR: a safety setting must never be silently ignored."""
    from datetime import datetime

    out = {}
    for part in get_settings().signing_compromised_keys.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            kid, ts = part.split("=", 1)
            when = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
            if not kid.strip() or when.tzinfo is None:
                raise ValueError
        except ValueError:
            raise RuntimeError("SIGNING_COMPROMISED_KEYS must look like kid=2026-11-10T00:00:00Z (with a time zone), comma separated") from None
        out[kid.strip()] = when
    return out


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
