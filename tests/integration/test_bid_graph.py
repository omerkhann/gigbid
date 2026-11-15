"""Bid graph end to end, in-process: real GigSim, real Marketplace + Portfolio MCP servers (in-memory
transport), a deterministic fake LLM, and an in-memory checkpointer. No network, no API keys."""

from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from mcp.shared.memory import create_connected_server_and_client_session as connect

from agent.graphs.bid_graph import build_bid_graph
from agent.handoffs import (
    Claim,
    ClaimCheckLLM,
    Critique,
    CritiqueScores,
    FitLLM,
    ItemJudgement,
    JobSpecLLM,
    ProposalLLM,
    RiskLLM,
)
from agent.llm import Usage
from agent.llm import config as load_config
from agent.mcp_client import McpGateway, ToolNotAllowed
from agent.nodes.common import Deps
from gigsim.app import create_app
from mcp_servers.marketplace.adapters.gigsim import GigSimBackend
from mcp_servers.marketplace.server import Settings as MSettings
from mcp_servers.marketplace.server import build_server as build_marketplace
from mcp_servers.portfolio.server import Settings as PSettings
from mcp_servers.portfolio.server import build_server as build_portfolio
from rag.retriever import reset_cache

ROOT = Path(__file__).resolve().parents[2]
ADMIN = {"Authorization": "Bearer dev-admin"}
USER = {"user_id": "u-data-analyst", "persona": "data_analyst", "portfolio_dir": str(ROOT / "data/personas/data_analyst"),
        "hourly_floor": 18, "fixed_floor": 80, "hourly_rate": 28}


class ProcessKilled(BaseException):
    """Simulates the worker dying. A BaseException (not Exception) so the node wrapper can't catch it;
    not KeyboardInterrupt, which asyncio re-raises into the event loop."""


class FakeLLM:
    """Deterministic stand-ins for every LLM node. `writer_text` and `critic_verdicts` steer tests."""

    def __init__(self, writer_text=None, critic_verdicts=None):
        self.writer_text = writer_text
        self.critic_verdicts = list(critic_verdicts or [])
        self.calls: dict[str, int] = {}

    def __call__(self, node, schema):
        def call(messages):
            self.calls[node] = self.calls.get(node, 0) + 1
            text = "\n".join(m.content for m in messages)
            return self.answer(node, text), Usage("fake", 100, 50, 0.0, 0)
        return call

    def answer(self, node, text):
        if node == "job_analyst":
            return JobSpecLLM(deliverables=["dashboard"], requirements=["build dashboards", "SQL"], timeline=None,
                              hidden_needs=[], red_flags=[])
        if node == "risk_assessor":
            return RiskLLM(scam_signals=[], injection_attempt=False, assessment="Looks normal.")
        if node == "fit_matcher":
            items = []
            for block in text.split("Requirement ")[1:]:
                idx = int(block.split(":", 1)[0])
                ids = re.findall(r"id=(\S+)", block)[:1]
                items.append(ItemJudgement(index=idx, coverage="strong" if ids else "missing", evidence_ids=ids,
                                           reason="fake"))
            return FitLLM(items=items)
        if node == "writer":
            ev = re.findall(r"- \[([^\]]+)\]", text)
            first = ev[0] if ev else "none"
            letter = self.writer_text or (f"Your reporting needs a clear, reliable dashboard. I built a Power BI sales "
                                          f"dashboard that cut reporting from 3 days to 2 hours [{first}]. I would start "
                                          f"by agreeing the key metrics with you.")
            n_q = text.count("\n- ", text.find("Screening questions:"), text.find("\n\n", text.find("Screening questions:")))
            return ProposalLLM(cover_letter=letter, screening_answers=["A Power BI project for 40 managers."] * max(n_q, 0))
        if node == "verify_claims":
            draft = text.split("DRAFT:\n", 1)[1]
            return ClaimCheckLLM(claims=[Claim(claim="built a Power BI sales dashboard", verdict="supported")],
                                 revised_cover_letter=draft)
        if node == "critic":
            verdict = self.critic_verdicts.pop(0) if self.critic_verdicts else "pass"
            return Critique(verdict=verdict, scores=CritiqueScores(grounding=4, personalisation=4, clarity=4, length=4), issues=["be more specific"] if verdict == "revise" else [])
        raise AssertionError(node)


@pytest.fixture
def env(tmp_path):
    reset_cache()
    sim = create_app({"db_path": str(tmp_path / "gigsim.sqlite3"),
                      "faults": {"error_rate": 0.0, "latency_ms": [0, 0], "seed": 1}})
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=sim), base_url="http://gigsim")
    market = build_marketplace(MSettings(db_path=tmp_path / "m.sqlite3", local_user="u-data-analyst"),
                               GigSimBackend("http://gigsim", client=http, backoff=0.01, max_wait=0.05))
    portfolio = build_portfolio(PSettings(embedder="hash", db_path=tmp_path / "p.sqlite3",
                                          cache_root=tmp_path / "cache", local_user="u-data-analyst"))

    def factory(server):
        @asynccontextmanager
        async def open_session():
            async with connect(server) as s:
                yield s
        return open_session

    gateway = McpGateway({"marketplace": factory(market), "portfolio": factory(portfolio)})
    return {"sim": sim, "http": http, "gateway": gateway}


