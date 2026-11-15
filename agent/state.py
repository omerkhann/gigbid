"""Bid graph state (assignment C2).

State is what this job needs right now. Hand-off objects are stored as plain dicts (Pydantic
`model_dump()`), so checkpoints stay simple JSON in Postgres.

Reducers: keys written by the three parallel branches are separate (job_spec, risk_report,
fit_report), so they never conflict. Keys several nodes append to use reducers that append, and
reset when given None: a new run on an existing thread (a retry) starts with clean per-run
bookkeeping (failures, timeline, errors, step and token budgets). See start_input() in the graph.

Not in state: the full execution trace (every tool/LLM call with arguments and results) goes to
tracing; `events` here is only a compact timeline for the UI. Long-term memory lives in a
separate store and is written only by promotion rules.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

Status = Literal["running", "skipped", "watching", "awaiting_approval", "submitted", "rejected",
                 "needs_attention", "waiting_marketplace", "dead_letter"]


def add_or_reset(old: list | None, new: list | None) -> list:
    """Append, except that None clears the list (a new run on an existing thread starts clean)."""
    return [] if new is None else [*(old or []), *new]


def sum_or_reset(old: int | None, new: int | None) -> int:
    """Add, except that None resets to 0 (budgets are per run)."""
    return 0 if new is None else (old or 0) + new


class GigBidState(TypedDict, total=False):
    # inputs
    user: dict[str, Any]                 # user_id, persona, floors, connects reserve
    job: dict[str, Any]                  # marketplace job as returned by get_job
    # parallel analyses
    job_spec: dict[str, Any]
    risk_report: dict[str, Any]
    fit_report: dict[str, Any]
    evidence: Annotated[dict[str, dict[str, Any]], lambda a, b: {**(a or {}), **(b or {})}]
    # decision and drafting
    decision: dict[str, Any]
    price_quote: dict[str, Any]
    proposal_draft: dict[str, Any]
    claims: list[dict[str, Any]]
    critiques: Annotated[list[dict[str, Any]], add_or_reset]
    revisions: int
    revise_requested: bool
    compliance_verdict: dict[str, Any]
    marketplace_proposal_id: str
    preview: dict[str, Any]              # dry_run result shown on the approval screen
    approval: dict[str, Any]
    submission: dict[str, Any]
    # bookkeeping
    status: Status
    status_reason: str
    steps: Annotated[int, sum_or_reset]
    tokens: Annotated[int, sum_or_reset]
    events: Annotated[list[dict[str, Any]], add_or_reset]
    errors: Annotated[list[str], add_or_reset]
    branch_failures: Annotated[list[dict[str, Any]], add_or_reset]   # from the parallel analyses


# Kept for the starter kit's name.
BidState = GigBidState
