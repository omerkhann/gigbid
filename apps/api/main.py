"""GigBid API (FastAPI). Run: uvicorn apps.api.main:create_app --factory --port 8000

Graph runs happen in the worker (worker/main.py); the API queues them and reads their checkpoints.
Every request gets a trace id (X-Trace-Id in, or a new one), which travels with queued work into
the graph, every MCP call and the MCP audit logs (assignment E3).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from apps.api.auth.security import encrypt, hash_password
from apps.api.db import Db

if sys.platform == "win32":   # psycopg's async mode needs the selector event loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

DEV_PERSONA_TOKENS = {  # dev MCP tokens per persona (the MCP servers' DEV_USERS); deployments use real ones
    p: {"marketplace_mcp": f"dev-mcp-{p.replace('_', '-')}", "portfolio_mcp": f"dev-pf-{p.replace('_', '-')}",
        "workspace_mcp": f"dev-ws-{p.replace('_', '-')}"}
    for p in ("ml_engineer", "fullstack_dev", "data_analyst")}
DEFAULT_SETTINGS = {"ml_engineer": {"hourly_floor": 30, "fixed_floor": 200, "hourly_rate": 45},
                    "fullstack_dev": {"hourly_floor": 22, "fixed_floor": 150, "hourly_rate": 35},
                    "data_analyst": {"hourly_floor": 18, "fixed_floor": 80, "hourly_rate": 28}}
DEFAULT_SEARCH = {"ml_engineer": {"category": "data_science"}, "fullstack_dev": {"category": "development"},
                  "data_analyst": {"category": "data_science"}}


@dataclass
class Services:
    db: Db
    runtime: Any
    queue: Any
    events: Any

    async def create_user(self, user_id: str, email: str, name: str, password: str, persona: str,
                          saved_search: bool = True) -> None:
        settings = {**DEFAULT_SETTINGS[persona], "autonomy": "approve_everything", "weekly_connects_budget": 80}
        await self.db.run("INSERT INTO users (user_id, email, name, password, persona, settings) VALUES (%s,%s,%s,%s,%s,%s)",
                          user_id, email, name, hash_password(password), persona, json.dumps(settings))
        for provider, token in DEV_PERSONA_TOKENS[persona].items():
            await self.db.run("INSERT INTO credentials (user_id, provider, ciphertext) VALUES (%s,%s,%s) "
                              "ON CONFLICT (user_id, provider) DO UPDATE SET ciphertext = EXCLUDED.ciphertext",
                              user_id, provider, encrypt(token))
        if saved_search:
            await self.db.run("INSERT INTO saved_searches (search_id, user_id, query, every_minutes) VALUES (%s,%s,%s,60)",
                              f"s-{uuid.uuid4().hex[:10]}", user_id, json.dumps(DEFAULT_SEARCH[persona]))

    async def tokens(self, user_id: str) -> dict[str, str]:
        from worker.tasks import load_user

        return (await load_user({"db": self.db}, user_id))[1]

    async def marketplace(self, user: dict, tool: str, args: dict, trace_id: str) -> dict:
        """A read-only marketplace call on behalf of the user (pipeline, messages, health)."""
        tokens = await self.tokens(user["user_id"])
        gateway = self.runtime.config(user, "api", trace_id, tokens)["configurable"]["deps"].gateway
        gateway.allowlist = {**gateway.allowlist, "api": {("marketplace", t) for t in
                                                          ("list_proposals", "list_threads", "list_messages",
                                                           "get_connects_balance", "get_job")}}
        return await gateway.call("api", "marketplace", tool, args, trace_id)


async def seed(svc: Services) -> None:
    """Demo accounts, only if no users exist. The reviewer login is required by the assignment."""
    if await svc.db.one("SELECT 1 AS x FROM users LIMIT 1"):
        return
    reviewer_pw = os.environ.get("REVIEWER_PASSWORD", "gigbid-review")
    await svc.create_user("u-reviewer", os.environ.get("REVIEWER_EMAIL", "reviewer@gigbid.dev"), "Reviewer",
                          reviewer_pw, "data_analyst")
    for persona in DEV_PERSONA_TOKENS:
        # Persona demo accounts get no saved search: scheduled scouting for every account would
        # spend the free-tier model budget in minutes. Each user adds searches in Settings.
        await svc.create_user(f"u-{persona.replace('_', '-')}", f"{persona}@gigbid.dev", persona.replace("_", " ").title(),
                              reviewer_pw, persona, saved_search=False)


def create_app(services: Services | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if services is not None:
            app.state.services = services
            yield
            return
        from redis.asyncio import Redis

        from agent.runtime import Runtime
        from worker.queue import ArqQueue, RedisEvents

        db = await Db().open()
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        from arq import create_pool
        from arq.connections import RedisSettings

        arq_pool = await create_pool(RedisSettings.from_dsn(redis_url))
        async with Runtime() as runtime:
            svc = Services(db=db, runtime=runtime, queue=ArqQueue(arq_pool), events=RedisEvents(Redis.from_url(redis_url)))
            await seed(svc)
            app.state.services = svc
            yield
        await arq_pool.aclose()
        await db.close()

    app = FastAPI(title="GigBid API", version="1.0", lifespan=lifespan,
                  description="GigBid: a multi-agent freelancer copilot. Nothing is sent without human approval.")
    if services is not None:   # tests inject services directly (ASGI test transports skip lifespan)
        app.state.services = services
    app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("WEB_ORIGINS", "http://localhost:3000").split(","),
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["X-Trace-Id", "X-Session-Token"])

    @app.middleware("http")
    async def trace(request: Request, call_next):
        request.state.trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        return response

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "service": "gigbid-api"}

    from apps.api.routers import (
        analytics,
        approvals,
        auth,
        jobs,
        messages,
        proposals,
        runs,
        settings,
    )

    for r in (auth.router, jobs.router, approvals.router, runs.router, proposals.router, messages.router,
              analytics.router, settings.router):
        app.include_router(r)
    return app
