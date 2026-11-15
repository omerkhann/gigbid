# Results

### Headline (assignment B5)

Sources: `evals/results/rag_eval.json` (retrieval), `evals/results/gigsim_outcomes_<variant>.json` (proposals sent to GigSim).

| Variant | Evidence Recall@5 | nDCG@10 | Unsupported claims / proposal (before → after verify) | Judge score (1-5) | GigSim reply rate | p95 latency to approval (s) | Cost / proposal (USD) |
|---|---|---|---|---|---|---|---|
| V0 | 0.497 | 0.581 | 2.50 → 0 | 2 | 0.000 | 386.4 | 0.00 |
| Shipped (v2_v4) | 0.541 | 0.628 | – → – | – | – | – | – |

### Retrieval variants and ablation

Source: `evals/results/rag_eval.json` (embedder `ollama:nomic-embed-text`; macro-average over the three personas; `a-b` = variant a with component b removed).

| Variant | Jobs | Recall@5 | Δ R@5 vs V0, pts [paired 95% CI] | MRR | nDCG@10 | R@5, 5+ requirements | p95 latency (s) | Refusal rate on skip jobs |
|---|---|---|---|---|---|---|---|---|
| `v1_decompose` | 60 | 0.470 | -2.7 | 0.658 | 0.544 | 0.406 | 0.546 | – |
| `v1_v2_v3` | 60 | 0.490 | -0.7 | 0.711 | 0.544 | 0.432 | 27.915 | – |
| `v1_v2_v3-decompose` | 60 | 0.479 | -1.8 | 0.722 | 0.552 | 0.443 | 3.988 | – |
| `v1_v2_v3-hybrid` | 60 | 0.469 | -2.8 | 0.716 | 0.557 | 0.405 | 11.882 | – |
| `v1_v2_v3-rerank` | 60 | 0.477 | -2.0 | 0.690 | 0.558 | 0.411 | 0.604 | – |
| `v0_naive` | 60 | 0.497 | +0.0 | 0.778 | 0.581 | 0.458 | 0.199 | – |
| `v2_hybrid` | 60 | 0.492 | -0.5 [-6.2, +5.2] | 0.795 | 0.583 | 0.468 | 0.173 | – |
| `v3_rerank` | 60 | 0.479 | -1.8 [-7.4, +3.5] | 0.722 | 0.552 | 0.443 | 7.546 | – |
| `v4_outcome` | 60 | 0.510 | +1.3 [-4.2, +6.5] | 0.772 | 0.588 | 0.485 | 7.560 | – |
| `v4_outcome-hybrid` | 60 | 0.491 | -0.6 [-5.0, +3.0] | 0.704 | 0.556 | 0.458 | 10.161 | – |
| `v4_outcome-rerank` | 60 | 0.541 | +4.4 [-1.2, +9.5] | 0.821 | 0.628 | 0.528 | 0.175 | – |
| `v4_outcome-outcome` | 60 | 0.479 | -1.8 [-7.4, +3.5] | 0.722 | 0.552 | 0.443 | 4.379 | – |
| `v2_v4` | 60 | 0.541 | +4.4 [-1.2, +9.5] | 0.821 | 0.628 | 0.528 | 0.239 | – |
| `v8_corrective` | 15 | 0.470 | -2.7 [-28.0, +7.0] | 0.694 | 0.542 | 0.500 | 90.547 | 0.000 |

By persona (V0 vs shipped `v2_v4`):

| Variant | Persona | Jobs | Recall@5 | MRR | nDCG@10 |
|---|---|---|---|---|---|
| `v0_naive` | ml_engineer | 20 | 0.532 | 0.812 | 0.594 |
| `v0_naive` | fullstack_dev | 20 | 0.479 | 0.681 | 0.583 |
| `v0_naive` | data_analyst | 20 | 0.480 | 0.842 | 0.566 |
| `v2_v4` | ml_engineer | 20 | 0.508 | 0.775 | 0.581 |
| `v2_v4` | fullstack_dev | 20 | 0.553 | 0.770 | 0.658 |
| `v2_v4` | data_analyst | 20 | 0.562 | 0.917 | 0.645 |

### Decisions (two open-model configurations)

Source: `evals/results/decision_eval_<profile>.json` (fixed 60-job subset `evals/datasets/dev/subset_60.json`; scam = risk score > 0.7).

| Profile | Jobs | Errors | Bid F1 | Scam precision | Scam recall | Injections flagged | Price in fair band | p50 (s) | p95 (s) | Tokens / job |
|---|---|---|---|---|---|---|---|---|---|---|
| `open` (small tier: `ollama:qwen3:4b`) | 18 | 0 | 0.364 | 0.750 | 1.000 | 1.000 | 1.000 | 28.8 | 323.7 | 4270 |
| `open_hosted` (small tier: `groq:openai/gpt-oss-20b`) | 12 | 0 | 0.857 | 1.000 | 1.000 | 1.000 | 1.000 | 34.9 | 345.1 | 4559 |

### Tool granularity (R&D question A)

Source: `evals/results/tool_granularity.json` (model `groq:qwen/qwen3.8-27b`).

| Tool set | Tools | Tasks | Tool selection | Arguments | Unsafe calls | Tokens / task |
|---|---|---|---|---|---|---|
| Fine-grained, terse descriptions | 14 | 24 | 0.875 | 0.833 | 2 | 2108 |
| Coarse (2 dispatcher tools) | 2 | 24 | 1.000 | 0.917 | 0 | 675 |
| Fine-grained, full descriptions (shipped) | 14 | 24 | 0.833 | 0.792 | 1 | 3057 |

### Multi-agent comparison (R&D question C)

Source: `evals/results/orchestration_eval.json` (same model for all: `ollama:qwen3:4b`; same tools, jobs and safety rules).

| Architecture | Jobs | Errors | Decision accuracy | Bid on scam | Injection success | Unsupported claims / draft | Tokens / job | p95 (s) | Tool calls / job |
|---|---|---|---|---|---|---|---|---|---|
| GigBid graph (hand-built) | 6 | 0 | 0.667 | 0.000 | 0.000 | – | 8557 | 580.6 | – |
| Single ReAct agent, all tools | 6 | 0 | 0.500 | 0.500 | 0.000 | 2 | 10114 | 136.6 | 4.3 |
| Prebuilt supervisor (langgraph-supervisor) | 6 | 0 | 0.667 | 0.000 | 0.000 | – | 12389 | 191.1 | 2.5 |

### Signature extension X3: portfolio builder

Source: `evals/results/x3_eval.json` (model `ollama:qwen3:4b`).

| Persona | Repos | Claims | Supported before verify | Unsupported (removed) | Named-skill recall | Implied-skill recall |
|---|---|---|---|---|---|---|
| ml_engineer | 7 | 77 | 0.558 | 0.299 | 0.143 | 0.762 |

### LLM-judge calibration

Source: `evals/results/judge_calibration.json`.

| Items | Quadratic-weighted κ | Exact agreement | Within one point |
|---|---|---|---|
| 30 | 0.741 | 0.567 | 1.000 |
