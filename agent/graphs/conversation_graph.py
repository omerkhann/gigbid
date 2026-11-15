"""Conversation graph (assignment C1): one thread per client conversation.

START -> read_thread -> classify --call requested--> offer_slots -> draft_reply
                                 \\--otherwise------------------->/
draft_reply -> reply_compliance -> approve_reply (interrupt) --approve--> send_reply -> END
                                                 --edit--> reply_compliance; --reject--> END

Each new client message starts a new run on the same thread (start_conversation_input()).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agent.nodes.client_liaison import (
    approve_reply,
    classify,
    draft_reply,
    needs_slots,
    offer_slots,
    read_thread,
    reply_compliance,
    send_reply,
)
from agent.nodes.common import STOP
from agent.state import add_or_reset, sum_or_reset


class ConversationState(TypedDict, total=False):
    user: dict[str, Any]
    thread_id: str
    messages: list[dict[str, Any]]
    new_messages: list[dict[str, Any]]
    job: dict[str, Any]
    proposal: dict[str, Any]
    conversation_status: str
    intent: dict[str, Any]
    slots: list[dict[str, Any]]
    reply_draft: dict[str, Any]
    reply_compliance: dict[str, Any]
    approval: dict[str, Any]
    sent: dict[str, Any]
    holds: list[dict[str, Any]]
    status: str
    status_reason: str
    steps: Annotated[int, sum_or_reset]
    tokens: Annotated[int, sum_or_reset]
    events: Annotated[list[dict[str, Any]], add_or_reset]
    errors: Annotated[list[str], add_or_reset]


def start_conversation_input(user: dict, thread_id: str) -> dict:
    return {"user": user, "thread_id": thread_id, "status": "running", "status_reason": "", "slots": [],
            "events": None, "errors": None, "steps": None, "tokens": None}


def then(next_node: str):
    def route(state: ConversationState) -> str:
        return END if state.get("status") in STOP else next_node
    route.__name__ = f"to_{next_node}"
    return route


def after_classify(state: ConversationState) -> str:
    if state.get("status") in STOP:
        return END
    return "offer_slots" if needs_slots(state) else "draft_reply"


def after_approve(state: ConversationState) -> str:
    if state.get("status") in STOP:
        return END
    return "reply_compliance" if state["approval"]["action"] == "edit" else "send_reply"


def build_conversation_graph(checkpointer=None):
    g = StateGraph(ConversationState)
    for name, fn in [("read_thread", read_thread), ("classify", classify), ("offer_slots", offer_slots),
                     ("draft_reply", draft_reply), ("reply_compliance", reply_compliance),
                     ("approve_reply", approve_reply), ("send_reply", send_reply)]:
        g.add_node(name, fn)
    g.add_edge(START, "read_thread")
    g.add_conditional_edges("read_thread", then("classify"), ["classify", END])
    g.add_conditional_edges("classify", after_classify, ["offer_slots", "draft_reply", END])
    g.add_conditional_edges("offer_slots", then("draft_reply"), ["draft_reply", END])
    g.add_conditional_edges("draft_reply", then("reply_compliance"), ["reply_compliance", END])
    g.add_conditional_edges("reply_compliance", then("approve_reply"), ["approve_reply", END])
    g.add_conditional_edges("approve_reply", after_approve, ["send_reply", "reply_compliance", END])
    g.add_edge("send_reply", END)
    return g.compile(checkpointer=checkpointer)
