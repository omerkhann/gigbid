"""V0 (mandatory baseline): fixed chunks, dense top-k cosine on the whole query.

This is "the number everything else must beat". No query rewriting, no hybrid search, no
reranking, no use of outcomes - deliberately naive.
"""

from __future__ import annotations

from rag.index.vector import VectorIndex
from rag.ingest.chunking import Chunk, chunk_all
from rag.ingest.loaders import Document


class V0Naive:
    name = "v0_naive"

    def __init__(self, docs: list[Document], embedder, cache_dir=None, chunk_size: int = 900, overlap: int = 150):
        self.chunks: dict[str, Chunk] = {c.chunk_id: c for c in chunk_all(docs, chunk_size, overlap)}
        self.index = VectorIndex(embedder, cache_dir).build(list(self.chunks), [c.text for c in self.chunks.values()])

    def retrieve(self, query: str, k: int = 5, allowed: set[str] | None = None) -> list[tuple[Chunk, float]]:
        return [(self.chunks[cid], score) for cid, score in self.index.search(query, k, allowed)]


def retrieve(query: str, index: V0Naive, k: int = 5):
    """Starter-kit signature, kept for compatibility."""
    return index.retrieve(query, k)
