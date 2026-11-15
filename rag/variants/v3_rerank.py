"""V3 (retrieval group): cross-encoder reranking of the top candidates.

Why: bi-encoders (embeddings) and BM25 score query and document separately; a cross-encoder reads
them together, which is much better at precision in the top few results. It is too slow to run on
the whole corpus, so it only reorders the first `candidates` results. ONNX via fastembed (CPU, no
PyTorch). Default model ms-marco-MiniLM-L-12-v2: bge-reranker-v2-m3 (568M params, on the
assignment's shortlist) measured 70-110 s per job on this laptop's CPU against about 8 s for
MiniLM, so it stays an option (RERANKER env var) for a GPU host rather than the default.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUERY_CHARS, DOC_CHARS = 400, 600


@lru_cache(maxsize=2)
def cross_encoder(model: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    # ONNX Runtime's default (all cores) oversubscribes on a 6-core laptop; 4 threads measured fastest.
    return TextCrossEncoder(model, cache_dir=os.environ.get("RERANKER_CACHE", str(ROOT / "data/processed/models")),
                            threads=int(os.environ.get("RERANKER_THREADS", "4")))


def rerank(query: str, items: list[tuple[str, str]], model: str) -> list[tuple[str, float]]:
    """items: (chunk_id, text). Returns (chunk_id, score) best first."""
    if not items:
        return []
    # Cost grows with pair length on CPU (and pairs cap at 512 tokens anyway): a job query opens with
    # title and skills, and a chunk's opening carries most of its signal.
    scores = list(cross_encoder(model).rerank(query[:QUERY_CHARS], [t[:DOC_CHARS] for _, t in items]))
    return sorted(((cid, float(s)) for (cid, _), s in zip(items, scores, strict=True)), key=lambda x: -x[1])
