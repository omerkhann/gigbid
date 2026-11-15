"""Proposal and outcome evaluation (assignment B4): GigSim reply and hire rate on a fixed job set,
unsupported claims per proposal (before and after claim verification), Critic loops, an LLM-judge
score, and latency / tokens per proposal.

  python -m evals.runners.gigsim_outcomes --variant v0_naive        # bid-worthy jobs of the fixed subset
  python -m evals.runners.gigsim_outcomes --variant v0_naive --limit 2

Full bid graph with real models, auto-approved, submitted to GigSim whose simulated client runs in
LLM mode (Qwen; a different family from the Writer). GigSim's LLM cache persists in
data/processed/gigsim_eval.sqlite3 across runs (state is reset each run, the cache is kept), so the
same proposal is never paid for twice. Writes evals/results/gigsim_outcomes_<variant>.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
ADMIN = {"Authorization": "Bearer dev-admin"}


async def run(variant: str, limit: int | None, embedder: str) -> dict:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from agent.graphs.bid_graph import build_bid_graph, start_input
    from agent.llm import profile
    from agent.mcp_client import McpGateway
    from agent.nodes.common import Deps
    from agent.runtime import user_profile
    from evals.runners.decision_eval import labels, subset
    from evals.runners.judge_calibration import judge
    from gigsim.app import create_app as create_gigsim
    from gigsim.config import load_config as gigsim_config
    from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
    from mcp_servers.marketplace.server import Settings as MSettings
    from mcp_servers.marketplace.server import build_server as build_marketplace
    from mcp_servers.portfolio.server import Settings as PSettings
    from mcp_servers.portfolio.server import build_server as build_portfolio

    tmp = Path(tempfile.mkdtemp(prefix="gigbid-outcomes-"))
    client_cfg = {**gigsim_config()["client"], "mode": "llm"}
    sim = create_gigsim({"db_path": str(ROOT / "data/processed/gigsim_eval.sqlite3"), "client": client_cfg,
                         "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                         "rate_limit": {"requests_per_minute": 10**6, "submits_per_minute": 10**6}})
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim", timeout=600)
    await http.post("/admin/reset", headers=ADMIN)                 # fresh state; the LLM cache survives
    await http.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    gold = {(r["job_id"], r["persona"]): r for r in labels()}
    jobs = {j["job_id"]: j for j in map(json.loads, (ROOT / "gigsim/scenarios/dev/jobs.jsonl").open(encoding="utf-8"))}

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    rows = []
    wanted = [p for p in os.environ.get("OUTCOME_PERSONAS", "").split(",") if p]   # time-boxed runs
    for persona, job_ids in subset().items():
        if wanted and persona not in wanted:
            continue
        slug = persona.replace("_", "-")
        market = build_marketplace(MSettings(db_path=tmp / f"m-{persona}.sqlite3", local_user=f"u-{slug}",
                                             limits={"read": 10**6, "submit": 10**6, "write": 10**6}),
                                   GigSimBackend("http://gigsim", client=http))
        portfolio = build_portfolio(PSettings(db_path=tmp / f"p-{persona}.sqlite3", local_user=f"u-{slug}",
                                              variant=variant, embedder=embedder))
        gateway = McpGateway({"marketplace": factory(market), "portfolio": factory(portfolio)})
        graph = build_bid_graph(InMemorySaver())
        user = user_profile({"user_id": f"u-{slug}", "persona": persona, "settings": {}})
        sk = __import__("yaml").safe_load((ROOT / f"data/personas/{persona}/skeleton.yaml").read_text(encoding="utf-8"))
        user.update(hourly_floor=sk["rate_floor_hourly"], fixed_floor=sk["min_fixed_budget"], hourly_rate=sk["hourly_rate"])
        bid_jobs = [j for j in job_ids if gold[(j, persona)]["bid"] and not gold[(j, persona)]["injection"]]
        for job_id in bid_jobs[:limit] if limit else bid_jobs:
            job = {k: v for k, v in jobs[job_id].items() if k not in ("source", "release_offset_h")}
            cfg = {"configurable": {"thread_id": f"out:{persona}:{job_id}", "deps": Deps(gateway=gateway)}}
            t = time.time()
            out = await graph.ainvoke(start_input(user, job), cfg)
            row = {"persona": persona, "job_id": job_id, "reached_approval": "__interrupt__" in out,
                   "decision": (out.get("decision") or {}).get("action"), "status": out.get("status")}
            if row["reached_approval"]:
                draft = out["proposal_draft"]
                secs = round(time.time() - t, 1)
                final = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
                letter = draft["cover_letter"].lower()
                # "before": unsupported claims the Writer made; "after": any of those still in the sent letter
                after = sum(c["verdict"] == "unsupported" and c["claim"].lower()[:60] in letter for c in out.get("claims", []))
                outcome = None
                if final.get("status") == "submitted":
                    adm = (await http.get(f"/admin/proposals/{out['marketplace_proposal_id']}", headers=ADMIN)).json()
                    outcome = ((adm.get("decision") or {}).get("decision"))   # ignore / reply / interview
                row.update(seconds_to_approval=secs, tokens=final.get("tokens") or out.get("tokens"),
                           unsupported_before=draft.get("unsupported_before", 0), claims=draft.get("claims_total", 0),
                           unsupported_after=after, critic_revisions=out.get("revisions", 0),
                           submitted=final.get("status") == "submitted", outcome=outcome,
                           submit_error=None if final.get("status") == "submitted" else final.get("status_reason"))
                row["judge"] = judge({"job_title": job["title"], "job_excerpt": job["description"][:600],
                                      "proposal": out["preview"]["cover_letter"]})["score"]
            rows.append(row)
            print(json.dumps(row), flush=True)

    sent = [r for r in rows if r.get("submitted")]
    secs = sorted(r["seconds_to_approval"] for r in sent)
    summary = {
        "variant": variant, "profile": profile(), "embedder": embedder, "jobs": len(rows),
        "reached_approval": sum(r["reached_approval"] for r in rows), "submitted": len(sent),
        "reply_rate": round(sum(r["outcome"] in ("reply", "interview") for r in sent) / len(sent), 3) if sent else None,
        "interview_rate": round(sum(r["outcome"] == "interview" for r in sent) / len(sent), 3) if sent else None,
        "unsupported_claims_before": round(statistics.mean(r["unsupported_before"] for r in sent), 2) if sent else None,
        "unsupported_claims_after": round(statistics.mean(r["unsupported_after"] for r in sent), 2) if sent else None,
        "judge_score": round(statistics.mean(r["judge"] for r in sent), 2) if sent else None,
        "critic_revisions_avg": round(statistics.mean(r["critic_revisions"] for r in sent), 2) if sent else None,
        "latency_p50_s": statistics.median(secs) if secs else None,
        "latency_p95_s": secs[int(0.95 * (len(secs) - 1))] if secs else None,
        "tokens_per_proposal": round(statistics.mean(r["tokens"] for r in sent)) if sent else None,
        "usd_per_proposal": 0.0, "usd_note": "open models on free tiers (Groq, local Ollama)",
    }
    (ROOT / f"evals/results/gigsim_outcomes_{variant}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None, help="default: agent/config.yaml rag.variant")
    ap.add_argument("--limit", type=int, default=None, help="bid jobs per persona")
    ap.add_argument("--embedder", default="ollama:nomic-embed-text")
    a = ap.parse_args()
    from mcp_servers.portfolio.server import shipped_variant
    coro = run(a.variant or os.environ.get("PORTFOLIO_VARIANT") or shipped_variant(), a.limit, a.embedder)
    if sys.platform == "win32":
        asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(coro)
