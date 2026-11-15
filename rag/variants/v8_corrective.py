"""V8 (agentic group): corrective RAG. Grade the evidence, re-query when it is weak, and refuse to
return evidence when none is relevant.

Why: for jobs the persona should skip, plain retrieval still returns *something*, and a Writer
given something will claim it. A small model grades each candidate for the requirement; if fewer
than `min_relevant` pass, it rewrites the query once (synonyms, the capability behind a tool name)
and retrieves again; if still nothing passes, it returns nothing (the caller then knows to say
"missing" instead of stretching weak evidence).
"""

from __future__ import annotations

from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

GRADE_PROMPT = ("You check whether portfolio evidence proves a freelancer can meet ONE job requirement. "
                "For each numbered item answer relevant=true only if it shows this capability was actually "
                "used or delivered (a skill merely mentioned in passing does not count).")
REWRITE_PROMPT = ("Rewrite the job requirement as a search query for a freelancer's portfolio: name the "
                  "underlying capability and 2-3 common tools or synonyms for it. One line.")


class Grade(BaseModel):
    index: int
    relevant: bool


class Grades(BaseModel):
    grades: list[Grade]


class Rewrite(BaseModel):
    query: str = Field(max_length=300)


def grade(ask: Callable, requirement: str, items: list[tuple[str, str]]) -> set[str]:
    listing = "\n".join(f"{i}. {text[:500]}" for i, (_, text) in enumerate(items))
    out: Grades = ask("grade", Grades)([SystemMessage(GRADE_PROMPT),
                                        HumanMessage(f"REQUIREMENT: {requirement}\n\nEVIDENCE:\n{listing}")])
    return {items[g.index][0] for g in out.grades if g.relevant and 0 <= g.index < len(items)}


def rewrite(ask: Callable, requirement: str) -> str:
    out: Rewrite = ask("rewrite", Rewrite)([SystemMessage(REWRITE_PROMPT), HumanMessage(requirement)])
    return out.query
