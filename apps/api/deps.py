"""Request dependencies: the current user (session cookie or bearer token) and app services."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request

from apps.api.auth.security import token_hash

SESSION_COOKIE = "gigbid_session"


def services(request: Request) -> Any:
    return request.app.state.services


async def current_user(request: Request) -> dict:
    # An explicit bearer token wins over the cookie, so a client acting for a specific user is never
    # silently switched to whoever last signed in on that browser.
    bearer = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    token = bearer or request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    db = request.app.state.services.db
    row = await db.one("SELECT u.user_id, u.email, u.name, u.persona, u.settings FROM sessions s JOIN users u USING (user_id) "
                       "WHERE s.token_hash = %s AND s.expires_at > now()", token_hash(token))
    if row is None:
        raise HTTPException(401, "Session expired")
    return row


User = Annotated[dict, Depends(current_user)]
Services = Annotated[Any, Depends(services)]


def trace_id(request: Request) -> str:
    return request.state.trace_id


TraceId = Annotated[str, Depends(trace_id)]
