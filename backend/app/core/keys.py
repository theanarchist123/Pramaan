from functools import lru_cache

from app.config import get_settings
from app.core.signing import Signer


@lru_cache
def get_signer() -> Signer:
    s = get_settings()
    return Signer.load(seed_b64=s.signing_key_b64, key_path=s.data_dir / "signing.key")
