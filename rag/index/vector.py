"""Embedders and an in-memory cosine index with an on-disk embedding cache.

Embedders:
  OllamaEmbedder - open models served by Ollama (nomic-embed-text, bge-m3); runs on GPU locally
                   and on CPU in deployment (assignment: embeddings are open models in both profiles).
  HashEmbedder   - deterministic bag-of-words hashing; no model needed. Only for CI and unit tests.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import ClassVar

import httpx
import numpy as np


class OllamaEmbedder:
    # nomic-embed-text was trained with task prefixes; other models get none.
    PREFIXES: ClassVar[dict[str, tuple[str, str]]] = {"nomic-embed-text": ("search_document: ", "search_query: ")}

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434", batch: int = 32):
        self.model, self.base_url, self.batch = model, base_url.rstrip("/"), batch
        self.name = f"ollama:{model}"
        self.doc_prefix, self.query_prefix = self.PREFIXES.get(model.split(":")[0], ("", ""))

    def _embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), self.batch):
            r = httpx.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts[i:i + self.batch]},
                           timeout=300)
            r.raise_for_status()
            out.extend(r.json()["embeddings"])
        return np.asarray(out, dtype=np.float32)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]


class HashEmbedder:
    """Hashing-trick bag of words. Deterministic and dependency-free; crude, so tests only."""

    name = "hash"

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _one(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.dim] += 1.0
        return v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._one(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._one(text)


def _normalise(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    return m / np.where(n == 0, 1, n)


class VectorIndex:
    """Cosine top-k over chunk embeddings. Embeddings are cached on disk by (embedder, text) hash,
    so re-indexing an unchanged corpus is instant and adding one item embeds only that item."""

    def __init__(self, embedder, cache_dir: Path | None = None):
        self.embedder, self.cache_dir = embedder, cache_dir
        self.ids: list[str] = []
        self.matrix = np.zeros((0, 1), np.float32)

    def _cache_file(self) -> Path | None:
        if not self.cache_dir:
            return None
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.embedder.name)
        return self.cache_dir / f"emb_{safe}.npz"

    def build(self, ids: list[str], texts: list[str]) -> VectorIndex:
        keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        cached: dict[str, np.ndarray] = {}
        cf = self._cache_file()
        if cf and cf.exists():
            data = np.load(cf)
            cached = dict(zip(data["keys"].tolist(), data["vecs"], strict=True))
        missing = [i for i, k in enumerate(keys) if k not in cached]
        if missing:
            vecs = self.embedder.embed_documents([texts[i] for i in missing])
            for i, v in zip(missing, vecs, strict=True):
                cached[keys[i]] = v
            if cf:
                cf.parent.mkdir(parents=True, exist_ok=True)
                np.savez(cf, keys=np.array(list(cached)), vecs=np.stack(list(cached.values())))
        self.ids = ids
        self.matrix = _normalise(np.stack([cached[k] for k in keys])) if keys else self.matrix
        return self

    def search(self, query: str, k: int, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        q = _normalise(self.embedder.embed_query(query)[None, :])[0]
        scores = self.matrix @ q
        order = np.argsort(-scores)
        out = []
        for i in order:
            if allowed is None or self.ids[i] in allowed:
                out.append((self.ids[i], float(scores[i])))
                if len(out) == k:
                    break
        return out