def labels(**match) -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "evals/datasets/dev/labels.jsonl").open(encoding="utf-8")]
    return [r for r in rows if r["persona"] == "data_analyst" and all(r.get(k) == v for k, v in match.items())]


async def job(env, job_id):
    await env["http"].post("/admin/release_all", json={"on": True}, headers=ADMIN)
    r = await env["http"].get(f"/jobs/{job_id}", headers={"Authorization": "Bearer dev-data-analyst"})
    return r.json()


def run_cfg(env, llm, thread="t1", **cfg_overrides):
    cfg = load_config()
    if cfg_overrides:
        cfg = json.loads(json.dumps(cfg))
        for k, v in cfg_overrides.items():
            cfg["budgets"][k] = v
    return {"configurable": {"thread_id": thread, "deps": Deps(gateway=env["gateway"], llm=llm, cfg=cfg)}}


def bid_job():
    return next(r for r in labels(bid=True, stratum="fit"))["job_id"]


def charges(env, pid):
    return env["sim"].state.engine.store.q("SELECT * FROM ledger WHERE reason='submit' AND ref=?", (pid,))


async def test_good_job_pauses_for_approval_then_submits_once(env):
    graph = build_bid_graph(InMemorySaver())
    llm, cfg = FakeLLM(), run_cfg(env, FakeLLM())
    cfg["configurable"]["deps"].llm = llm
    out = await graph.ainvoke({"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    assert "__interrupt__" in out, out.get("status_reason")
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "proposal_approval" and payload["preview"]["sent"] is False
    assert {"job_analyst", "risk_assessor", "fit_matcher"} <= set(llm.calls)        # all three branches ran
    assert "[" not in payload["preview"]["cover_letter"]                             # citations stripped
    done = await graph.ainvoke(Command(resume={"action": "approve"}), cfg)
    assert done["status"] == "submitted"
    assert len(charges(env, done["marketplace_proposal_id"])) == 1


async def test_crash_after_submit_before_checkpoint_still_submits_once(env):
    saver = InMemorySaver()
    cfg = run_cfg(env, FakeLLM(), thread="crash")
    graph = build_bid_graph(saver)
    out = await graph.ainvoke({"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    pid = out["marketplace_proposal_id"]

    class DiesAfterSubmit(McpGateway):
        async def call(self, node, server, tool, args, trace_id):
            result = await super().call(node, server, tool, args, trace_id)
            if tool == "submit_proposal" and not args.get("dry_run"):
                raise ProcessKilled("process killed")
            return result

    crashing = run_cfg(env, FakeLLM(), thread="crash")
    crashing["configurable"]["deps"].gateway = DiesAfterSubmit(env["gateway"].sessions)
    with pytest.raises(ProcessKilled):
        await graph.ainvoke(Command(resume={"action": "approve"}), crashing)
    assert len(charges(env, pid)) == 1                     # the marketplace accepted it...
    restarted = build_bid_graph(saver)                      # ...but no checkpoint: restart and resume
    done = await restarted.ainvoke(Command(resume={"action": "approve"}), cfg)
    assert done["status"] == "submitted"
    assert len(charges(env, pid)) == 1                     # replayed, not submitted again


async def test_scam_is_skipped_with_reasons(env):
    scam = labels(scam=True)[0]["job_id"]
    graph = build_bid_graph(InMemorySaver())
    out = await graph.ainvoke({"user": USER, "job": await job(env, scam), "status": "running"}, run_cfg(env, FakeLLM()))
    assert out["status"] == "skipped" and "risk" in out["status_reason"]
    assert "writer" not in [e["node"] for e in out["events"]]


async def test_injection_is_flagged_but_job_still_bid(env):
    inj = labels(injection=True, bid=True)[0]["job_id"]
    graph = build_bid_graph(InMemorySaver())
    out = await graph.ainvoke({"user": USER, "job": await job(env, inj), "status": "running"}, run_cfg(env, FakeLLM()))
    assert "prompt_injection" in out["risk_report"]["flags"]
    assert "__interrupt__" in out                         # still reaches approval: flagged, not obeyed


async def test_critic_loop_is_capped_at_two_revisions(env):
    llm = FakeLLM(critic_verdicts=["revise", "revise", "revise", "revise"])
    cfg = run_cfg(env, llm)
    cfg["configurable"]["deps"].llm = llm
    out = await build_bid_graph(InMemorySaver()).ainvoke(
        {"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    assert llm.calls["writer"] == 3 and llm.calls["critic"] == 3 and out["revisions"] == 2
    assert "__interrupt__" in out


async def test_compliance_blocks_off_platform_text(env):
    llm = FakeLLM(writer_text="I can deliver this dashboard quickly, just message me on WhatsApp so we can talk.")
    cfg = run_cfg(env, llm)
    cfg["configurable"]["deps"].llm = llm
    out = await build_bid_graph(InMemorySaver()).ainvoke(
        {"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    assert out["status"] == "needs_attention" and "no_off_platform" in out["status_reason"]


async def test_reject_and_edit_paths(env):
    graph = build_bid_graph(InMemorySaver())
    cfg = run_cfg(env, FakeLLM(), thread="rej")
    await graph.ainvoke({"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    rej = await graph.ainvoke(Command(resume={"action": "reject", "reason": "not my niche"}), cfg)
    assert rej["status"] == "rejected" and "submission" not in rej

    cfg2 = run_cfg(env, FakeLLM(), thread="edit")
    jid = labels(bid=True, stratum="fit")[1]["job_id"]
    await graph.ainvoke({"user": USER, "job": await job(env, jid), "status": "running"}, cfg2)
    edited = "I have built exactly this kind of dashboard before and would start by agreeing your metrics. " \
             "Guaranteed 100% satisfaction."
    again = await graph.ainvoke(Command(resume={"action": "edit", "cover_letter": edited}), cfg2)
    assert "__interrupt__" in again                                    # re-checked, asks again
    assert "Guaranteed" not in again["__interrupt__"][0].value["preview"]["cover_letter"]   # compliance fixed it
    done = await graph.ainvoke(Command(resume={"action": "approve"}), cfg2)
    assert done["status"] == "submitted"


async def test_marketplace_down_parks_the_thread(env):
    j = await job(env, bid_job())
    await env["http"].post("/admin/faults", json={"down": True}, headers=ADMIN)
    out = await build_bid_graph(InMemorySaver()).ainvoke({"user": USER, "job": j, "status": "running"},
                                                         run_cfg(env, FakeLLM()))
    assert out["status"] == "waiting_marketplace"


async def test_step_budget(env):
    out = await build_bid_graph(InMemorySaver()).ainvoke(
        {"user": USER, "job": await job(env, bid_job()), "status": "running"},
        run_cfg(env, FakeLLM(), max_graph_steps=4))
    assert out["status"] == "needs_attention" and "budget" in out["status_reason"]


async def test_allowlist(env):
    with pytest.raises(ToolNotAllowed):
        await env["gateway"].call("writer", "marketplace", "submit_proposal", {}, "t")


async def test_two_parallel_branches_failing_at_once(env):
    """Regression: two branches writing `status` in the same step crashed the graph."""
    from agent.mcp_client import MarketplaceDown

    class Broken(McpGateway):
        async def call(self, node, server, tool, args, trace_id):
            if node == "risk_assessor":
                raise MarketplaceDown("marketplace_unavailable", "down")
            if node == "fit_matcher":
                raise RuntimeError("portfolio exploded")
            return await super().call(node, server, tool, args, trace_id)

    cfg = run_cfg(env, FakeLLM())
    cfg["configurable"]["deps"].gateway = Broken(env["gateway"].sessions)
    out = await build_bid_graph(InMemorySaver()).ainvoke(
        {"user": USER, "job": await job(env, bid_job()), "status": "running"}, cfg)
    assert out["status"] == "waiting_marketplace"            # the resumable failure wins
    assert {f["node"] for f in out["branch_failures"]} == {"risk_assessor", "fit_matcher"}


async def test_retry_on_same_thread_starts_clean(env):
    """A dead-lettered job retried on its thread must not see the old run's failures."""
    from agent.graphs.bid_graph import start_input

    saver, j = InMemorySaver(), await job(env, bid_job())

    class Broken(McpGateway):
        async def call(self, node, server, tool, args, trace_id):
            if node == "fit_matcher":
                raise RuntimeError("temporary")
            return await super().call(node, server, tool, args, trace_id)

    bad = run_cfg(env, FakeLLM(), thread="retry")
    bad["configurable"]["deps"].gateway = Broken(env["gateway"].sessions)
    first = await build_bid_graph(saver).ainvoke(start_input(USER, j), bad)
    assert first["status"] == "dead_letter"
    second = await build_bid_graph(saver).ainvoke(start_input(USER, j), run_cfg(env, FakeLLM(), thread="retry"))
    assert "__interrupt__" in second and second["branch_failures"] == []


async def test_critic_failure_does_not_kill_the_job(env):
    class CriticDown(FakeLLM):
        def __call__(self, node, schema):
            if node == "critic":
                def fail(messages):
                    raise RuntimeError("All models failed for critic: Failed to validate JSON")
                return fail
            return super().__call__(node, schema)

    out = await build_bid_graph(InMemorySaver()).ainvoke(
        {"user": USER, "job": await job(env, bid_job()), "status": "running"}, run_cfg(env, CriticDown()))
    assert "__interrupt__" in out                                   # still reaches approval
    assert out["critiques"][-1]["verdict"] == "unavailable"          # and the gap is visible
