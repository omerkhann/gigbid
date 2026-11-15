"""Load a freelancer's portfolio folder into documents with metadata (assignment B1).

Folder layout (what data/personas/<id>/ contains; any freelancer can use the same layout):
  skeleton.yaml          profile + project index (title, year, industry, named skills, outcome)
  cv.pdf (or cv.md)      CV
  case_studies/<project_id>.md
  repos/<name>/README.md and code; repos/<name>/.project.json links the repo to a project
  reviews.jsonl          {project_id, rating, text, year, client_industry}
  past_proposals.jsonl   {proposal_id, date, job_title, text, cited_projects, outcome, ...}

Metadata on every document: persona, type, project_id, skills, date, client_industry and, for
proposals, outcome. `skills` holds only skills NAMED for the project, never the implied ones:
a metadata filter must not bypass the "skills implied rather than named" trap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".sql", ".yaml", ".yml", ".toml", ".json", ".sh",
                 ".java", ".kt", ".swift", ".php", ".rb", ".go", ".cs", ".dart", ".vue", ".html", ".css"}


@dataclass
class Document:
    doc_id: str
    persona: str
    type: str                      # cv | case_study | readme | code | review | proposal
    title: str
    text: str
    source: str                    # path relative to the portfolio folder
    project_id: str | None = None
    date: str | None = None        # YYYY or YYYY-MM-DD
    skills: list[str] = field(default_factory=list)
    client_industry: str | None = None
    outcome: str | None = None     # proposals: won | replied | ignored
    extra: dict = field(default_factory=dict)

    def meta(self) -> dict:
        return {k: getattr(self, k) for k in ("doc_id", "persona", "type", "title", "source", "project_id",
                                              "date", "skills", "client_industry", "outcome")}


def load_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages).strip()


def load_portfolio(folder: Path) -> list[Document]:
    folder = Path(folder)
    sk = yaml.safe_load((folder / "skeleton.yaml").read_text(encoding="utf-8"))
    pid = sk["id"]
    projects = {p["id"]: p for p in sk["projects"]}
    docs: list[Document] = []

    def project_meta(proj_id: str | None) -> dict:
        p = projects.get(proj_id or "")
        if not p:
            return {}
        return {"project_id": p["id"], "date": str(p["year"]), "skills": list(p["skills"]),
                "client_industry": p["client_industry"]}

    if (folder / "cv.pdf").exists():
        docs.append(Document(f"{pid}:cv", pid, "cv", f"CV - {sk['name']}", load_pdf_text(folder / "cv.pdf"),
                             "cv.pdf", skills=list(sk["listed_skills"])))
    elif (folder / "cv.md").exists():
        docs.append(Document(f"{pid}:cv", pid, "cv", f"CV - {sk['name']}",
                             (folder / "cv.md").read_text(encoding="utf-8"), "cv.md", skills=list(sk["listed_skills"])))

    for f in sorted((folder / "case_studies").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines() if not line.startswith("<!--")).strip()
        title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), f.stem)
        docs.append(Document(f"{pid}:case:{f.stem}", pid, "case_study", title, text,
                             f.relative_to(folder).as_posix(), **project_meta(f.stem)))

    for repo in sorted(p for p in (folder / "repos").glob("*") if p.is_dir()):
        link = repo / ".project.json"
        proj = json.loads(link.read_text(encoding="utf-8"))["project_id"] if link.exists() else None
        if (repo / "README.md").exists():
            docs.append(Document(f"{pid}:readme:{repo.name}", pid, "readme", repo.name,
                                 (repo / "README.md").read_text(encoding="utf-8"),
                                 (repo / "README.md").relative_to(folder).as_posix(), **project_meta(proj)))
        for f in sorted(repo.rglob("*")):
            if f.is_file() and f.suffix in CODE_SUFFIXES and f.name != ".project.json":
                rel = f.relative_to(folder).as_posix()
                docs.append(Document(f"{pid}:code:{rel}", pid, "code", f"{repo.name}/{f.relative_to(repo).as_posix()}",
                                     f.read_text(encoding="utf-8", errors="ignore"), rel, **project_meta(proj)))

    reviews = folder / "reviews.jsonl"
    if reviews.exists():
        for line in reviews.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                r = json.loads(line)
                p = projects.get(r["project_id"], {})
                docs.append(Document(f"{pid}:review:{r['project_id']}", pid, "review",
                                     f"Client review - {p.get('title', r['project_id'])}", r["text"],
                                     "reviews.jsonl", **project_meta(r["project_id"]),
                                     extra={"rating": r.get("rating")}))

    proposals = folder / "past_proposals.jsonl"
    if proposals.exists():
        for line in proposals.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            r = json.loads(line)
            cited = r.get("cited_projects") or []
            meta = project_meta(cited[0]) if cited else {}
            meta["date"] = r["date"]
            docs.append(Document(f"{pid}:proposal:{r['proposal_id']}", pid, "proposal",
                                 f"Proposal - {r['job_title']}", r["text"], "past_proposals.jsonl",
                                 outcome=r["outcome"], **meta,
                                 extra={"proposal_id": r["proposal_id"], "job_title": r["job_title"],
                                        "cited_projects": cited, "bid": r.get("bid"), "style": r.get("style")}))
    return docs
