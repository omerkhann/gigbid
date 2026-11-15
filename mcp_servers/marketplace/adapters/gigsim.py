"""GigSim adapter: HTTP calls to the GigSim REST API with bounded retries.

- 429: wait for Retry-After (capped), then retry.
- 5xx / connection errors: exponential backoff, then retry.
- Writes are retried with the SAME Idempotency-Key, so a retry after a lost response is safe.
- After the retry budget, raise MarketplaceUnavailable so GigBid can show degraded mode.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from mcp_servers.marketplace.adapters.base import MarketplaceError, MarketplaceUnavailable


class GigSimBackend:
    def __init__(self, base_url: str, client: httpx.AsyncClient | None = None, retries: int = 3,
                 backoff: float = 0.5, max_wait: float = 10.0, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self.retries, self.backoff, self.max_wait = retries, backoff, max_wait

    async def _req(self, method: str, path: str, cred: str, trace: str, *, params: dict | None = None,
                   body: dict | None = None, key: str | None = None) -> Any:
        headers = {"Authorization": f"Bearer {cred}", "X-Trace-Id": trace}
        if key:
            headers["Idempotency-Key"] = key
        params = {k: v for k, v in (params or {}).items() if v is not None and v != []}
        last = "no attempt made"
        for attempt in range(self.retries + 1):
            try:
                r = await self.client.request(method, path, params=params, json=body, headers=headers)
            except httpx.TransportError as exc:
                last = f"connection error: {exc.__class__.__name__}"
            else:
                if r.status_code < 400:
                    return r.json()
                if r.status_code == 429:
                    last = "rate limited by the marketplace"
                    await asyncio.sleep(min(float(r.headers.get("Retry-After", 1)), self.max_wait))
                    continue
                if r.status_code >= 500:
                    last = f"marketplace error {r.status_code}"
                else:
                    err = (r.json() if r.headers.get("content-type", "").startswith("application/json")
                           else {}).get("error", {})
                    extra = {k: v for k, v in err.items() if k not in ("code", "detail")}
                    raise MarketplaceError(err.get("code", f"http_{r.status_code}"),
                                           err.get("detail", r.text[:200]), r.status_code, extra)
            if attempt < self.retries:
                await asyncio.sleep(self.backoff * 2**attempt)
        raise MarketplaceUnavailable(f"{last} (after {self.retries + 1} attempts)")

    # --- reads ---------------------------------------------------------------------------

    async def search_jobs(self, cred, trace, **filters):
        return await self._req("GET", "/jobs", cred, trace, params=filters)

    async def get_job(self, cred, trace, job_id):
        return await self._req("GET", f"/jobs/{job_id}", cred, trace)

    async def get_client(self, cred, trace, client_id):
        return await self._req("GET", f"/clients/{client_id}", cred, trace)

    async def get_connects(self, cred, trace):
        return await self._req("GET", "/connects", cred, trace)

    async def get_market_stats(self, cred, trace, category):
        return await self._req("GET", "/market/stats", cred, trace, params={"category": category})

    async def get_policy(self, cred, trace):
        return await self._req("GET", "/policy", cred, trace)

    async def list_proposals(self, cred, trace, status):
        return await self._req("GET", "/proposals", cred, trace, params={"status": status})

    async def list_threads(self, cred, trace):
        return await self._req("GET", "/threads", cred, trace)

    async def get_thread(self, cred, trace, thread_id):
        return await self._req("GET", f"/threads/{thread_id}", cred, trace)

    # --- writes --------------------------------------------------------------------------

    async def create_draft(self, cred, trace, key, job_id, cover_letter, bid_amount, screening_answers):
        body = {"job_id": job_id, "cover_letter": cover_letter, "bid_amount": bid_amount,
                "screening_answers": screening_answers}
        return await self._req("POST", "/proposals", cred, trace, body=body, key=key)

    async def submit(self, cred, trace, key, proposal_id, dry_run):
        return await self._req("POST", f"/proposals/{proposal_id}/submit", cred, trace,
                               params={"dry_run": "true" if dry_run else None}, key=None if dry_run else key)

    async def send_message(self, cred, trace, key, thread_id, body):
        return await self._req("POST", f"/threads/{thread_id}/messages", cred, trace, body={"body": body}, key=key)
