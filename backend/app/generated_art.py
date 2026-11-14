"""The approved, frozen generated-art library: a small JSON manifest read at certificate time.

Kept free of heavy imports so `app.domain` can use it. The assets themselves are JPEG files in `apps/web/public/certificate-photos/` (the same place and the
same signed path as the stock photos); this manifest says which of them are generated, which sector each belongs to, and each file's SHA-256.
Nothing here ever calls an image model: generation happens offline, once, through `scripts/cert_art.py`, and a person approves each image.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ART_MANIFEST_PATH = Path(__file__).resolve().parent / "generated_art.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    try:
        return dict(json.loads(ART_MANIFEST_PATH.read_text(encoding="utf-8")).get("assets", {}))
    except (OSError, ValueError):
        return {}  # no library yet (or an unreadable one): certificates fall back to the stock photos


def clear_cache() -> None:
    _load.cache_clear()


def approved() -> dict[str, dict]:
    """id -> {sector, sha256, prompt, seed, model, licence, ...} for every APPROVED asset."""
    return _load()


def ids_for_sector(sector: str) -> list[str]:
    return sorted(i for i, meta in _load().items() if meta.get("sector") == sector)


def sha_map() -> dict[str, str]:
    return {i: meta.get("sha256", "") for i, meta in _load().items()}
