"""Text embeddings for semantic search (384-dim, multilingual).

* fastembed: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (runs locally, no key,
  understands Hindi/Marathi/Tamil… so "सौर ऊर्जा" finds clean-energy people).
* hash: deterministic feature-hashing fallback (words + char trigrams). Lexical, not semantic —
  used for tests and when the model can't be loaded, and it says so in /healthz.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
from functools import lru_cache

from app.config import get_settings

log = logging.getLogger("pramaan.embeddings")
DIM = 384
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _normalize(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / n for x in vec]


def hash_embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    tokens = re.findall(r"\w+", text.lower())
    feats = list(tokens) + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    feats += [w[i : i + 3] for w in tokens if len(w) > 3 for i in range(len(w) - 2)]
    for f in feats:
        h = int(hashlib.md5(f.encode()).hexdigest(), 16)
        vec[h % DIM] += 1.0 if (h >> 100) & 1 else -1.0
    return _normalize(vec)


class Embedder:
    def __init__(self) -> None:
        self.kind = "hash"
        self._model = None
        pref = get_settings().embeddings.lower()
        if pref in ("auto", "fastembed"):
            try:
                from fastembed import TextEmbedding

                self._model = TextEmbedding(MODEL)
                self.kind = "fastembed"
            except Exception as exc:  # noqa: BLE001
                log.warning("fastembed unavailable (%s); using the lexical hash fallback", exc)

    def embed_sync(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            return [hash_embed(t) for t in texts]
        return [_normalize([float(x) for x in v]) for v in self._model.embed(texts)]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # The model is CPU-bound; keep the event loop free.
        return await asyncio.to_thread(self.embed_sync, texts)


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()
