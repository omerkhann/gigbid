# GigSim

The marketplace simulator GigBid is developed and graded against. Design and reasoning: [docs/GIGSIM_DESIGN.md](../docs/GIGSIM_DESIGN.md). Data sources and labels: [docs/DATA_CARD.md](../docs/DATA_CARD.md).

**Frozen at git tag `gigsim-v1`.** CI fails if anything in this folder changes. A fix means a new tag (`gigsim-v2`) and an entry under "Changelog" below, never a silent edit.

## Run

```bash
uv run uvicorn gigsim.app:create_app --factory --port 8100
```

Interactive API docs: http://localhost:8100/docs

| Variable | Default | Meaning |
|---|---|---|
| `GIGSIM_PACK` | `dev` | Scenario set: `dev`, `live`, or `test` (generated locally, not in git) |
| `GIGSIM_POLICY` | `v1` | Policy file in `policies/` |
| `GIGSIM_SPEED` | `24` | Sim hours per wall hour. Use `1` for the deployed `live` set |
| `GIGSIM_CLIENT_MODE` | `heuristic` | `llm` for the real simulated client (needs `GROQ_API_KEY`) |
| `GIGSIM_CLIENT_MODEL` | `qwen/qwen3.8-27b` | Any model on the configured OpenAI-compatible endpoint |
| `GIGSIM_DB` | `data/processed/gigsim.sqlite3` | State file; delete it to start over |
| `GIGSIM_ADMIN` / `GIGSIM_ADMIN_TOKEN` | on / `dev-admin` | Admin routes; disable or set a secret when deployed |
| `GIGSIM_ACCOUNTS` | three dev accounts | JSON list of `{token, freelancer_id, persona}` |

Dev tokens: `dev-ml-engineer`, `dev-fullstack-dev`, `dev-data-analyst`.

## Admin routes (tests, evals, demos)

- `POST /admin/release_all {"on": true}`: eval mode. Every job is visible and clients answer instantly.
- `POST /admin/faults {"down": true}` or `{"error_rate": 0.2}`: outage or random errors.
- `POST /admin/reset`: clear all state and restart the clock.
- `GET /admin/proposals/{id}`: the client's decision and reason, plus the hidden preferences.

## Changelog

- `gigsim-v1` (2026-11-15): first frozen version.
