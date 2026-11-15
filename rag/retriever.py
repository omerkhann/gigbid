"""Retriever factory: the deployed RAG design is chosen by config, not hard-coded (assignment R6).

  get_retriever(portfolio_dir, variant="v0_naive", embedder="ollama:nomic-embed-text")

The returned object's `search()` applies metadata filters and returns evidence items. Phase 4
adds more variants (requirement decomposition, hybrid, rerank, corrective loop) behind the same
`search()` signature, so the Portfolio MCP tool never changes.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

# Imported eagerly (it loads numpy): on Windows, importing numpy for the first time from a worker
# thread while a stdio MCP server is blocked reading stdin deadlocks. Load it before serving.
from rag.index.vector import HashEmbedder, OllamaEmbedder
from rag.ingest.loaders import Document, load_portfolio

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = {"v0_naive": "rag.variants.v0_naive:V0Naive"}


@dataclass
class Filters:
    types: list[str] | None = None
    project_id: str | None = None
    since_year: int | None = None
    outcomes: list[str] | None = None

    def allows(self, d: Document) -> bool:
        if self.types and d.type not in self.types:
            return False
        if self.project_id and d.project_id != self.project_id:
            return False
        if self.since_year and (not d.date or int(d.date[:4]) < self.since_year):
            return False
        return not (self.outcomes and d.outcome not in self.outcomes)


def make_embedder(spec: str):
    if spec == "hash":
        return HashEmbedder()
    if spec.startswith("ollama:"):
        return OllamaEmbedder(spec.split(":", 1)[1], os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    raise ValueError(f"Unknown embedder {spec!r}")


class Retriever:
    def __init__(self, portfolio_dir: Path, variant: str, embedder_spec: str, cache_root: Path):
        self.docs = load_portfolio(portfolio_dir)
        self.by_id = {d.doc_id: d for d in self.docs}
        mod, cls = VARIANTS[variant].split(":")
        import importlib

        corpus_key = hashlib.sha1(str(Path(portfolio_dir).resolve()).encode()).hexdigest()[:10]
        cache = cache_root / f"{self.docs[0].persona if self.docs else 'empty'}_{corpus_key}"
        self.impl = getattr(importlib.import_module(mod), cls)(self.docs, make_embedder(embedder_spec), cache)
        self.variant = variant

    def search(self, query: str, k: int = 5, filters: Filters | None = None) -> list[dict]:
        allowed = None
        if filters:
            allowed = {cid for cid, c in self.impl.chunks.items() if filters.allows(c.doc)}
        out = []
        for chunk, score in self.impl.retrieve(query, k, allowed):
            out.append({**chunk.doc.meta(), "evidence_id": chunk.chunk_id, "score": round(score, 4),
                        "text": chunk.text, **({"rating": chunk.doc.extra["rating"]}
                                               if "rating" in chunk.doc.extra else {})})
        return out


_CACHE: dict[tuple, Retriever] = {}


def get_retriever(portfolio_dir: Path, variant: str = "v0_naive", embedder: str = "ollama:nomic-embed-text",
                  cache_root: Path | None = None) -> Retriever:
    key = (str(Path(portfolio_dir).resolve()), variant, embedder)
    if key not in _CACHE:
        _CACHE[key] = Retriever(Path(portfolio_dir), variant, embedder, cache_root or ROOT / "data/processed/rag_cache")
    return _CACHE[key]


def reset_cache() -> None:
    """Forget built indexes (e.g. after the user adds portfolio items)."""
    _CACHE.clear()
