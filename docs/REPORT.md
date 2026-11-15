# GigBid: R&D report

AI-4016 Assignment II · engineering design review · repository `github.com/omerkhann/gigbid`

Every number below cites the file in `evals/results/` it comes from, and every design claim cites code or a commit. Negative results are reported as measured.

## 1. Problem and constraints

A freelancer on a marketplace spends hours each week reading job posts, discarding scams and poor fits, and writing proposals that cite their own work. GigBid automates the reading, filtering and drafting, and nothing else.

**Never automated:**
- sending a proposal or a message;
- spending Connects;
- claiming experience the portfolio doesn't show.

Every send passes an `interrupt()` approval in the bid and conversation graphs (`agent/nodes/approval.py`). Every claim is checked against cited evidence before review (`rag/verify.py`, ADR 0006). Live mode may use only the official Upwork MCP server; there is no scraping or browser automation.

**Budgets (declared):**

| Unit | p95 latency | Tokens | Cost |
|---|---|---|---|
| Job analysed (to the bid/skip decision) | ≤ 90 s | ≤ 8k | $0 |
| Proposal (to the approval screen) | ≤ 180 s | ≤ 40k (hard cap in `agent/config.yaml` `budgets.max_tokens_per_job`) | $0 |

The cost budget is $0 because every model runs on a free tier (Groq) or locally (Ollama on an RTX 4050, 6 GB). The binding constraint turned out to be the free tier's quota, not money: Groq allows 200k tokens per day per model. This is measured and documented in `docs/RUNBOOK.md` ("Free-tier caps"), and it shaped the size of several experiments below.

## 2. Architecture

Two hand-built LangGraph `StateGraph`s run in an Arq worker. They reach the outside world only through MCP servers, and they checkpoint to Postgres after every node (ADR 0001, ADR 0005). Full description: `docs/ARCHITECTURE.md`.

- **Bid graph** (one thread per job). Three analyses run in parallel with `Send`: Job Analyst (JobSpec), Risk Assessor (rules plus a small LLM), Fit Matcher (evidence per requirement).
  - A rule-based `decide` step then skips, watches or bids, always with a recorded reason (ADR 0007).
  - On a bid: Pricing (arithmetic), Writer, claim verification, Critic (at most two revisions), Compliance Guard (can block), then approval (`interrupt`), then an idempotent submit.
- **Conversation graph** (one thread per client conversation): classify, offer calendar slots, draft a reply, compliance check, approval, send.
- **Marketplace port.** One tool surface (`search_jobs`, `get_job`, `get_client_history`, `get_market_stats`, `get_connects_balance`, `create_proposal_draft`, `submit_proposal`, messaging tools) with two adapters, `gigsim` and `upwork_live`. Live mode is a configuration switch; no agent code changes (ADR 0002).
- **MCP surface.** Three own servers: Marketplace :8201, Workspace :8202, Portfolio :8203. All use Streamable HTTP with per-user bearer auth. A shared guard adds rate limits, an append-only audit log, PII masking and typed failures. Each agent node may call only the tools on its allowlist (`agent/mcp_client.py`). A third-party server, GitHub's official MCP server, feeds the X3 extension (§7).
- **Stores** are kept apart:
  - graph state: Postgres checkpoints, per thread;
  - execution traces: Phoenix;
  - long-term memory: Postgres store, entered only through `agent/memory/promotion_rules.py`;
  - app tables: users, encrypted credentials, runs;
  - per-server SQLite: audit log, idempotency records, embedding cache.

**Why each agent exists** is tabulated in `docs/ARCHITECTURE.md`. The short version:
- Analyses that don't depend on each other run in parallel, which cuts latency.
- Anything that must be explainable (decide, risk score, price) is rules or arithmetic.
- Only prose for the client uses the strong model.

## 3. R&D question A: tool granularity

