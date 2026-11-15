"""How agents reach MCP servers (assignment A6: each agent gets only the tools it needs).

`McpGateway.call(node, server, tool, args, trace_id)` checks the node's allowlist, opens a session
to that server (Streamable HTTP with the user's bearer token in production; in-memory in tests),
forwards the trace id in the request meta, and returns the tool's structured result.

Errors come back as typed exceptions:
  ToolNotAllowed      - the node asked for a tool outside its allowlist (a bug, never retried)
  MarketplaceDown     - marketplace_unavailable after the server's own retries -> degraded mode
  ToolCallFailed      - any other tool error, with the server's error code
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp import ClientSession

# node -> {(server, tool)}. Mirrors the agent/MCP table in docs/BID_GRAPH_DESIGN.md.
ALLOWLIST: dict[str, set[tuple[str, str]]] = {
    "scout": {("marketplace", "search_jobs"), ("marketplace", "get_job")},
    "job_analyst": set(),
    "risk_assessor": {("marketplace", "get_client_history")},
    "fit_matcher": {("portfolio", "search_evidence")},
    "pricing": {("marketplace", "get_market_stats"), ("marketplace", "get_connects_balance")},
    "writer": {("portfolio", "search_evidence")},
    "verify_claims": set(),
    "critic": set(),
    "compliance": set(),
    "prepare_draft": {("marketplace", "create_proposal_draft"), ("marketplace", "submit_proposal")},
    "submit": {("marketplace", "submit_proposal"), ("marketplace", "get_connects_balance")},
    "client_liaison": {("marketplace", "list_threads"), ("marketplace", "list_messages"),
                       ("marketplace", "send_message"), ("workspace", "get_free_slots"),
                       ("workspace", "create_interview_hold"), ("workspace", "create_email_draft")},
}


class ToolNotAllowed(Exception):
    pass


class ToolCallFailed(Exception):
    def __init__(self, code: str, detail: str, body: dict | None = None):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.body = code, detail, body or {}


class MarketplaceDown(ToolCallFailed):
    pass


SessionFactory = Callable[[], AbstractAsyncContextManager[ClientSession]]


def http_session_factory(url: str, token: str) -> SessionFactory:
    """Streamable HTTP session with a bearer token (one per user)."""
    from contextlib import asynccontextmanager

    from mcp.client.streamable_http import streamablehttp_client

    @asynccontextmanager
    async def open_session():
        async with (streamablehttp_client(url, headers={"Authorization": f"Bearer {token}"}) as (r, w, _),
                    ClientSession(r, w) as s):
            await s.initialize()
            yield s
    return open_session


class McpGateway:
    def __init__(self, sessions: dict[str, SessionFactory], allowlist: dict[str, set[tuple[str, str]]] | None = None):
        self.sessions = sessions
        self.allowlist = allowlist or ALLOWLIST

    async def call(self, node: str, server: str, tool: str, args: dict[str, Any], trace_id: str) -> dict[str, Any]:
        if (server, tool) not in self.allowlist.get(node, set()):
            raise ToolNotAllowed(f"{node} may not call {server}.{tool}")
        async with self.sessions[server]() as s:
            result = await s.call_tool(tool, args, meta={"trace_id": trace_id})
        if result.isError:
            text = result.content[0].text if result.content else ""
            body = json.loads(text[text.index("{"):]) if "{" in text else {"error": "unknown", "detail": text}
            exc = MarketplaceDown if body.get("error") == "marketplace_unavailable" else ToolCallFailed
            raise exc(body.get("error", "unknown"), body.get("detail", ""), body)
        return result.structuredContent or {}
