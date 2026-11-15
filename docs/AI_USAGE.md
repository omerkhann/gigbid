# AI usage

The assignment allows AI coding assistants and holds the author accountable for every line. This file records which tool was used, for what, and mistakes it made that were caught.

## Tool

**Claude Code** (Anthropic, Claude Opus models), in VS Code on Windows, used throughout as a pair programmer. Every change was reviewed, run, and tested before commit; commits are small and carry a `Co-Authored-By` line.

## What it helped with

| Area | Files | How |
|---|---|---|
| Data pipelines | `pipelines/*`, `docs/DATA_CARD.md` | Dataset profiling, cleaning code, data card draft |
| GigSim | `gigsim/*`, `docs/GIGSIM_DESIGN.md` | Design discussion (simplified from a first, heavier design), implementation, tests |
| Persona corpus | `pipelines/build_personas.py`, `data/personas/*` | Generator code; generated text was spot-checked |
| MCP servers | `mcp_servers/*`, `tests/contract/*` | Implementation, guard layer, contract tests |
| Agents and graphs | `agent/*` | Nodes, graphs, prompts, config, memory rules |
| Backend and UI | `apps/api/*`, `worker/*`, `apps/web/*` | API, worker, Next.js UI, Playwright tests |
| RAG and evals | `rag/*`, `evals/*` | Variants, eval runners, threshold checks, results tables |
| Docs | `docs/*`, `README.md` | Drafts, then edited |

Design decisions (what to build, what to cut, what ships) were made by the author; the reasoning is in [docs/adr/](adr/).

## Mistakes it made that were caught

1. **It edited a frozen file.** A repo-wide replace of `localhost` with `127.0.0.1` (to fix a 2-second IPv6 lookup penalty on Windows) also changed a docstring in `gigsim/llm_client.py`. GigSim is frozen at `gigsim-v1`, and CI would have failed. Caught in `git status` before committing, and reverted.
2. **It extrapolated a benchmark that didn't match real use.** The cross-encoder reranker was timed at 5.2 s per 30 pairs with short test queries, so a full run looked feasible. Real job queries are about 1,700 characters, so every pair hit the 512-token limit, and the eval ran 100 s per job. Caught when the run made no progress for 30 minutes. Fixed by switching to a smaller reranker, capping pair length, and tuning ONNX threads (ADR 0008).
3. **It documented behaviour the code doesn't have.** A draft ADR said a dead MCP server moves the run to `needs_attention`; the code uses `waiting_marketplace` (resumable) or `dead_letter`. Caught by checking the claim against `agent/nodes/common.py` before committing.
4. **It set an option where it had no effect.** In the decision eval, `interrupt_before` was set on a `.with_config(...)` wrapper rather than on the compiled graph, so runs went on to draft proposals. Caught because a "decisions only" run was using Writer tokens.

5. **It computed a percentile wrong.** The eval runners took p95 as `sorted(x)[int(0.95 * (n - 1))]`, which returns the *minimum* when n = 2 and understates the tail for small samples. Caught when a results file showed p95 below p50. Fixed with a nearest-rank helper (`evals/stats.py`); the affected summaries were recomputed from their stored rows before any number was reported.

<!-- Add at least one example from your own review here, in your own words. -->
