"""Run one job through the bid graph with real models, real MCP servers and the Postgres checkpointer.

Needs running: Postgres (docker compose), GigSim (:8100), Marketplace MCP (:8201), Portfolio MCP (:8203).

  python -m agent.run_bid --persona data_analyst --job job-0b954e1ba14e      # runs until approval
  python -m agent.run_bid --persona data_analyst --job job-0b954e1ba14e --resume approve
  python -m agent.run_bid ... --resume reject --reason "not my niche"

The thread id is bid:<user>:<job>, so resuming (even after killing this process) continues the same
checkpointed thread.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langgraph.types import Command

ROOT = Path(__file__).resolve().parents[1]


def user_for(persona: str) -> dict:
    import yaml

    sk = yaml.safe_load((ROOT / f"data/personas/{persona}/skeleton.yaml").read_text(encoding="utf-8"))
    return {"user_id": f"u-{persona.replace('_', '-')}", "persona": persona,
            "portfolio_dir": str(ROOT / f"data/personas/{persona}"), "hourly_floor": sk["rate_floor_hourly"],
            "fixed_floor": sk["min_fixed_budget"], "hourly_rate": sk["hourly_rate"]}


async def main(args) -> None:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    from agent.graphs.bid_graph import build_bid_graph, start_input
    from agent.mcp_client import McpGateway, http_session_factory
    from agent.nodes.common import Deps

    slug = args.persona.replace("_", "-")
    gateway = McpGateway({
        "marketplace": http_session_factory(os.environ.get("MARKETPLACE_MCP_URL", "http://127.0.0.1:8201/mcp"),
                                            f"dev-mcp-{slug}"),
        "portfolio": http_session_factory(os.environ.get("PORTFOLIO_MCP_URL", "http://127.0.0.1:8203/mcp"),
                                          f"dev-pf-{slug}"),
    })
    user = user_for(args.persona)
    thread = f"bid:{user['user_id']}:{args.job}"
    cfg = {"configurable": {"thread_id": thread, "deps": Deps(gateway=gateway)}}

    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as saver:
        await saver.setup()
        graph = build_bid_graph(saver)
        if args.show:   # read the checkpoint; runs nothing
            snap = await graph.aget_state(cfg)
            out = {**snap.values, "__interrupt__": list(snap.interrupts)} if snap.interrupts else dict(snap.values)
        elif args.resume:
            decision = {"action": args.resume, "reason": args.reason}
            out = await graph.ainvoke(Command(resume=decision), cfg)
        else:
            job = await gateway.call("scout", "marketplace", "get_job", {"job_id": args.job}, thread)
            out = await graph.ainvoke(start_input(user, job), cfg)

    print(f"thread {thread}")
    for e in out.get("events", []):
        print(f"  {e['node']:<14} {e.get('ms', 0):>6} ms  {e.get('tokens', 0):>6} tok  {e['summary']}")
    if "__interrupt__" in out:
        p = out["__interrupt__"][0].value
        print("\nWAITING FOR APPROVAL")
        print(f"  risk {p['risk']['score']} {p['risk']['flags']} | fit {p['fit']['score']} | "
              f"price {p['price']['amount']} {p['price']['unit']} | costs {p['preview']['connects_cost']} Connects")
        print("\n--- cover letter (as the client will see it) ---\n" + p["preview"]["cover_letter"])
        for i, a in enumerate(p["preview"]["screening_answers"], 1):
            print(f"\nQ{i}: {a}")
    else:
        print(f"\nSTATUS {out.get('status')}: {out.get('status_reason', '')}")
        if out.get("submission"):
            print(json.dumps({k: out["submission"][k] for k in ("status", "connects_cost", "balance_after")}))
    print(f"\nsteps {out.get('steps')} | tokens {out.get('tokens')} | errors {out.get('errors', [])}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona", required=True)
    ap.add_argument("--job", required=True)
    ap.add_argument("--resume", choices=["approve", "reject"])
    ap.add_argument("--reason")
    ap.add_argument("--show", action="store_true", help="print the thread's saved state; run nothing")
    a = ap.parse_args()
    if sys.platform == "win32":   # psycopg's async mode needs the selector event loop on Windows
        asyncio.run(main(a), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main(a))
