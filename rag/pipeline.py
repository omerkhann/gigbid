"""A retrieval pipeline assembled from switchable components, so every variant (and every ablation)
is a configuration, not a separate implementation:

  decompose  V1  one retrieval per requirement, fused with RRF            (rag/variants/v1_decompose.py)
  hybrid     V2  BM25 + dense, fused with RRF                             (rag/variants/v2_hybrid.py)
  rerank     V3  cross-encoder reorders the top candidates                (rag/variants/v3_rerank.py)
  outcome    V4  boost evidence from proposals that won or got replies    (rag/variants/v4_outcome.py)
  corrective V8  grade evidence, re-query once, refuse when none relevant (rag/variants/v8_corrective.py)

With every switch off this is exactly V0: fixed chunks, dense cosine top-k on the whole query.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rag.index.vector import VectorIndex
from rag.ingest.chunking import Chunk, chunk_all
from rag.ingest.loaders import Document
from rag.variants.v1_decompose import requirements
from rag.variants.v2_hybrid import RRF_K, BM25Index, rrf
from rag.variants.v3_rerank import rerank as cross_rerank
from rag.variants.v4_outcome import outcome_factor
from rag.variants.v8_corrective import grade, rewrite

POOL = 30          # candidates passed between stages (hybrid fusion)
RERANK_POOL = 20   # candidates the cross-encoder reorders (CPU cost is per candidate)
MIN_RELEVANT = 1   # corrective: re-query when fewer evidence items than this pass the grader


def job_query(job: dict) -> str:
    return f"{job['title']}\n{', '.join(job.get('required_skills') or [])}\n{job.get('description', '')}"[:4000]


class Pipeline:
    def __init__(self, docs: list[Document], embedder, cache_dir: Path | None, *, name: str = "custom",
                 decompose: bool = False, hybrid: bool = False, rerank: str | None = None, outcome: bool = False,
                 corrective: Callable | None = None, chunk_size: int = 900, overlap: int = 150):
        self.name = name
        self.chunks: dict[str, Chunk] = {c.chunk_id: c for c in chunk_all(docs, chunk_size, overlap)}
        ids, texts = list(self.chunks), [c.text for c in self.chunks.values()]
        self.dense = VectorIndex(embedder, cache_dir).build(ids, texts)
        self.bm25 = BM25Index(ids, texts) if hybrid else None
        self.decompose, self.rerank_model, self.outcome, self.ask = decompose, rerank, outcome, corrective
        self.trace: list[dict] = []   # corrective decisions, for evaluation and debugging

    # --- one query -------------------------------------------------------------------------------

    def _rank(self, query: str, k: int, allowed: set[str] | None) -> list[tuple[str, float]]:
        deep = self.bm25 is not None or self.rerank_model or self.outcome
        ranking = self.dense.search(query, POOL if deep else k, allowed)
        if self.bm25 is not None:
            ranking = rrf([ranking, self.bm25.search(query, POOL, allowed)], POOL)
        if self.rerank_model:
            ranking = cross_rerank(query, [(cid, self.chunks[cid].text) for cid, _ in ranking[:RERANK_POOL]],
                                   self.rerank_model)
        if self.outcome:
            # Reranker scores are logits (can be negative), so boost a rank-based score instead.
            ranking = sorted(((cid, outcome_factor(self.chunks[cid].doc.outcome) / (RRF_K + r))
                              for r, (cid, _) in enumerate(ranking, start=1)), key=lambda x: -x[1])
        return ranking[:k]

    def retrieve(self, query: str, k: int = 5, allowed: set[str] | None = None) -> list[tuple[Chunk, float]]:
        ranking = self._rank(query, k, allowed)
        if self.ask is not None:
            items = [(cid, self.chunks[cid].text) for cid, _ in ranking]
            relevant = grade(self.ask, query, items) if items else set()
            step = {"query": query, "candidates": len(items), "relevant": len(relevant), "requeried": False}
            if len(relevant) < MIN_RELEVANT:
                better = rewrite(self.ask, query)
                ranking = self._rank(better, k, allowed)
                items = [(cid, self.chunks[cid].text) for cid, _ in ranking]
                relevant = grade(self.ask, query, items) if items else set()
                step.update(requeried=True, rewritten=better, relevant=len(relevant))
            self.trace.append(step)
            ranking = [(cid, s) for cid, s in ranking if cid in relevant]   # may be empty: refuse to claim
        return [(self.chunks[cid], score) for cid, score in ranking]

    # --- a whole job -----------------------------------------------------------------------------

    def retrieve_job(self, job: dict, k: int = 10) -> list[tuple[Chunk, float]]:
        if not self.decompose:
            return self.retrieve(job_query(job), k)
        per_req = [[(c.chunk_id, s) for c, s in self.retrieve(req, k)] for req in requirements(job)]
        return [(self.chunks[cid], s) for cid, s in rrf(per_req, k)]