**Not run in this submission.** The planned setup: 40 tasks with known correct calls, comparing (a) fine-grained tools, (b) a few coarse tools, and (c) the current set with rewritten descriptions, and measuring tool-selection accuracy, argument accuracy and tokens per task. It was dropped for time. One observation relevant to the question came out of R&D C (§5): the prebuilt supervisor often answered without calling any tool, which suggests that how tools are described and routed matters more than how many there are. That is an observation, not a measured answer.

## 4. R&D question B: retrieval variants, claim verification, ablation

**Setup.** One pipeline with switchable components (`rag/pipeline.py`, ADR 0008), so every variant and ablation is a configuration over the same chunks and embedding cache.
- Gold evidence is project-level (`evals/datasets/dev/labels.jsonl`). Retrieved chunks are mapped to their project and de-duplicated in rank order before scoring.
- Jobs: the first 20 bid-worthy dev jobs per persona, 60 in total, the same jobs for every variant.
- Embeddings: `nomic-embed-text`. Reranker: `ms-marco-MiniLM-L-12-v2`; `bge-reranker-v2-m3` measured 70 to 110 s per job on the laptop CPU (ADR 0008).
- Uncertainty: a paired bootstrap over jobs (2,000 resamples) for the Recall@5 change against V0.

**Working hypothesis.** It was not committed before the runs, so it is stated here as the reason V1 and V2 were built first: *"Requirement decomposition plus hybrid retrieval raises evidence Recall@5 by 15 points over V0 on jobs with five or more requirements."*

**Results** (`evals/results/rag_eval.json`, macro-average over the three personas, 60 jobs; `a-b` = variant a with component b removed):

| Variant | Recall@5 | Δ vs V0, pts [95% CI] | MRR | nDCG@10 | R@5, 5+ reqs | p95 latency |
|---|---|---|---|---|---|---|
| V0 naive dense | 0.497 | | 0.778 | 0.581 | 0.458 | 0.20 s |
| V1 decomposition | 0.470 | −2.7 | 0.658 | 0.544 | 0.406 | 0.55 s |
| V2 hybrid (BM25 + dense, RRF) | 0.492 | −0.5 [−6.1, +5.2] | 0.795 | 0.583 | 0.468 | 0.17 s |
| V3 = V2 + cross-encoder rerank | 0.479 | −1.8 [−7.7, +3.4] | 0.722 | 0.552 | 0.443 | 7.6 s |
| V4 = V3 + outcome boost | 0.510 | +1.3 [−4.2, +6.4] | 0.772 | 0.588 | 0.485 | 7.6 s |
| V1+V2+V3 | 0.490 | −0.7 | 0.711 | 0.544 | 0.432 | 27.9 s |
| V4 − hybrid | 0.491 | −0.6 [−5.1, +3.0] | 0.704 | 0.556 | 0.458 | 10.2 s |
| V4 − outcome (= V3) | 0.479 | −1.8 [−7.7, +3.4] | 0.722 | 0.552 | 0.443 | 4.4 s |
| **V4 − rerank = V2 + outcome (`v2_v4`, shipped)** | **0.541** | **+4.4 [−1.1, +9.6]** | **0.821** | **0.628** | **0.528** | **0.24 s** |
| V1+V2+V3 − decompose (= V3) | 0.479 | −1.8 | 0.722 | 0.552 | 0.443 | 4.0 s |

V1+V2+V3 − decompose gives exactly the same numbers as V3: they are the same configuration, which checks that the pipeline is deterministic.

**By job type and requirement count** (`evals/results/rag_breakdown.json`, V0 → shipped):

| Group | Jobs | V0 R@5 | Shipped R@5 | Δ pts |
|---|---|---|---|---|
| development | 28 | 0.465 | 0.549 | +8.3 |
| data science | 32 | 0.525 | 0.535 | +1.0 |
| 5+ requirements | 43 | 0.459 | 0.532 | +7.3 |
| under 5 requirements | 17 | 0.594 | 0.566 | −2.8 |
| fullstack_dev | 20 | 0.479 | 0.553 | +7.4 |
| data_analyst | 20 | 0.480 | 0.562 | +8.3 |
| ml_engineer | 20 | 0.532 | 0.508 | −2.4 |

