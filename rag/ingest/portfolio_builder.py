"""Signature extension X3: turn a GitHub account (or a folder of repos) into case studies, verified
against the code, in the folder format the Portfolio MCP server reads.

  python -m rag.ingest.portfolio_builder --repos data/personas/ml_engineer/repos --out data/processed/x3/ml_engineer
  python -m rag.ingest.portfolio_builder --github <username> --out my-portfolio   # needs GITHUB_TOKEN

For each repo: collect the README and a bounded set of source files; the Writer-tier model drafts a
case study that cites a file path after every factual sentence; claim verification (rag/verify.py,
the same verifier the bid graph uses) checks each claim against those files and removes unsupported
ones. Output: case_studies/gh-<repo>.md, repos/<repo>/ (README + files + .project.json) and
skeleton.yaml, so the Portfolio server can index it directly.

The GitHub source goes through GitHub's official MCP server (third-party server, assignment A5),
run as its published Docker image over stdio with a read-only token. No scraping: only the API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".sql", ".ipynb", ".go", ".rs", ".java", ".rb", ".php", ".yml",
            ".yaml", ".toml", ".json", ".r", ".R", ".sh", ".dockerfile"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".next"}
MAX_FILES, MAX_CHARS = 12, 3000
GITHUB_MCP_IMAGE = "ghcr.io/github/github-mcp-server"


class CaseStudyLLM(BaseModel):
    title: str = Field(max_length=120)
    summary: str
    body: str
    skills: list[str] = Field(default_factory=list)


@dataclass
class Repo:
    name: str
    files: dict[str, str]                  # path -> text (README first)
    project_id: str | None = None
    url: str | None = None
    meta: dict = field(default_factory=dict)


# --- sources ---------------------------------------------------------------------------------------

def local_repos(root: Path) -> list[Repo]:
    repos = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        files: dict[str, str] = {}
        paths = sorted((p for p in d.rglob("*") if p.is_file() and not (set(p.parts) & SKIP_DIRS)),
                       key=lambda p: (p.name.lower() != "readme.md", len(p.parts), p.name))
        for p in paths:
            if p.name.lower() == "readme.md" or p.suffix in CODE_EXT and p.name != ".project.json":
                files[p.relative_to(d).as_posix()] = p.read_text(encoding="utf-8", errors="replace")[:MAX_CHARS]
            if len(files) >= MAX_FILES:
                break
        meta_file = d / ".project.json"
        pid = json.loads(meta_file.read_text(encoding="utf-8")).get("project_id") if meta_file.exists() else None
        repos.append(Repo(d.name, files, pid))
    return repos


async def github_repos(username: str, token: str, limit: int = 10) -> list[Repo]:
    """Public repos of `username` through GitHub's official MCP server (read-only toolsets)."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command="docker", args=[
        "run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", "-e", "GITHUB_TOOLSETS=repos",
        "-e", "GITHUB_READ_ONLY=1", GITHUB_MCP_IMAGE], env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token})

    def text(res) -> str:
        return "".join(getattr(c, "text", "") for c in res.content)

    repos = []
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        found = json.loads(text(await s.call_tool("search_repositories", {
            "query": f"user:{username} fork:false", "perPage": limit})))
        for item in (found.get("items") or [])[:limit]:
            owner, name = item["owner"]["login"], item["name"]
            files: dict[str, str] = {}
            tree = await s.call_tool("get_file_contents", {"owner": owner, "repo": name, "path": "/"})
            entries = json.loads(text(tree)) if text(tree).startswith("[") else []
            wanted = sorted((e["path"] for e in entries if e.get("type") == "file"
                             and (e["path"].lower() == "readme.md" or Path(e["path"]).suffix in CODE_EXT)),
                            key=lambda p: p.lower() != "readme.md")[:MAX_FILES]
            for path in wanted:
                res = await s.call_tool("get_file_contents", {"owner": owner, "repo": name, "path": path})
                files[path] = text(res)[:MAX_CHARS]
            repos.append(Repo(name, files, None, item.get("html_url"),
                              {"stars": item.get("stargazers_count"), "language": item.get("language")}))
    return repos


