# 0002 Every external capability behind an MCP server

**Context.** The same agents must run against GigSim and, in live mode, the official Upwork MCP server, without code changes. Agents read untrusted text (job posts, client messages), so what each agent can do must be limited.

**Decision.** Three own servers (Marketplace :8201, Workspace :8202, Portfolio :8203) on Streamable HTTP with per-user bearer auth. The Marketplace server is a port with adapters (`gigsim`, `upwork_live`), so live mode is a config switch. A shared `ToolGuard` adds rate limits, an append-only audit log, PII masking and typed `ToolFailure`s. `agent/mcp_client.py` holds an allowlist per node: the Writer can search the portfolio but cannot submit; only the approval node can call `submit_proposal`.

**Alternatives.** Plain Python functions as tools: faster to write, but no process boundary, no reuse from Claude Desktop or Cursor, and no realistic transport failures to handle. One big server: simpler to deploy, but every agent would see every tool.

**Consequences.** Each call adds a network hop (milliseconds), and each server needs its own tests and contract snapshots (`tests/contract/`). In return, a dead server is a handled, visible failure: an unreachable marketplace moves the run to `waiting_marketplace` (resumable, shown in the UI with the tool error), and other tool failures to `dead_letter` (`agent/nodes/common.py`). The Portfolio server is reusable on its own.