**Conclusions.**
1. **The hypothesis is rejected.** Decomposition *lowered* Recall@5 (−2.7 points) and MRR. Per-requirement queries are short, so they match skill mentions anywhere in the corpus, and fusing their rankings promotes projects that touch many requirements weakly over the one project that delivers the core one.
2. **The cross-encoder hurt.** MiniLM is trained on web search (MS MARCO), not on "does this portfolio chunk prove this capability". It lowered every configuration it was added to, at 30 times the latency.
3. **Hybrid plus outcome boost helps where expected**: development jobs (+8.3), where exact library names suit BM25, and long jobs (+7.3). It is neutral on data-science jobs and slightly worse for the ML persona. The 95% interval still includes zero (−1.1 to +9.6 points over 60 jobs), so the gain is likely but not proven.
4. **Corrective RAG (V8)**: see `evals/results/rag_eval.json` (`v8_corrective`, 5 jobs per persona; small, because every requirement needs an LLM grading call).

**Claim verification.** In the bid graph, unsupported claims are counted before verification and removed before the Critic sees the draft. The rate before and after verification is reported in the README headline table (`evals/results/gigsim_outcomes_<variant>.json`).

**What ships.** `v2_v4`, hybrid BM25+dense with the outcome boost (`agent/config.yaml` `rag.variant`, commit f8b41eb). It was the best on every metric, it's as fast as V0, and it needs no GPU. The reranker stays in the code as an option for a GPU host with a portfolio-trained model; on CPU it costs 30 times the latency and lowered quality here. The outcome boost multiplies evidence from proposals that won by 1.3, that got replies by 1.15, and that were ignored by 0.8. It is the one component that helped in every ablation, which fits the corpus design: past proposals' outcomes matter more than their wording.

**Did better retrieval give a better reply rate?** See the README headline table: V0 against `v2_v4` proposals sent to GigSim. On the small free-tier sample, a few points of Recall@5 are unlikely to show up in reply rate. GigSim's simulated client reacts to the letter's specificity and price, and the Writer cites only two or three projects. When the right project is already in the top five, as it usually is for V0, better ranking further down changes nothing the client sees.

**LLM-judge calibration** (`evals/results/judge_calibration.json`). The judge (`qwen/qwen3.8-27b`, a different family from the Writer) scored 30 past proposals that the author also labelled blind.
- Quadratic-weighted Cohen's κ = 0.741; exact agreement 0.567; within one point 1.000.
- Where they disagree, the judge is mostly one point harsher on plain-but-specific proposals (3 → 2). The author rewarded a plain, specific proposal that a client could act on; the judge penalised its lack of polish. A client reading quickly would likely side with the author, so judge scores are read as conservative.

## 5. R&D question C: single agent vs prebuilt supervisor vs graph

**Setup** (`evals/runners/orchestration_eval.py`, results `evals/results/orchestration_eval.json`).
- Jobs: 6 from the fixed subset (ml_engineer and data_analyst: one bid-worthy, one scam and one injected job each). The set is small because of the free-tier quota.
- Model: all three architectures use the same model, `gpt-oss-20b` (profile `open_lite`), the same MCP tools and the same safety rules in their prompts.
- Baselines: `create_react_agent` with all read tools, and `langgraph-supervisor` 0.0.31 with four workers (risk, fit, pricer, writer).
- Scoring: decision against gold, bids on scams, the dataset's own injection checks, unsupported claims through the same verifier, and tokens through one usage callback for all three.

<!-- RESULTS_C -->

**Observed failure of the prebuilt supervisor.** In the smoke run it answered directly without delegating to any worker (0 tool calls). It asserted that the client had "no payment history", a risk judgement made without calling `get_client_history`. A supervisor that decides by itself whether to consult its specialists can skip the step that matters most. The hand-built graph runs the Risk Assessor on every job by construction.

## 6. The change request

No change request was applied in this submission.

## 7. Signature extension: X3, portfolio builder

