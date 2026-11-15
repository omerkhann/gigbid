"""Task queue and event bus.

ArqQueue + RedisEvents in production (Redis). InlineQueue + MemoryEvents for tests and single-process
dev: tasks run immediately in the same process, events go to in-memory subscribers.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any


class ArqQueue:
    def __init__(self, pool):
        self.pool = pool

    async def enqueue(self, task: str, job_key: str | None = None, **kwargs) -> str | None:
        job = await self.pool.enqueue_job(task, _job_id=job_key, **kwargs)
        return job.job_id if job else None      # None: a job with this key is already queued or running


class InlineQueue:
    def __init__(self):
        self.ctx: dict[str, Any] = {}
        self.done: list[tuple[str, dict, Any]] = []
        self._keys: set[str] = set()

    async def enqueue(self, task: str, job_key: str | None = None, **kwargs) -> str | None:
        from worker.tasks import TASKS

        if job_key and job_key in self._keys:
            return None
        if job_key:
            self._keys.add(job_key)
        result = await TASKS[task](self.ctx, **kwargs)
        self.done.append((task, kwargs, result))
        return job_key or task


class RedisEvents:
    def __init__(self, redis):
        self.redis = redis

    async def publish(self, user_id: str, event: dict) -> None:
        await self.redis.publish(f"events:{user_id}", json.dumps(event, default=str))

    async def subscribe(self, user_id: str):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(f"events:{user_id}")
        try:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield json.loads(msg["data"])
        finally:
            await pubsub.unsubscribe(f"events:{user_id}")
            await pubsub.aclose()


class MemoryEvents:
    def __init__(self):
        self.history: dict[str, list[dict]] = defaultdict(list)
        self.queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, user_id: str, event: dict) -> None:
        self.history[user_id].append(event)
        for q in self.queues[user_id]:
            q.put_nowait(event)

    async def subscribe(self, user_id: str):
        q: asyncio.Queue = asyncio.Queue()
        self.queues[user_id].append(q)
        try:
            while True:
                yield await q.get()
        finally:
            self.queues[user_id].remove(q)
