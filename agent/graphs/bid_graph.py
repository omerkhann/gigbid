"""The bid graph (assignment C1): one thread per job. Design: docs/BID_GRAPH_DESIGN.md.

START --Send--> job_analyst | risk_assessor | fit_matcher (parallel) --> decide
decide --bid--> pricing --> writer --> verify_claims --> critic --revise (max 2)--> writer
                                                           \\--ok--> compliance --> prepare_draft --> approve
approve --approve--> submit --> END;  --edit--> compliance;  --reject--> END
Any node can stop the thread (skipped, watching, needs_attention, waiting_marketplace,
dead_letter): every edge checks `status` first.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.nodes.analyst import job_analyst
from agent.nodes.approval import after_approve, approve, prepare_draft, submit
from agent.nodes.common import STOP
from agent.nodes.compliance import compliance
from agent.nodes.critic import after_critic, critic, verify_claims
from agent.nodes.decide import decide
from agent.nodes.fit_matcher import fit_matcher
from agent.nodes.pricing import pricing
from agent.nodes.risk_assessor import risk_assessor
from agent.nodes.writer import writer
from agent.state import GigBidState

PARALLEL = ("job_analyst", "risk_assessor", "fit_matcher")


def start_input(user: dict, job: dict) -> dict:
    """Input for a new run. On an existing thread (a retry) it resets the per-run bookkeeping:
    failures, timeline, errors, and the step and token budgets."""
    return {"user": user, "job": job, "status": "running", "status_reason": "", "branch_failures": None,
            "events": None, "errors": None, "steps": None, "tokens": None, "critiques": None, "revisions": 0}


def fan_out(state: GigBidState) -> list[Send]:
    """Run the three analyses in parallel; each gets the same input state."""
    return [Send(n, state) for n in PARALLEL]


def then(next_node: str):
    def route(state: GigBidState) -> str:
        return END if state.get("status") in STOP else next_node
    route.__name__ = f"to_{next_node}"
    return route


def after_decide(state: GigBidState) -> str:
    if state.get("status") in STOP or state.get("decision", {}).get("action") != "bid":
        return END
    return "pricing"


def after_critic_route(state: GigBidState) -> str:
    return END if state.get("status") in STOP else after_critic(state)


def after_approve_route(state: GigBidState) -> str:
    nxt = after_approve(state)
    return END if nxt == "end" or state.get("status") in STOP else nxt


def build_bid_graph(checkpointer=None):
    g = StateGraph(GigBidState)
    for name, fn in [("job_analyst", job_analyst), ("risk_assessor", risk_assessor), ("fit_matcher", fit_matcher),
                     ("decide", decide), ("pricing", pricing), ("writer", writer), ("verify_claims", verify_claims),
                     ("critic", critic), ("compliance", compliance), ("prepare_draft", prepare_draft),
                     ("approve", approve), ("submit", submit)]:
        g.add_node(name, fn)
    g.add_conditional_edges(START, fan_out, list(PARALLEL))
    g.add_edge(list(PARALLEL), "decide")              # waits for all three branches
    g.add_conditional_edges("decide", after_decide, ["pricing", END])
    g.add_conditional_edges("pricing", then("writer"), ["writer", END])
    g.add_conditional_edges("writer", then("verify_claims"), ["verify_claims", END])
    g.add_conditional_edges("verify_claims", then("critic"), ["critic", END])
    g.add_conditional_edges("critic", after_critic_route, ["writer", "compliance", END])
    g.add_conditional_edges("compliance", then("prepare_draft"), ["prepare_draft", END])
    g.add_conditional_edges("prepare_draft", then("approve"), ["approve", END])
    g.add_conditional_edges("approve", after_approve_route, ["submit", "compliance", END])
    g.add_edge("submit", END)
    return g.compile(checkpointer=checkpointer)
