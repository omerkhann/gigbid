"""Bearer-token auth shared by GigBid's MCP servers (Streamable HTTP)."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl


class StaticTokenVerifier:
    """Bearer token -> user id, from settings. Requests without a valid token get 401."""

    def __init__(self, users: list[dict], scope: str):
        self.by_token = {u["token"]: u for u in users}
        self.scope = scope

    async def verify_token(self, token: str) -> AccessToken | None:
        u = self.by_token.get(token)
        return AccessToken(token=token, client_id=u["user_id"], scopes=[self.scope]) if u else None


def auth_settings(url: str, scope: str) -> AuthSettings:
    # Static per-user tokens are checked by StaticTokenVerifier itself; they carry no audience.
    return AuthSettings(issuer_url=AnyHttpUrl(url), resource_server_url=AnyHttpUrl(url),
                        required_scopes=[scope], validate_token_resource=False)
