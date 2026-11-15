"""Settings, saved searches, the memory viewer, and marketplace health (for the degraded banner)."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException

from agent.llm import config as agent_config
from agent.memory.store import forget, outcome_stats
from apps.api.deps import Services, TraceId, User
from apps.api.schemas import SavedSearch, SavedSearchIn, SettingsIn

router = APIRouter(tags=["settings"])
LIVE_MIN_INTERVAL = 60


@router.get("/settings")
async def get_settings(user: User) -> dict:
    return user["settings"]


@router.put("/settings")
async def put_settings(body: SettingsIn, user: User, svc: Services) -> dict:
    merged = {**user["settings"], **body.model_dump(exclude_none=True)}
    await svc.db.run("UPDATE users SET settings = %s WHERE user_id = %s", json.dumps(merged), user["user_id"])
    return merged


@router.get("/settings/searches", response_model=list[SavedSearch])
async def list_searches(user: User, svc: Services):
    rows = await svc.db.all("SELECT * FROM saved_searches WHERE user_id = %s", user["user_id"])
    return [SavedSearch(search_id=r["search_id"], every_minutes=r["every_minutes"],
                        last_run_at=r["last_run_at"].isoformat() if r["last_run_at"] else None, **r["query"]) for r in rows]


@router.post("/settings/searches", response_model=SavedSearch, status_code=201)
async def add_search(body: SavedSearchIn, user: User, svc: Services):
    sid = f"s-{uuid.uuid4().hex[:10]}"
    query = body.model_dump(exclude={"every_minutes"}, exclude_none=True)
    every = body.every_minutes
    if agent_config()["marketplace"]["mode"] == "upwork_live":
        every = max(every, LIVE_MIN_INTERVAL)   # never poll live Upwork more often than hourly (RUNBOOK)
    await svc.db.run("INSERT INTO saved_searches (search_id, user_id, query, every_minutes) VALUES (%s,%s,%s,%s)",
                     sid, user["user_id"], json.dumps(query), every)
    return SavedSearch(search_id=sid, last_run_at=None, **{**body.model_dump(), "every_minutes": every})


@router.delete("/settings/searches/{search_id}", status_code=204)
async def delete_search(search_id: str, user: User, svc: Services):
    await svc.db.run("DELETE FROM saved_searches WHERE search_id = %s AND user_id = %s", search_id, user["user_id"])


@router.get("/memory")
async def memory(user: User, svc: Services) -> dict:
    store, uid = svc.runtime.store, user["user_id"]
    return {"style_rules": [{"key": i.key, **i.value} for i in store.search(("style", uid), limit=100)],
            "style_candidates": [{"key": i.key, **i.value} for i in store.search(("style_candidates", uid), limit=100)],
            "outcomes": outcome_stats(store, uid)}


@router.delete("/memory/{namespace}/{key}", status_code=204)
async def delete_memory(namespace: str, key: str, user: User, svc: Services):
    if namespace not in ("style", "style_candidates", "outcome"):
        raise HTTPException(404, "Unknown memory namespace")
    forget(svc.runtime.store, user["user_id"], namespace, key)


@router.get("/health/marketplace")
async def marketplace_health(user: User, svc: Services, trace_id: TraceId) -> dict:
    try:
        bal = await svc.marketplace(user, "get_connects_balance", {}, trace_id)
        return {"marketplace": "ok", "connects_balance": bal["balance"]}
    except Exception as exc:  # noqa: BLE001 - any failure means degraded mode for the UI
        return {"marketplace": "unavailable", "detail": str(exc)[:200]}
