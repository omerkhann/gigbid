"""Fit Matcher: requirement -> portfolio evidence -> coverage, then a computed fit score.

Runs in parallel with the Job Analyst, so it cannot use the JobSpec. Its requirements are the job's
listed skills (generic tags dropped) plus the job title as a whole-job requirement. Retrieval is a
Portfolio MCP call per requirement; one batched small-model call judges all of them, and evidence
ids the model invents are discarded. Score = mean of strong 1, partial 0.5, missing 0.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from agent.handoffs import FitLLM, FitReport, RequirementFit
from agent.llm import prompt
from agent.nodes.common import Ctx, node

GENERIC = {"English", "Smartphone", "Tablet", "Business with 1-9 Employees", "Business with 10-99 Employees",
           "Business with 100-499 Employees", "Business with 500-999 Employees", "Business with 1000+ Employees"}
WEIGHT = {"strong": 1.0, "partial": 0.5, "missing": 0.0}
MAX_SKILLS = 6


def requirements_for(job: dict) -> list[str]:
    skills = [s for s in job.get("required_skills") or [] if s not in GENERIC][:MAX_SKILLS]
    # Very short tags ("R", "C") are too ambiguous to search for alone (and below the tool's minimum).
    skills = [s if len(s) >= 3 else f"{s} programming experience" for s in skills]
    return [f"{job['title']} (the job as a whole)", *skills]


@node("fit_matcher")
async def fit_matcher(state: dict, ctx: Ctx) -> dict:
    job = state["job"]
    k = ctx.deps.cfg["rag"]["evidence_per_requirement"]
    reqs = requirements_for(job)
    found: dict[int, list[dict]] = {}
    evidence: dict[str, dict] = {}
    for i, req in enumerate(reqs):
        res = await ctx.tool("fit_matcher", "portfolio", "search_evidence", {"requirement": req, "k": k})
        found[i] = res["items"]
        for item in res["items"]:
            evidence[item["evidence_id"]] = {key: item[key] for key in
                                             ("evidence_id", "type", "title", "project_id", "date", "outcome", "text")}
    blocks = []
    for i, req in enumerate(reqs):
        items = "\n".join(f"  - id={e['evidence_id']} type={e['type']}: {e['text'][:400]}" for e in found[i]) or "  (none)"
        blocks.append(f"Requirement {i}: {req}\nEvidence:\n{items}")
    out: FitLLM = ctx.ask("fit_matcher", FitLLM, [
        SystemMessage(prompt("fit_matcher")),
        HumanMessage("\n\n".join(blocks))])
    judged = {j.index: j for j in out.items if 0 <= j.index < len(reqs)}
    results = []
    for i, req in enumerate(reqs):
        j = judged.get(i)
        allowed = {e["evidence_id"] for e in found[i]}
        if j is None:
            results.append(RequirementFit(requirement=req, coverage="missing", reason="not judged"))
            continue
        ids = [e for e in j.evidence_ids if e in allowed]   # drop invented ids
        cov = j.coverage if ids or j.coverage == "missing" else "missing"
        results.append(RequirementFit(requirement=req, coverage=cov, evidence_ids=ids, reason=j.reason))
    score = round(sum(WEIGHT[r.coverage] for r in results) / len(results), 3) if results else 0.0
    skill_rows = results[1:]
    report = FitReport(score=score,
                       matched_skills=[r.requirement for r in skill_rows if r.coverage != "missing"],
                       missing_skills=[r.requirement for r in skill_rows if r.coverage == "missing"],
                       evidence_ids=sorted({e for r in results for e in r.evidence_ids}),
                       requirements=results)
    used = {e: evidence[e] for e in report.evidence_ids}
    return {"fit_report": report.model_dump(), "evidence": used,
            "_summary": f"fit {score} ({sum(r.coverage == 'strong' for r in results)} strong of {len(results)})"}
