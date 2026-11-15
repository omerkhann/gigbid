"""Sign in / out / register. Sessions are HttpOnly cookies; only a hash of the token is stored."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response

from apps.api.auth.security import hash_password, new_session_token, token_hash, verify_password
from apps.api.deps import SESSION_COOKIE, Services, User
from apps.api.schemas import LoginIn, Me, RegisterIn

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_DAYS = 14


async def start_session(db, user_id: str, response: Response) -> None:
    token, digest = new_session_token()
    await db.run("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                 digest, user_id, datetime.now(UTC) + timedelta(days=SESSION_DAYS))
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=SESSION_DAYS * 86400,
                        secure=False)  # set secure=True behind HTTPS (Caddy)
    response.headers["X-Session-Token"] = token  # for non-browser clients (tests, scripts)


@router.post("/login", response_model=Me)
async def login(body: LoginIn, response: Response, svc: Services):
    row = await svc.db.one("SELECT * FROM users WHERE email = %s", body.email.lower())
    if row is None or not verify_password(body.password, row["password"]):
        raise HTTPException(401, "Wrong email or password")
    await start_session(svc.db, row["user_id"], response)
    return Me(**{k: row[k] for k in ("user_id", "email", "name", "persona", "settings")})


@router.post("/register", response_model=Me, status_code=201)
async def register(body: RegisterIn, response: Response, svc: Services):
    if await svc.db.one("SELECT 1 AS x FROM users WHERE email = %s", body.email.lower()):
        raise HTTPException(409, "Email already registered")
    uid = f"u-{uuid.uuid4().hex[:10]}"
    await svc.create_user(uid, body.email.lower(), body.name, body.password, body.persona)
    await start_session(svc.db, uid, response)
    return Me(user_id=uid, email=body.email.lower(), name=body.name, persona=body.persona, settings={})


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, svc: Services):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await svc.db.run("DELETE FROM sessions WHERE token_hash = %s", token_hash(token))
    response.delete_cookie(SESSION_COOKIE)


@router.get("/me", response_model=Me)
async def me(user: User):
    return Me(**user)


_ = hash_password  # re-exported for seeding
