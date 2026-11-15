"""V1 (query group): requirement decomposition. One retrieval per requirement, then merge.

Why: a job asking for five things embedded as one query lands near the "average" of them and
misses evidence for the less prominent requirements. Searching each requirement separately and
fusing the lists (RRF) gives every requirement a chance to surface its own evidence.

Requirements come from the job's skill tags (generic tags dropped) plus the title, the same list
the Fit Matcher uses, so no LLM call is needed.
"""

from __future__ import annotations

GENERIC = {"English", "Smartphone", "Tablet", "Business with 1-9 Employees", "Business with 10-99 Employees",
           "Business with 100-499 Employees", "Business with 500-999 Employees", "Business with 1000+ Employees"}


def requirements(job: dict, max_skills: int = 6) -> list[str]:
    skills = [s for s in job.get("required_skills") or [] if s not in GENERIC][:max_skills]
    return [job["title"], *[s if len(s) >= 3 else f"{s} programming" for s in skills]]
