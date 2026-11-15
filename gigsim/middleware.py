"""Cross-cutting HTTP behaviour: trace ids, injected faults, rate limits, idempotency."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from gigsim.engine import SimError
from gigsim.store import Store

UNGUARDED = ("/health", "/admin", "/docs", "/openapi.json")


def error_body(code: str, detail: str, extra: dict | None = None) -> dict:
    return {"error": {"code": code, "detail": detail, **(extra or {})}}


class Faults:
    """Random 500/503s, latency and a full outage switch. Changed at runtime via /admin/faults."""

    def __init__(self, cfg: dict):
        self.error_rate = cfg["error_rate"]
        self.latency_ms = list(cfg["latency_ms"])
        self.down = False
        self.rng = random.Random(cfg["seed"])

    def as_dict(self) -> dict:
        return {"error_rate": self.error_rate, "latency_ms": self.latency_ms, "down": self.down}


class RateLimiter:
    """Sliding one-minute window per token, with a stricter bucket for real submits."""

    def __init__(self, cfg: dict):
        self.limits = {"all": cfg["requests_per_minute"], "submit": cfg["submits_per_minute"]}
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)

    def check(self, token: str, bucket: str) -> float | None:
        """Record a hit; return seconds to wait if over the limit."""
        now = time.monotonic()
        q = self.hits[(token, bucket)]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= self.limits[bucket]:
            return 60 - (now - q[0])
        q.append(now)
        return None


def install(app, faults: Faults, limiter: RateLimiter) -> None:
    @app.middleware("http")
    async def gigsim_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        path = request.url.path

        def done(resp):
            resp.headers["X-Trace-Id"] = trace_id
            return resp

        if path.startswith(UNGUARDED) or path == "/":
            return done(await call_next(request))

        if faults.down:
            return done(JSONResponse(error_body("unavailable", "Marketplace is down"), status_code=503))

        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        wait = limiter.check(token, "all")
        is_submit = path.endswith("/submit") and request.query_params.get("dry_run") not in ("true", "1")
        if wait is None and is_submit:
            wait = limiter.check(token, "submit")
        if wait is not None:
            resp = JSONResponse(error_body("rate_limited", "Too many requests"), status_code=429)
            resp.headers["Retry-After"] = str(max(1, round(wait)))
            return done(resp)

        lo, hi = faults.latency_ms
        await asyncio.sleep(faults.rng.uniform(lo, hi) / 1000)
        if faults.rng.random() < faults.error_rate:
            if faults.rng.random() < 0.5:
                # Fails before doing anything.
                return done(JSONResponse(error_body("unavailable", "Temporary error"), status_code=503))
            # Does the work, then loses the response - the case idempotency keys exist for.
            await call_next(request)
            return done(JSONResponse(error_body("internal", "Internal error"), status_code=500))
        return done(await call_next(request))


def idempotent(store: Store, fid: str, key: str | None, payload: dict, fn: Callable[[], dict],
               status_code: int = 200) -> JSONResponse:
    """Run a write once per (freelancer, Idempotency-Key). Replays return the stored response."""
    if not key:
        return JSONResponse(error_body("idempotency_key_required",
                                       "Writes need an Idempotency-Key header"), status_code=400)
    req_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with store.lock:
        row = store.one("SELECT request_hash, status_code, body FROM idempotency "
                        "WHERE freelancer_id = ? AND key = ?", (fid, key))
        if row:
            if row["request_hash"] != req_hash:
                return JSONResponse(error_body("idempotency_key_reused",
                                               "This key was used for a different request"), status_code=422)
            resp = JSONResponse(json.loads(row["body"]), status_code=row["status_code"])
            resp.headers["Idempotent-Replay"] = "true"
            return resp
        try:
            body, code = fn(), status_code
        except SimError as e:
            body, code = error_body(e.code, e.detail, e.extra), e.status
        store.run("INSERT INTO idempotency(freelancer_id, key, request_hash, status_code, body) "
                  "VALUES (?, ?, ?, ?, ?)", (fid, key, req_hash, code, json.dumps(body)))
    return JSONResponse(body, status_code=code)
