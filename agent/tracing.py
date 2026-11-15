"""Tracing with Arize Phoenix (self-hosted) via OpenInference (assignment E3).

Off unless PHOENIX_COLLECTOR_ENDPOINT is set, so tests and CI never need Phoenix.

What gets traced: every LangChain/LangGraph step and every LLM call (with token counts and
latency), grouped by graph thread (Phoenix "session" = our thread id) and tagged with GigBid's own
trace id. That id starts at the API request (X-Trace-Id), goes into queued work, the graph config,
every MCP call's meta and the MCP servers' audit logs, so one id joins the UI, API, graph, MCP
servers and audit log.
"""

from __future__ import annotations

import os
from contextlib import contextmanager, nullcontext

_ENABLED = False


def setup_tracing(service: str) -> bool:
    global _ENABLED
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT")
    if not endpoint or _ENABLED:
        return _ENABLED
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    provider = register(project_name=os.environ.get("PHOENIX_PROJECT", "gigbid"), endpoint=endpoint, batch=True,
                        set_global_tracer_provider=True, verbose=False)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    _ENABLED = True
    return True


@contextmanager
def run_attributes(thread_id: str, trace_id: str, user_id: str):
    """Attach session, user and GigBid trace id to every span created inside."""
    if not _ENABLED:
        with nullcontext():
            yield
        return
    from openinference.instrumentation import using_attributes

    with using_attributes(session_id=thread_id, user_id=user_id,
                          metadata={"gigbid.trace_id": trace_id, "gigbid.thread_id": thread_id},
                          tags=[thread_id.split(":", 1)[0]]):
        yield


def trace_link(thread_id: str) -> str | None:
    """Where to look in the Phoenix UI for this run's traces."""
    base = os.environ.get("PHOENIX_UI_URL", "http://localhost:6006")
    return f"{base}/projects?session={thread_id}" if _ENABLED or os.environ.get("PHOENIX_COLLECTOR_ENDPOINT") else None
