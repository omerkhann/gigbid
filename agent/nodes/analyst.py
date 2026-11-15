"""Job Analyst: job post -> JobSpec (small model). Structured fields come straight from the
marketplace; the model adds requirements, deliverables, timeline, hidden needs and red flags."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import JobSpec, JobSpecLLM
from agent.llm import prompt
from agent.nodes.common import Ctx, node, untrusted


def job_text(job: dict) -> str:
    qs = "\n".join(f"- {q}" for q in job.get("screening_questions") or []) or "none"
    return (f"Title: {job['title']}\nSkills listed: {', '.join(job.get('required_skills') or [])}\n"
            f"Screening questions:\n{qs}\n\n{job['description']}")


@node("job_analyst")
async def job_analyst(state: dict, ctx: Ctx) -> dict:
    job = state["job"]
    out: JobSpecLLM = ctx.ask("job_analyst", JobSpecLLM, [
        SystemMessage(prompt("job_analyst")), HumanMessage(untrusted("job_post", job_text(job)))])
    spec = JobSpec(job_id=job["job_id"], title=job["title"], deliverables=out.deliverables,
                   requirements=out.requirements[:8], required_skills=job.get("required_skills") or [],
                   budget_min=job.get("budget_min"), budget_max=job.get("budget_max"),
                   payment_type=job.get("payment_type"), timeline=out.timeline,
                   screening_questions=job.get("screening_questions") or [], hidden_needs=out.hidden_needs,
                   red_flags=out.red_flags)
    return {"job_spec": spec.model_dump(), "_summary": f"{len(spec.requirements)} requirements"}
