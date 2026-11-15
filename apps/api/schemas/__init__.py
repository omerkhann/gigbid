"""Request and response models. The web client's TypeScript types are generated from these (OpenAPI)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)


class RegisterIn(LoginIn):
    name: str = Field(min_length=1, max_length=100)
    persona: Literal["ml_engineer", "fullstack_dev", "data_analyst"]


class Me(BaseModel):
    user_id: str
    email: str
    name: str
    persona: str | None
    settings: dict[str, Any]


class SettingsIn(BaseModel):
    hourly_floor: float | None = Field(default=None, ge=0, le=1000)
    fixed_floor: float | None = Field(default=None, ge=0, le=100000)
    hourly_rate: float | None = Field(default=None, ge=0, le=1000)
    weekly_connects_budget: int | None = Field(default=None, ge=0, le=1000)
    autonomy: Literal["approve_everything", "auto_skip_low_fit"] | None = None


class SavedSearchIn(BaseModel):
    query: str | None = Field(default=None, max_length=200)
    category: Literal["development", "data_science", "marketing", "3d_design"] | None = None
    skills: list[str] = Field(default_factory=list, max_length=10)
    min_budget: float | None = Field(default=None, ge=0)
    every_minutes: int = Field(default=60, ge=15, le=1440)


class SavedSearch(SavedSearchIn):
    search_id: str
    last_run_at: str | None


class RunRow(BaseModel):
    thread_id: str
    kind: Literal["bid", "conversation"]
    job_id: str | None
    conversation_id: str | None
    title: str | None
    status: str
    status_reason: str | None
    summary: dict[str, Any]
    trace_id: str | None
    tokens: int
    latency_ms: int
    updated_at: str


class Enqueued(BaseModel):
    queued: bool
    thread_id: str | None = None
    trace_id: str


class ApprovalIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    cover_letter: str | None = Field(default=None, max_length=5000, description="Edited proposal or message text")
    screening_answers: list[str] | None = None
    bid_amount: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)


class RunDetail(BaseModel):
    thread_id: str
    kind: str
    status: str | None
    status_reason: str | None
    trace_id: str | None
    trace_url: str | None = None
    events: list[dict[str, Any]]
    state: dict[str, Any]
    pending_approval: dict[str, Any] | None


class PipelineCard(BaseModel):
    proposal_id: str
    job_id: str
    title: str | None
    bid_amount: float
    bid_type: str
    thread_id: str | None
    updated_at: str | None
    run_thread: str


class Pipeline(BaseModel):
    columns: list[str]
    board: dict[str, list[PipelineCard]]


class ThreadSummary(BaseModel):
    thread_id: str
    proposal_id: str
    job_id: str
    client_id: str
    status: str
    accepting_messages: bool
    agent_status: str | None = None
    intent: str | None = None


class Threads(BaseModel):
    threads: list[ThreadSummary]


class Message(BaseModel):
    sender: Literal["client", "freelancer"]
    body: str
    at: str


class Thread(BaseModel):
    thread_id: str
    proposal_id: str
    job_id: str
    client_id: str
    status: str
    accepting_messages: bool
    messages: list[Message]
    run_thread: str
    pending_reply: dict[str, Any] | None


class Analytics(BaseModel):
    jobs_analysed: int
    decisions: dict[str, int]
    proposals_submitted: int
    connects_spent: int
    reply_rate: float | None
    hire_rate: float | None
    by_category: dict[str, dict[str, int]]
    per_proposal: dict[str, int]
    per_job_analysed: dict[str, int]
    top_skip_reasons: list[tuple[str, int]]


class MemoryItem(BaseModel):
    key: str
    rule: str | None = None
    count: int | None = None
    since: str | None = None
    evidence_edits: int | None = None
    examples: list[str] | None = None


class Memory(BaseModel):
    style_rules: list[MemoryItem]
    style_candidates: list[MemoryItem]
    outcomes: dict[str, dict[str, int]]


class MarketplaceHealth(BaseModel):
    marketplace: Literal["ok", "unavailable"]
    connects_balance: int | None = None
    detail: str | None = None


class RegenerateIn(BaseModel):
    paragraph: str = Field(min_length=1, max_length=3000, description="The paragraph to rewrite, as shown")
    instruction: str | None = Field(default=None, max_length=300, description="Optional, e.g. 'shorter' or 'more specific'")


class RegenerateOut(BaseModel):
    text: str
