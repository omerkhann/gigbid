# 0008 One retrieval pipeline with switchable components

**Context.** Part B compares retrieval variants and ablates the best one component at a time. Separate implementations per variant would make each ablation a rewrite and the comparisons unfair.

**Decision.** `rag/pipeline.py` is one pipeline, and each technique is a switch:
- V1: requirement decomposition;
- V2: hybrid BM25 + dense retrieval, fused with reciprocal rank fusion;
- V3: cross-encoder reranking;
- V4: outcome boosting;
- V8: corrective grading.

A variant is a dict in `rag/retriever.py`; an ablation is a variant with one key removed (`rag_eval --ablate`). The shipped variant is `rag.variant` in `agent/config.yaml`, which the Portfolio server reads.

**Reranker on CPU.** `bge-reranker-v2-m3` (568M parameters) took 70 to 110 s per job on the laptop CPU. The default is therefore `ms-marco-MiniLM-L-12-v2`, at about 4 s per job with 4 ONNX threads; ONNX Runtime's all-cores default was 2.5 times slower. The larger model stays available through the `RERANKER` env var for a GPU host.

**Consequences.** Every variant shares chunking and the embedding cache, so differences come from the component under test. Results and the shipping decision are in the README results table and the R&D report.
