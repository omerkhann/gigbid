# Runbook

## Start everything (development, Windows or Linux)

```bash
docker compose -f infra/docker-compose.yml up -d          # Postgres (host port 5433) + Redis
uv sync --extra dev --extra data

python -m uvicorn gigsim.app:create_app --factory --port 8100   # GigSim
python -m mcp_servers.marketplace.server                         # :8201
python -m mcp_servers.workspace.server                           # :8202
python -m mcp_servers.portfolio.server                           # :8203 (first search embeds the portfolio, ~2 min)
python -m worker.main                                            # Arq worker: graph runs, Scout, outcome polling
python -m apps.api.serve --port 8000                             # API (docs at http://localhost:8000/docs)
```

Ollama must be running for the `open` profile (local `qwen3:4b`, `nomic-embed-text`). Without a GPU, set `MODEL_PROFILE=open_hosted`.

Sign in: `reviewer@gigbid.dev` / `REVIEWER_PASSWORD` (default `gigbid-review`; set a real one when deployed).

Why `apps.api.serve` and not `uvicorn apps.api.main...`: on Windows uvicorn creates a Proactor event loop before the app loads, and psycopg's async mode (Postgres pool and checkpointer) can't use it. The launcher starts on a selector loop. On Linux both work.

## Schedules (assignment E1)

| What | When | Why |
|---|---|---|
| Scout (saved searches) | Each saved search has its own interval, default **60 min**, minimum 15 min. The worker checks every minute which are due | New jobs matter within the hour; more often wastes model budget. Each Scout run analyses at most **5 new jobs** |
| Outcome polling | Every 5 min | Proposal statuses and new client messages; cheap read-only calls |
| **Live Upwork mode** | Saved searches forced to **≥ 60 min** | Upwork's automation rules: polling must not look like scraping. Hourly reads via the official MCP server are well within normal use |

Every task is idempotent:
- **Graph runs:** they resume from Postgres checkpoints, and marketplace writes carry idempotency keys, so a retried task never double-submits.
- **Scout:** it records every job it has seen (by id and by a text fingerprint), so a worker restart never re-analyses a job.
- **Queue keys:** Arq job ids are deterministic per action, so a double-clicked approval can't queue twice.

## Operations notes

- **Budget guard.** Demo accounts other than the reviewer have no saved search. Scheduled scouting for every account on a fresh database queued 40 full analyses in one minute in testing; that would exhaust Groq's free tier.
- **Logs.** The worker logs every task start and end (`arq.worker`). If a job seems stuck, look there first, then at `runs.status` / `status_reason` in Postgres.
- **Clear the queue** (development only): delete Redis keys `arq:*`.
- **Ports.** GigSim 8100, MCP 8201–8203, API 8000, Postgres 5433 (a native Postgres may already use 5432), Redis 6379.

## Free-tier caps (measured 2026-11-15)

GigBid runs on free tiers only. The binding limit is **Groq's per-model daily token quota: 200,000 tokens/day per model** on the free plan, a rolling window. The account sees four chat models: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b` and `qwen/qwen3.8-27b`, each with its own quota. The OpenRouter key is also free tier (no credits).

| What | Cost | Runs per day on one model's quota |
|---|---|---|
| One job analysed (to the decision) | ~5k tokens, mostly small tier (local Ollama on the laptop: no quota) | unlimited locally; ~40 on hosted `gpt-oss-20b` |
| One proposal (draft, claim check, Critic loop) | ~30k tokens on the strong tier | **~6 per day** on `gpt-oss-120b` |

On 2026-11-15, evaluation runs used the whole `gpt-oss-120b` quota (Groq returned `429 ... tokens per day (TPD): Limit 200000, Used 199520`).

**What GigBid does about it:**
- Every tier is a fallback chain (`agent/config.yaml`). When `gpt-oss-120b` returns 429, the Writer drops to `gpt-oss-20b`, and the trace records which model answered.
- Small-tier work (analysis, risk, fit, intent) runs on local Ollama in the `open` profile, so it costs no hosted quota.
- Scout analyses at most 5 new jobs per run, and only accounts with a saved search are scouted.

**Effect on the evaluation:**
- Proposal-writing evals ran on fewer jobs than planned.
- R&D question C ran all architectures on one model, `gpt-oss-20b` (profile `open_lite`), to stay fair inside the quota.
- Numbers are reported with their job counts; see the README results.

**Effect on the deployed system:** a busy day degrades the drafts to `gpt-oss-20b` rather than failing. A paid tier (Groq Dev, or credits on OpenRouter) removes the cap without code changes: add the model to the tier's chain.
