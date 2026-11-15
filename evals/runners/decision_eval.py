"""Decision evaluation (assignment B4): bid-or-skip F1, scam precision and recall, injection flagging,
price inside the fair band, and latency/tokens per job analysed.

  python -m evals.runners.decision_eval                 # real models on the fixed 60-job subset
  python -m evals.runners.decision_eval --limit 5       # quick check

Runs the real bid graph (GigSim and MCP servers in-process, real LLMs from agent/config.yaml) and
stops before pricing (interrupt_before), so no proposals are written. The fixed subset is
evals/datasets/dev/subset_60.json: 20 jobs per persona, stratified, chosen once by seed.
Writes evals/results/decision_eval.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SUBSET = ROOT / "evals/datasets/dev/subset_60.json"
PERSONAS = ("ml_engineer", "fullstack_dev", "data_analyst")
SHARES = {"bid": 8, "skip": 7, "scam": 3, "injection": 2}


def labels() -> list[dict]:
    return [json.loads(line) for line in (ROOT / "evals/datasets/dev/labels.jsonl").open(encoding="utf-8")]


def build_subset(seed: int = 7) -> dict:
    """20 jobs per persona: bid-worthy, plain skips, scams, injected-but-biddable. Fixed once, committed."""
    rng = random.Random(seed)
    out = {}
    for p in PERSONAS:
        rows = [r for r in labels() if r["persona"] == p]
        pools = {"bid": [r for r in rows if r["bid"] and not r["injection"]],
                 "skip": [r for r in rows if not r["bid"] and not r["scam"] and not r["injection"]],
                 "scam": [r for r in rows if r["scam"]],
                 "injection": [r for r in rows if r["injection"]]}
        picked = []
        for k, n in SHARES.items():
            picked += rng.sample(pools[k], min(n, len(pools[k])))
        out[p] = [r["job_id"] for r in picked]
    return out


def subset() -> dict:
    if not SUBSET.exists():
        SUBSET.write_text(json.dumps(build_subset(), indent=2) + "\n", encoding="utf-8", newline="\n")
    return json.loads(SUBSET.read_text(encoding="utf-8"))


def stratified(job_ids: list[str], persona: str, gold: dict, limit: int | None) -> list[str]:
    """The first `limit` jobs taking kinds in turn (bid, skip, scam, injection), so a small run still
    contains every kind; the whole list when limit is None."""
    if not limit:
        return job_ids

    def kind(j):
        g = gold[(j, persona)]
        return "injection" if g["injection"] else "scam" if g["scam"] else "bid" if g["bid"] else "skip"
    queues = {k: [j for j in job_ids if kind(j) == k] for k in SHARES}
    out = []
    while len(out) < limit and any(queues.values()):
        for k in SHARES:
            if queues[k] and len(out) < limit:
                out.append(queues[k].pop(0))
    return out


def f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0.0


async def run(limit: int | None, out_path: Path | None = None) -> dict:
    from langgraph.checkpoint.memory import InMemorySaver
    from mcp.shared.memory import create_connected_server_and_client_session as connect

    from agent.graphs.bid_graph import build_bid_graph, start_input
    from agent.llm import config as agent_config
    from agent.mcp_client import McpGateway
    from agent.nodes.common import Deps
    from agent.nodes.pricing import quote
    from agent.runtime import user_profile
    from gigsim.app import create_app as create_gigsim
    from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
    from mcp_servers.marketplace.server import Settings as MSettings
    from mcp_servers.marketplace.server import build_server as build_marketplace
    from mcp_servers.portfolio.server import Settings as PSettings
    from mcp_servers.portfolio.server import build_server as build_portfolio
    from mcp_servers.portfolio.server import shipped_variant

    tmp = Path(tempfile.mkdtemp(prefix="gigbid-deval-"))
    sim = create_gigsim({"db_path": str(tmp / "g.sqlite3"), "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                         "rate_limit": {"requests_per_minute": 10**6, "submits_per_minute": 10**6}})
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
    await http.post("/admin/release_all", json={"on": True}, headers={"Authorization": "Bearer dev-admin"})
    gold = {(r["job_id"], r["persona"]): r for r in labels()}
    jobs = {j["job_id"]: j for j in map(json.loads, (ROOT / "gigsim/scenarios/dev/jobs.jsonl").open(encoding="utf-8"))}
    stats = json.loads((ROOT / "gigsim/scenarios/market/stats.json").read_text(encoding="utf-8"))["groups"]
    cfg = agent_config()
    rows = []

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    for persona, job_ids in subset().items():
        slug = persona.replace("_", "-")
        market = build_marketplace(MSettings(db_path=tmp / f"m-{persona}.sqlite3", local_user=f"u-{slug}",
                                             limits={"read": 10**6, "submit": 10**6, "write": 10**6}),
                                   GigSimBackend("http://gigsim", client=http))
        portfolio = build_portfolio(PSettings(db_path=tmp / f"p-{persona}.sqlite3", local_user=f"u-{slug}",
                                              variant=os.environ.get("PORTFOLIO_VARIANT") or shipped_variant(),
                                              embedder=os.environ.get("PORTFOLIO_EMBEDDER", "ollama:nomic-embed-text")))
        gateway = McpGateway({"marketplace": factory(market), "portfolio": factory(portfolio)})
        graph = build_bid_graph(InMemorySaver())
        graph.interrupt_before_nodes = ["pricing"]   # stop before any drafting: decisions only
        user = user_profile({"user_id": f"u-{slug}", "persona": persona, "settings": {}})
        sk = __import__("yaml").safe_load((ROOT / f"data/personas/{persona}/skeleton.yaml").read_text(encoding="utf-8"))
        user.update(hourly_floor=sk["rate_floor_hourly"], fixed_floor=sk["min_fixed_budget"], hourly_rate=sk["hourly_rate"])
        for job_id in stratified(job_ids, persona, gold, limit):
            job = {k: v for k, v in jobs[job_id].items() if k not in ("source", "release_offset_h")}
            g = gold[(job_id, persona)]
            t = time.time()
            out = await graph.ainvoke(start_input(user, job), {"configurable": {
                "thread_id": f"deval:{persona}:{job_id}", "deps": Deps(gateway=gateway)}})
            action = (out.get("decision") or {}).get("action") or ("error" if out.get("status") == "dead_letter" else "skip")
            risk = out.get("risk_report") or {}
            band = g["fair_price_band"]
            group = stats.get(job.get("category"), stats["all"])
            q = quote(job, {"hourly_rate": group["hourly"]["hourly_rate"], "fixed_total_paid": group["fixed"]["total_paid"]},
                      user, 80, (out.get("fit_report") or {}).get("score", 0.5), cfg["thresholds"]["min_connects_reserve"])
            rows.append({"persona": persona, "job_id": job_id, "gold_bid": g["bid"], "gold_skip_reason": g["skip_reason"],
                         "pred": action, "gold_scam": g["scam"], "risk": risk.get("score"), "flags": risk.get("flags", []),
                         "gold_injection": g["injection"], "fit": (out.get("fit_report") or {}).get("score"),
                         "price": q.amount, "band": [band["min"], band["max"]],
                         "price_in_band": band["min"] * 0.999 <= q.amount <= band["max"] * 1.001,
                         "tokens": out.get("tokens") or 0, "seconds": round(time.time() - t, 2),
                         "status": out.get("status"), "errors": out.get("errors") or []})
            print(json.dumps({k: rows[-1][k] for k in ("persona", "job_id", "gold_bid", "pred", "gold_scam", "risk",
                                                        "fit", "seconds")}), flush=True)
    return summarise(rows, out_path)


def summarise(rows: list[dict], out_path: Path | None = None) -> dict:
    def block(rs: list[dict]) -> dict:
        ok = [r for r in rs if r["pred"] != "error"]
        tp = sum(r["gold_bid"] and r["pred"] == "bid" for r in ok)
        fp = sum(not r["gold_bid"] and r["pred"] == "bid" for r in ok)
        fn = sum(r["gold_bid"] and r["pred"] != "bid" for r in ok)
        bp, br, bf = f1(tp, fp, fn)
        stp = sum(r["gold_scam"] and (r["risk"] or 0) > 0.7 for r in ok)
        sfp = sum(not r["gold_scam"] and (r["risk"] or 0) > 0.7 for r in ok)
        sfn = sum(r["gold_scam"] and (r["risk"] or 0) <= 0.7 for r in ok)
        sp, sr, sf = f1(stp, sfp, sfn)
        inj = [r for r in ok if r["gold_injection"]]
        priced = [r for r in ok if r["gold_bid"]]
        secs = sorted(r["seconds"] for r in ok)
        return {"jobs": len(rs), "errors": len(rs) - len(ok),
                "bid_precision": bp, "bid_recall": br, "bid_f1": bf,
                "scam_precision": sp, "scam_recall": sr, "scam_f1": sf,
                "injection_flagged": round(sum("prompt_injection" in r["flags"] for r in inj) / len(inj), 3) if inj else None,
                "price_in_band": round(sum(r["price_in_band"] for r in priced) / len(priced), 3) if priced else None,
                "latency_p50_s": statistics.median(secs) if secs else None,
                "latency_p95_s": secs[int(0.95 * (len(secs) - 1))] if secs else None,
                "tokens_per_job": round(statistics.mean(r["tokens"] for r in ok)) if ok else None}

    from agent.llm import chain_for, profile

    out = {"profile": profile(), "small_model": chain_for("job_analyst")[0], "overall": block(rows),
           "by_persona": {p: block([r for r in rows if r["persona"] == p]) for p in PERSONAS}, "rows": rows}
    path = out_path or ROOT / f"evals/results/decision_eval_{profile()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"profile": out["profile"], **out["overall"]}, indent=2))
    return out


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="jobs per persona")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if sys.platform == "win32":
        asyncio.run(run(a.limit, a.out), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(run(a.limit, a.out))
