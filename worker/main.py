"""Arq worker. Run: python -m worker.main   (needs Redis, Postgres and the MCP servers)

Schedules (assignment E1, justified in docs/RUNBOOK.md):
- every minute: run Scout for users whose saved searches are due (each search has its own interval;
  GigSim default 60 min, live Upwork mode is never more often than every 60 min);
- every 5 minutes: poll proposal outcomes and new client messages.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings
from dotenv import load_dotenv

from apps.api.db import Db
from worker import tasks
from worker.queue import ArqQueue, RedisEvents

if sys.platform == "win32":   # psycopg's async mode needs the selector event loop on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def startup(ctx: dict) -> None:
    from agent.runtime import Runtime

    ctx["db"] = await Db().open()
    ctx["runtime"] = await Runtime().__aenter__()
    ctx["events"] = RedisEvents(ctx["redis"])
    ctx["queue"] = ArqQueue(ctx["redis"])


async def shutdown(ctx: dict) -> None:
    await ctx["runtime"].__aexit__(None, None, None)
    await ctx["db"].close()


async def scout_due_users(ctx: dict) -> dict:
    users = await ctx["db"].all("SELECT DISTINCT user_id FROM saved_searches")
    for u in users:
        await ctx["queue"].enqueue("scout", user_id=u["user_id"], job_key=f"scout:{u['user_id']}")
    return {"users": len(users)}


async def poll_all_users(ctx: dict) -> dict:
    users = await ctx["db"].all("SELECT user_id FROM users WHERE persona IS NOT NULL")
    for u in users:
        await ctx["queue"].enqueue("poll_outcomes", user_id=u["user_id"], job_key=f"poll:{u['user_id']}")
    return {"users": len(users)}


class WorkerSettings:
    functions: ClassVar[list] = list(tasks.TASKS.values())
    cron_jobs: ClassVar[list] = [cron(scout_due_users, second=0, run_at_startup=False),
                 cron(poll_all_users, minute=set(range(0, 60, 5)), second=30)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    max_jobs = 4
    job_timeout = 900
    max_tries = 3            # a crashed or failed task is retried; checkpoints + idempotency keep it safe
    keep_result = 3600


if __name__ == "__main__":
    from arq import run_worker

    run_worker(WorkerSettings)
