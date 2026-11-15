# MCP Tool Inventory

Agents never call GigSim, Upwork, a database or a file directly. Every capability is an MCP tool with a schema, an owner and a test. Tool signatures are snapshotted in [tests/contract/snapshots/](../tests/contract/snapshots/), and CI fails when one changes unintentionally.

Annotation key: **RO** readOnlyHint · **D** destructiveHint · **I** idempotentHint · **OW** openWorldHint.

## Marketplace server (`mcp_servers/marketplace`, built)

Run: `python -m mcp_servers.marketplace.server` (Streamable HTTP at `http://127.0.0.1:8201/mcp`).

- **Auth:** bearer token on the HTTP endpoint, one token per GigBid user, mapped to that user's marketplace credential. Requests without a valid token get `401`.
- **Rate limit:** per user, kept under GigSim's limits: 50 reads/min, 20 drafts or messages/min, 4 submits/min. Callers wait politely up to 30 s, then get `rate_limited`.
- **Idempotency:** every write takes an `idempotency_key`. The server stores the result per (user, tool, key) and forwards the key to the marketplace, so a retry never submits twice or spends Connects twice.
- **Audit:** append-only SQLite table (user, tool, PII-masked arguments and result, status, trace id). Database triggers reject `UPDATE` and `DELETE`.
- **Backend:** `MARKETPLACE_BACKEND=gigsim` (built) or `upwork_live` (assignment A4, not built yet). Agents cannot tell which one is behind the server.
- **Errors:** `{"error": code, "detail": ...}`. Codes include `marketplace_unavailable` (after bounded retries; drives GigBid's degraded mode), `policy_violation`, `insufficient_connects`, `already_submitted`, `idempotency_key_reused`, `rate_limited`.

| Tool | R/W | Annotations | Purpose |
|---|---|---|---|
| `search_jobs` | Read | RO, I, OW | Search open jobs (query, category, skills, min budget, posted after), newest first, with previews |
| `get_job` | Read | RO, I, OW | Full job post, screening questions, Connects cost, client id |
| `get_client_history` | Read | RO, I, OW | Payment verified, spend, rating (null = new client), reviews, country, posted jobs |
| `get_connects_balance` | Read | RO, I, OW | Balance and recent ledger entries |
| `get_market_stats` | Read | RO, I, OW | p10–p90 of what comparable contracts actually paid |
| `list_proposals` | Read | RO, I, OW | Proposals with status history (pipeline board) |
| `list_threads` | Read | RO, I, OW | Client conversations |
| `list_messages` | Read | RO, I, OW | Messages in one conversation |
| `create_proposal_draft` | Write | I, OW | Save a draft on the marketplace; nothing sent, no Connects spent |
| `submit_proposal` | Write | **D**, I, OW | Send a draft and spend Connects. `dry_run=true` returns exactly what would be sent and its cost |
| `send_message` | Write | **D**, I, OW | Reply to a client. `dry_run=true` checks policy and returns the message |

Tests: [tests/integration/test_marketplace_mcp.py](../tests/integration/test_marketplace_mcp.py) (in-memory MCP client against GigSim in-process), [tests/contract/test_tool_schemas.py](../tests/contract/test_tool_schemas.py) (schema snapshot).

## Portfolio server (`mcp_servers/portfolio`, not built yet)

Read-only: `search_evidence(requirement, k, filters)`, `get_case_study(id)`, `list_skills()`, resource templates `portfolio://case/{id}` and `portfolio://proposal/{id}`, and prompt templates.

## Workspace server (`mcp_servers/workspace`, not built yet)

Free calendar slots, tentative interview holds, email drafts (local mock).

## Third-party servers (not connected yet)

| Server | Trust rationale |
|---|---|
| Upwork official MCP (`https://mcp.upwork.com/mcp`) | The platform's own server, OAuth 2.1; writes only create drafts the user confirms on Upwork |
| GitHub MCP | Official server, used read-only for ingesting a freelancer's repos |
