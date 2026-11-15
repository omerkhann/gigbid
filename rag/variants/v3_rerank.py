"""V3 (retrieval group): cross-encoder reranking of the top candidates.

Why: bi-encoders (embeddings) and BM25 score query and document separately; a cross-encoder reads
them together, which is much better at precision in the top few results. It is too slow to run on
the whole corpus, so it only reorders the first `candidates` results. ONNX via fastembed (CPU, no
PyTorch); model from config (default BAAI/bge-reranker-v2-m3-int8, the assignment's shortlist).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=2)
def cross_encoder(model: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(model, cache_dir=os.environ.get("RERANKER_CACHE", str(ROOT / "data/processed/models")))


def rerank(query: str, items: list[tuple[str, str]], model: str) -> list[tuple[str, float]]:
    """items: (chunk_id, text). Returns (chunk_id, score) best first."""
    if not items:
        return []
    # Cost grows with text length on CPU; the opening of a chunk carries most of its signal.
    scores = list(cross_encoder(model).rerank(query, [t[:1200] for _, t in items]))
    return sorted(((cid, float(s)) for (cid, _), s in zip(items, scores, strict=True)), key=lambda x: -x[1])
