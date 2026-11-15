"""V2 (retrieval group): hybrid BM25 + dense, merged with reciprocal rank fusion.

Why: embeddings blur exact names ("Celery", "dbt", "Pinecone", "GA4"); BM25 matches them exactly.
RRF combines the two rankings without having to calibrate their scores against each other.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")
RRF_K = 60   # standard constant from Cormack et al. (2009)


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, ids: list[str], texts: list[str]):
        self.ids = ids
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])

    def search(self, query: str, k: int, allowed: set[str] | None = None) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(self.ids)), key=lambda i: -scores[i])
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            if allowed is None or self.ids[i] in allowed:
                out.append((self.ids[i], float(scores[i])))
                if len(out) == k:
                    break
        return out


def rrf(rankings: list[list[tuple[str, float]]], k: int, rrf_k: int = RRF_K) -> list[tuple[str, float]]:
    """Reciprocal rank fusion: score(d) = sum over rankings of 1 / (rrf_k + rank)."""
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (cid, _) in enumerate(ranking, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(fused.items(), key=lambda kv: -kv[1])[:k]
