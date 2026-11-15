"""Live Upwork adapter (assignment A4). Not built yet.

Plan: connect to Upwork's official MCP server (https://mcp.upwork.com/mcp) with
MultiServerMCPClient over Streamable HTTP, complete the OAuth 2.1 flow per user, store tokens
encrypted, and map Upwork's tools onto the MarketplaceBackend methods. In live mode, writes only
ever create drafts that the user confirms on Upwork. No scraping, no browser automation.
"""

from __future__ import annotations

from mcp_servers.marketplace.adapters.base import MarketplaceError


class UpworkLiveBackend:
    def __getattr__(self, name):
        async def not_ready(*args, **kwargs):
            raise MarketplaceError("not_configured", "Live Upwork mode is not set up yet (assignment A4).")
        return not_ready
