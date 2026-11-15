"""Client Liaison nodes for the conversation graph (one graph thread per client conversation).

read_thread -> classify -> offer_slots (only for call requests) -> draft_reply -> reply_compliance
-> approve_reply (interrupt) -> send_reply (+ tentative calendar holds for the offered slots).
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import interrupt

from agent.handoffs import ApprovalDecision, IntentLLM, ReplyDraft, ReplyLLM
from agent.llm import prompt
from agent.memory.store import record_edit, style_rules
from agent.nodes.approval import idem_key
from agent.nodes.common import Ctx, node, untrusted
from agent.nodes.compliance import check
from agent.nodes.risk_assessor import INJECTION, PATTERNS, SENTENCES
from agent.nodes.writer import persona_header


def conversation_text(messages: list[dict]) -> str:
    return "\n".join(f"{'CLIENT' if m['sender'] == 'client' else 'YOU'}: {m['body']}" for m in messages)


def new_client_messages(messages: list[dict]) -> list[dict]:
    """Client messages after our last message: what this run must answer."""
    last_ours = max((i for i, m in enumerate(messages) if m["sender"] == "freelancer"), default=-1)
    return [m for m in messages[last_ours + 1:] if m["sender"] == "client"]


def rule_signals(text: str) -> dict[str, bool]:
    scam = injection = False
    for sentence in SENTENCES.split(text.lower()):
        if re.search(INJECTION[1], sentence):
            injection = True
        elif any(re.search(pat, sentence) for _, pat in PATTERNS.values()):
            scam = True
    return {"scam": scam, "injection": injection}


@node("read_thread")
async def read_thread(state: dict, ctx: Ctx) -> dict:
    t = await ctx.tool("read_thread", "marketplace", "list_messages", {"thread_id": state["thread_id"]})
    new = new_client_messages(t["messages"])
    if not new or not t["accepting_messages"]:
        return {"messages": t["messages"], "status": "no_action",
                "status_reason": "nothing new to answer" if not new else f"conversation closed ({t['status']})",
                "_summary": "no new client message"}
    job = await ctx.tool("read_thread", "marketplace", "get_job", {"job_id": t["job_id"]})
    props = await ctx.tool("read_thread", "marketplace", "list_proposals", {})
    ours = next((p for p in props["proposals"] if p["proposal_id"] == t["proposal_id"]), {})
    return {"messages": t["messages"], "new_messages": new, "job": job, "proposal": ours,
            "conversation_status": t["status"], "_summary": f"{len(new)} new client message(s)"}


@node("classify")
async def classify(state: dict, ctx: Ctx) -> dict:
    newest = "\n".join(m["body"] for m in state["new_messages"])
    rules = rule_signals(newest)
    out: IntentLLM = ctx.ask("intent", IntentLLM, [
        SystemMessage(prompt("intent")),
        HumanMessage(f"{untrusted('conversation', conversation_text(state['messages']))}\n\n"
                     f"Newest client message(s):\n{untrusted('client_message', newest)}")])
    intent = "scam_signal" if rules["scam"] else out.intent
    flags = [f for f, on in (("scam_signal", rules["scam"] or out.intent == "scam_signal"),
                             ("prompt_injection", rules["injection"])) if on]
    return {"intent": {"intent": intent, "wants_call": out.wants_call or intent == "interview_request",
                       "summary": out.summary, "flags": flags},
            "_summary": f"{intent} {flags or ''}"}


def needs_slots(state: dict) -> bool:
    i = state["intent"]
    return i["wants_call"] and i["intent"] != "scam_signal"


@node("offer_slots")
async def offer_slots(state: dict, ctx: Ctx) -> dict:
    r = await ctx.tool("offer_slots", "workspace", "get_free_slots", {"days": 5, "duration_minutes": 30, "max_slots": 3})
    return {"slots": r["slots"], "_summary": f"{len(r['slots'])} free slots"}


@node("draft_reply")
async def draft_reply(state: dict, ctx: Ctx) -> dict:
    name, headline = persona_header(state["user"])
    rules = style_rules(ctx.deps.store, state["user"]["user_id"])
    slots = "\n".join(f"- {s['start_local']} ({s['start_utc']} UTC)" for s in state.get("slots", [])) or "none"
    system = prompt("client_liaison").format(name=name, headline=headline)
    if rules:
        system += "\n\nThe user's own style rules (learned from their edits):\n" + "\n".join(f"- {r}" for r in rules)
    i = state["intent"]
    out: ReplyLLM = ctx.ask("client_liaison", ReplyLLM, [
        SystemMessage(system),
        HumanMessage(f"JOB: {state['job']['title']}\n\nPROPOSAL WE SENT:\n{state.get('proposal', {}).get('cover_letter', '')}\n"
                     f"Agreed bid: {state.get('proposal', {}).get('bid_amount')}\n\n"
                     f"{untrusted('conversation', conversation_text(state['messages']))}\n\n"
                     f"Client intent: {i['intent']} ({i['summary']}). Flags: {i['flags'] or 'none'}\n"
                     f"AVAILABLE SLOTS:\n{slots}")])
    draft = ReplyDraft(thread_id=state["thread_id"], body=out.reply, intent=i["intent"],
                       offered_slots=state.get("slots", []) if needs_slots(state) else [])
    return {"reply_draft": draft.model_dump(), "_summary": f"{len(out.reply.split())} words"}


@node("reply_compliance")
async def reply_compliance(state: dict, ctx: Ctx) -> dict:
    d = dict(state["reply_draft"])
    grounding = (state.get("proposal", {}).get("cover_letter", "") + " " + state["job"]["description"]).lower()
    text, fixed, blocked = check(d["body"], grounding, [])
    if blocked:
        return {"status": "needs_attention", "status_reason": f"reply blocked by: {', '.join(blocked)}",
                "_summary": f"blocked {blocked}"}
    if fixed:
        d["body"] = text
    return {"reply_draft": d, "reply_compliance": {"status": "fixed" if fixed else "pass", "fixed": fixed},
            "_summary": f"{'fixed ' + str(fixed) if fixed else 'pass'}"}


@node("approve_reply")
async def approve_reply(state: dict, ctx: Ctx) -> dict:
    decision = ApprovalDecision(**interrupt({
        "kind": "message_approval", "thread_id": state["thread_id"], "job_title": state["job"]["title"],
        "messages": state["messages"], "intent": state["intent"], "draft": state["reply_draft"],
        "compliance": state.get("reply_compliance")}))
    if decision.action == "reject":
        return {"approval": decision.model_dump(), "status": "rejected",
                "status_reason": decision.reason or "rejected by user", "_summary": "rejected"}
    if decision.action == "edit" and decision.cover_letter:
        d = dict(state["reply_draft"])
        if ctx.deps.store is not None:   # learn from the edit (promotion rules decide what sticks)
            record_edit(ctx.deps.store, state["user"]["user_id"], d["body"], decision.cover_letter,
                        f"message:{state['thread_id']}:v{d['version']}")
        d.update(body=decision.cover_letter, version=d["version"] + 1, edited_by_user=True)
        return {"approval": decision.model_dump(), "reply_draft": d, "_summary": "edited; re-checking"}
    return {"approval": decision.model_dump(), "_summary": "approved"}


@node("send_reply")
async def send_reply(state: dict, ctx: Ctx) -> dict:
    d = state["reply_draft"]
    sent = await ctx.tool("send_reply", "marketplace", "send_message", {
        "thread_id": state["thread_id"], "body": d["body"],
        "idempotency_key": idem_key(ctx.thread_id, "message", d["body"])})
    holds = []
    for s in d.get("offered_slots", []):
        h = await ctx.tool("send_reply", "workspace", "create_interview_hold", {
            "start": s["start_utc"], "ref": state["thread_id"],
            "idempotency_key": idem_key(ctx.thread_id, "hold", s["start_utc"])})
        holds.append(h)
    return {"sent": sent, "holds": holds, "status": "sent",
            "status_reason": f"sent; conversation now {sent['thread']['status']}",
            "_summary": f"sent, {len(holds)} tentative holds"}
