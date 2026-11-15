"""GigSim HTTP API. Run: uvicorn gigsim.app:create_app --factory --port 8100

No `from __future__ import annotations` here: FastAPI must evaluate the Annotated
dependency aliases defined inside create_app().
"""

import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gigsim.config import load_config, resolve
from gigsim.engine import Engine, SimError
from gigsim.middleware import Faults, RateLimiter, error_body, idempotent, install
from gigsim.store import Store
from gigsim.world import World


class DraftIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1, max_length=5000)
    bid_amount: float = Field(gt=0)
    screening_answers: list[str] = Field(default_factory=list)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class FaultsIn(BaseModel):
    error_rate: float | None = Field(default=None, ge=0, le=1)
    latency_ms: tuple[int, int] | None = None
    down: bool | None = None


class ReleaseAllIn(BaseModel):
    on: bool = True


def create_app(overrides: dict | None = None) -> FastAPI:
    cfg = load_config(overrides)
    world = World.load(cfg)
    store = Store(resolve(cfg["db_path"]))
    engine = Engine(cfg, world, store)
    faults = Faults(cfg["faults"])
    limiter = RateLimiter(cfg["rate_limit"])

    app = FastAPI(title="GigSim", version="1.0",
                  description="Marketplace simulator for GigBid (AI-4016). Synthetic and real-derived data.")
    app.state.engine, app.state.faults, app.state.cfg = engine, faults, cfg
    install(app, faults, limiter)

    @app.exception_handler(SimError)
    async def sim_error(_: Request, e: SimError):
        return JSONResponse(error_body(e.code, e.detail, e.extra), status_code=e.status)

    def account(authorization: Annotated[str | None, Header()] = None) -> dict:
        return engine.account((authorization or "").removeprefix("Bearer ").strip())

    Acc = Annotated[dict, Depends(account)]
    IdemKey = Annotated[str | None, Header(alias="Idempotency-Key")]

    def admin(authorization: Annotated[str | None, Header()] = None) -> None:
        if not cfg["admin_enabled"]:
            raise SimError(404, "not_found", "Admin routes are disabled")
        if (authorization or "").removeprefix("Bearer ").strip() != cfg["admin_token"]:
            raise SimError(401, "unauthorized", "Admin token required")

    Admin = Depends(admin)

    @app.get("/health")
    def health():
        return {"ok": True, "pack": cfg["pack"], "policy": world.policy["version"]}

    @app.get("/me")
    def me(acc: Acc):
        return engine.me(acc)

    @app.get("/jobs")
    def search_jobs(acc: Acc, q: str | None = None, category: str | None = None,
                    skills: Annotated[list[str] | None, Query()] = None,
                    min_budget: float | None = None, since: str | None = None,
                    cursor: int = 0, limit: int = Query(20, ge=1, le=100)):
        return engine.search_jobs(q, category, skills or [], min_budget, since, cursor, limit)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, acc: Acc):
        return engine.get_job(job_id)

    @app.get("/clients/{client_id}")
    def get_client(client_id: str, acc: Acc):
        return engine.get_client(client_id)

    @app.get("/market/stats")
    def market_stats(acc: Acc, category: str | None = None):
        groups = world.market_stats["groups"]
        if category:
            if category not in groups:
                raise SimError(404, "unknown_category", f"No stats for {category}")
            return {"category": category, **groups[category], "filter": world.market_stats["filter"]}
        return world.market_stats

    @app.get("/market/history")
    def market_history(acc: Acc, category: str | None = None, cursor: int = 0,
                       limit: int = Query(100, ge=1, le=500)):
        rows = [r for r in world.market_history if category is None or r["category"] == category]
        return {"contracts": rows[cursor:cursor + limit], "total": len(rows),
                "next_cursor": str(cursor + limit) if cursor + limit < len(rows) else None}

    @app.get("/connects")
    def connects(acc: Acc):
        return engine.connects(acc["freelancer_id"])

    @app.get("/policy")
    def get_policy(acc: Acc):
        return world.policy

    @app.post("/proposals", status_code=201)
    def create_draft(body: DraftIn, acc: Acc, key: IdemKey = None):
        fid = acc["freelancer_id"]
        return idempotent(engine.store, fid, key, {"route": "draft", **body.model_dump()},
                          lambda: engine.upsert_draft(fid, body.job_id, body.cover_letter,
                                                      body.bid_amount, body.screening_answers), 201)

    @app.post("/proposals/{proposal_id}/submit")
    def submit(proposal_id: str, acc: Acc, key: IdemKey = None, dry_run: bool = False):
        fid = acc["freelancer_id"]
        if dry_run:  # previews change nothing, so they need no key
            return engine.submit(fid, proposal_id, dry_run=True)
        return idempotent(engine.store, fid, key, {"route": "submit", "proposal_id": proposal_id},
                          lambda: engine.submit(fid, proposal_id, dry_run=False))

    @app.get("/proposals")
    def list_proposals(acc: Acc, status: str | None = None):
        return {"proposals": engine.list_proposals(acc["freelancer_id"], status)}

    @app.get("/proposals/{proposal_id}")
    def get_proposal(proposal_id: str, acc: Acc):
        return engine.get_proposal(acc["freelancer_id"], proposal_id)

    @app.get("/threads")
    def list_threads(acc: Acc):
        return {"threads": engine.list_threads(acc["freelancer_id"])}

    @app.get("/threads/{thread_id}")
    def get_thread(thread_id: str, acc: Acc):
        return engine.get_thread(acc["freelancer_id"], thread_id)

    @app.post("/threads/{thread_id}/messages")
    def post_message(thread_id: str, body: MessageIn, acc: Acc, key: IdemKey = None):
        fid = acc["freelancer_id"]
        return idempotent(engine.store, fid, key, {"route": "message", "thread_id": thread_id, **body.model_dump()},
                          lambda: engine.post_message(fid, thread_id, body.body))

    # --- admin (tests, evals, viva demos) -------------------------------------------------

    @app.post("/admin/release_all", dependencies=[Admin])
    def release_all(body: ReleaseAllIn):
        """Eval mode: every job visible and clients answer instantly."""
        engine.store.set_meta("eval_mode", body.on)
        return {"eval_mode": body.on}

    @app.post("/admin/faults", dependencies=[Admin])
    def set_faults(body: FaultsIn):
        if body.error_rate is not None:
            faults.error_rate = body.error_rate
        if body.latency_ms is not None:
            faults.latency_ms = list(body.latency_ms)
        if body.down is not None:
            faults.down = body.down
        return faults.as_dict()

    @app.post("/admin/reset", dependencies=[Admin])
    def reset():
        engine.store.reset()
        engine.store.set_meta("start_wall", time.time())
        return {"reset": True}

    @app.get("/admin/proposals/{proposal_id}", dependencies=[Admin])
    def admin_proposal(proposal_id: str):
        return engine.admin_proposal(proposal_id)

    return app