# --- build -----------------------------------------------------------------------------------------

CITATION = re.compile(r"\s*\[[^\]]+\]")


def verify(repo: Repo, cs: CaseStudyLLM, ask_verify) -> tuple[str, dict]:
    """Check every claim against the repo files; return the body with unsupported claims removed."""
    from rag.verify import verify_claims

    evidence = {p: {"evidence_id": p, "text": t} for p, t in repo.files.items()}
    claims, revised = verify_claims(ask_verify, cs.body, evidence)
    stats = {"claims": len(claims), "supported": sum(c.verdict == "supported" for c in claims),
             "partly": sum(c.verdict not in ("supported", "unsupported") for c in claims),
             "unsupported": sum(c.verdict == "unsupported" for c in claims)}
    return revised or cs.body, stats


def build(repos: list[Repo], out: Path, node: str = "portfolio_builder", profile_name: str = "GitHub portfolio") -> list[dict]:
    from agent.handoffs import ClaimCheckLLM
    from agent.llm import structured

    ask_draft = structured(node, CaseStudyLLM)
    ask_verify = structured("verify_claims", ClaimCheckLLM)
    (out / "case_studies").mkdir(parents=True, exist_ok=True)
    report, projects = [], []
    for repo in repos:
        if not repo.files:
            continue
        cs, _ = ask_draft(_messages(repo))
        body, stats = verify(repo, cs, lambda m: ask_verify(m)[0])
        pid = repo.project_id or f"gh-{repo.name}"
        source = repo.url or f"repos/{repo.name}"
        (out / "case_studies" / f"{pid}.md").write_text(
            f"# {cs.title}\n\n_{cs.summary}_\n\n{body.strip()}\n\nSource: {source} (generated from the code and "
            f"verified against it; {stats['unsupported']} unsupported claim(s) removed)\n", encoding="utf-8", newline="\n")
        rdir = out / "repos" / repo.name
        for path, text in repo.files.items():
            (rdir / path).parent.mkdir(parents=True, exist_ok=True)
            (rdir / path).write_text(text, encoding="utf-8", newline="\n")
        (rdir / ".project.json").write_text(json.dumps({"project_id": pid, "generated_by": "x3"}), encoding="utf-8")
        projects.append({"id": pid, "title": cs.title, "skills": cs.skills, "source": source})
        report.append({"repo": repo.name, "project_id": pid, "skills": cs.skills,
                       "body_before": cs.body, "body_after": body, **stats})
        print(json.dumps({k: report[-1][k] for k in ("repo", "claims", "supported", "unsupported")}), flush=True)
    (out / "skeleton.yaml").write_text(yaml.safe_dump({"name": profile_name, "projects": projects}, sort_keys=False),
                                       encoding="utf-8", newline="\n")
    return report


def _messages(repo: Repo):
    from langchain_core.messages import HumanMessage, SystemMessage

    from agent.llm import prompt
    from agent.nodes.common import untrusted

    listing = "\n\n".join(f"FILE {p}\n{untrusted(p, t)}" for p, t in repo.files.items())
    return [SystemMessage(prompt("portfolio_builder")), HumanMessage(f"REPOSITORY: {repo.name}\n\n{listing}")]


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--repos", type=Path, help="folder of repositories (one per subfolder)")
    src.add_argument("--github", help="GitHub username (public repos, via GitHub's MCP server; needs GITHUB_TOKEN)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    if a.repos:
        repos = local_repos(a.repos)[: a.limit]
    else:
        repos = asyncio.run(github_repos(a.github, os.environ["GITHUB_TOKEN"], a.limit))
    report = build(repos, a.out)
    (a.out / "x3_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