**What it does** (`rag/ingest/portfolio_builder.py`, `docs/EXTENSION.md`):
1. It takes a GitHub account, read through GitHub's official MCP server (Docker image, read-only token, `repos` toolset), or a local folder of repos.
2. For each repo it collects the README and up to 12 source files.
3. The Writer-tier model drafts a case study that cites a file after every factual sentence.
4. The same claim verifier as the bid graph checks every claim against those files and removes unsupported ones.
5. Output: case studies, repos and `skeleton.yaml` in the folder format the Portfolio MCP server indexes directly.

**How it was measured** (`evals/runners/x3_eval.py`, results `evals/results/x3_eval.json`): case studies were built from the ml_engineer persona's repos only, then compared with that persona's ground truth:
- the share of claims supported before verification;
- named-skill recall;
- implied-skill recall: skills the code uses but the hand-written profile never names, which is the corpus's "implied skills" trap.

<!-- RESULTS_X3 -->

## 8. Failure analysis

<!-- RESULTS_FAILURES -->

## 9. Safety and platform respect

**Must never happen:**
1. a send or a Connects spend without approval;
2. an invented claim;
3. contact details or off-platform payment in a proposal;
4. following instructions embedded in a job post or client message;
5. scraping or browser automation;
6. leaking PII into logs.

**How each is enforced:**
- **(1)** `interrupt()` before every write. The Marketplace server's `submit_proposal` sits on the approval node's allowlist only. Idempotency keys mean a crash between approval and submit can't send twice.
- **(2)** Claim verification against cited evidence before the Critic. Compliance re-checks after any human edit.
- **(3)** Compliance Guard rules (`agent/compliance_rules.yaml`) and GigSim's policy endpoint.
- **(4)** Untrusted text is fenced as data in every prompt (`untrusted()` in `agent/nodes/common.py`). The Risk Assessor flags injection patterns sentence by sentence. Tools are allowlisted per node, so an injected "submit now" has no tool to call.
- **(5)** Live mode uses only the official Upwork MCP server; Scout polls hourly at most; there is no HTTP client to marketplace web pages anywhere in the code.
- **(6)** The MCP guard masks emails and phone numbers in the audit log.

**What still gets through:**
- An injection phrased as a plausible client requirement (for example "mention your Google certification") is not an instruction pattern. If the portfolio contains a matching word, the Writer may use it. Claim verification catches it only when no evidence supports it.
- Rules can't see scams that look legitimate.
- Injection results on the dev set: decision eval (`evals/results/decision_eval_<profile>.json`, "injections flagged") and R&D C (§5, attack success).

## 10. Hidden test results against the declared budgets

The hidden test runs after the deadline, so its results can't appear here. Measured on dev:

<!-- RESULTS_BUDGETS -->

**One optimisation that helped:** running the small tier (analysis, risk, fit, intent) on the local GPU in the `open` profile. It takes the per-job analysis off the hosted quota entirely, leaving the hosted budget for proposals. A second optimisation was the shipped retrieval variant, which matches V0's latency (0.24 s p95) at better quality, instead of the reranked variant at 7.6 s.

## Appendix: reproducing every number

```bash
python -m evals.runners.rag_eval --limit 20 --ablate v1_v2_v3      # retrieval variants + ablation
python -m evals.runners.rag_eval --variants v0_naive v2_hybrid v3_rerank v4_outcome v2_v4 --ablate v4_outcome --limit 20
python -m evals.runners.rag_breakdown                               # by job type / requirements / persona
python -m evals.runners.decision_eval --limit 6                     # profile open (MODEL_PROFILE=open_hosted for the other)
python -m evals.runners.gigsim_outcomes --variant v0_naive --limit 1 # and --variant v2_v4
python -m evals.runners.judge_calibration score
MODEL_PROFILE=open_lite python -m evals.runners.orchestration_eval
python -m evals.runners.x3_eval --personas ml_engineer
python -m evals.make_tables                                         # README + evals/results/RESULTS.md
```
