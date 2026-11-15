"""Generate the SYNTHETIC persona corpus from the hand-written skeletons.

Design: docs/PERSONA_CORPUS.md.

  python -m pipelines.build_personas --plan-only   # print the seeded plan, no LLM calls
  python -m pipelines.build_personas               # generate (resumable), then write files

Stage 1 (plan): seeded and deterministic - repos, historical jobs, proposal styles, bids, outcomes.
Stage 2 (write): LLM tasks on Groq, two models in parallel, each result cached by prompt hash in
                 data/processed/persona_gen/, so a stopped run resumes without re-paying.
Stage 3 (assemble + check): files under data/personas/<id>/ and a manifest with trap checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv

from pipelines.build_world import PERSONAS, coverage, load_persona, real_skills
from pipelines.parsing import normalise_for_dedup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/processed/persona_gen"
SEED = 404
PROPOSALS_PER_PERSONA = 150
GROQ = "https://api.groq.com/openai/v1"
BIG, SMALL = "openai/gpt-oss-120b", "openai/gpt-oss-20b"

STYLES = {  # share, outcome odds (won, replied, ignored), word range
    "strong": (0.30, (0.30, 0.35, 0.35), "120-200"),
    "plain_specific": (0.20, (0.20, 0.35, 0.45), "60-110"),
    "polished_generic": (0.25, (0.03, 0.12, 0.85), "150-220"),
    "generic": (0.25, (0.01, 0.06, 0.93), "60-100"),
}
STYLE_GUIDE = {
    "strong": "Open on the client's specific problem. Cite the given project(s) by what was built and "
              "the real result. Briefly say how you would approach this job. Confident, concrete, no fluff.",
    "plain_specific": "Short and plain, slightly awkward English is fine. Mention the one given project "
                      "and its result in a sentence. No sales language.",
    "polished_generic": "Fluent, enthusiastic and polished, full of phrases like 'leverage', 'end-to-end', "
                        "'cutting-edge', 'passionate'. Sounds impressive but gives NO specific project, "
                        "number or detail about this job.",
    "generic": "A copy-paste template that could be sent to any job: greeting, 'I have read your job "
               "description', years of experience, 'please message me'. No specifics.",
}


# --- Stage 1: plan ------------------------------------------------------------------------

def _pack_prefixes() -> set[str]:
    """First 150 normalised characters of every GigSim job, to keep past proposals off them."""
    files = [ROOT / "gigsim/scenarios/dev/jobs.jsonl", ROOT / "gigsim/scenarios/live/jobs.jsonl",
             ROOT / "data/processed/scenarios/test/jobs.jsonl"]
    out = set()
    for f in files:
        # split("\n"), not splitlines(): job text can contain U+2028, which splitlines() breaks on.
        for line in f.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            out.add(normalise_for_dedup(json.loads(line)["description"])[:150])
    return out


def _repo_projects(sk: dict, rng) -> list[str]:
    must = [p["id"] for p in sk["projects"]
            if any(t.startswith("code_only") or t in ("implied_named_differently", "three_descriptions")
                   for t in p["traps"])]
    others = [p["id"] for p in sorted(sk["projects"], key=lambda p: -p["year"]) if p["id"] not in must]
    extra = max(0, 5 - len(must))
    return (must + others[:extra])[:7]


def _bid(job, sk, rng, overpriced: bool) -> float:
    bmin, bmax = job["budget_min"], job["budget_max"]
    if job["payment_type"] == "hourly":
        if overpriced and bmax:
            return round(bmax * rng.uniform(1.3, 1.6))
        base = sk["hourly_rate"]
        if bmax:
            base = min(max(base, bmin or bmax), bmax)
        return float(round(base))
    if overpriced and bmax:
        return round(bmax * rng.uniform(1.3, 1.6), -1)
    return round((bmax or sk["min_fixed_budget"] * 3) * rng.uniform(0.8, 1.05), -1)


def plan() -> dict:
    rng = np.random.default_rng(SEED)
    jobs = pd.read_parquet(ROOT / "data/processed/jobs.parquet")
    taken = _pack_prefixes()
    jobs = jobs[~jobs["description"].map(lambda d: normalise_for_dedup(d)[:150] in taken)]
    jobs = jobs[jobs["natural_dup_of"].isna() & (jobs["description"].str.len() >= 150)
                & jobs["required_skills"].map(lambda s: len(real_skills(s)) > 0)]
    used: set[str] = set()
    out = {}
    for pid in PERSONAS:
        sk = yaml.safe_load((ROOT / f"data/personas/{pid}/skeleton.yaml").read_text(encoding="utf-8"))
        persona = load_persona(pid)
        projects = {p["id"]: p for p in sk["projects"]}
        cand = jobs[jobs["category"].isin(sk["categories"]) & ~jobs["job_id"].isin(used)].copy()
        cand["cov"] = cand["required_skills"].map(lambda s, p=persona: coverage(s, p))
        good = cand[cand["cov"] >= 0.5].sample(n=105, random_state=int(rng.integers(2**31)))
        weak = cand[(cand["cov"] >= 0.25) & (cand["cov"] < 0.5)].sample(n=45, random_state=int(rng.integers(2**31)))
        picked = pd.concat([good, weak]).sample(frac=1, random_state=int(rng.integers(2**31)))
        used.update(picked["job_id"])

        names = list(STYLES)
        shares = [STYLES[s][0] for s in names]
        proposals = []
        for i, job in enumerate(picked.to_dict("records")):
            for k in ("budget_min", "budget_max"):  # NaN is truthy; make "no budget" explicit
                job[k] = None if pd.isna(job[k]) else float(job[k])
            style = str(rng.choice(names, p=shares))
            want = set(real_skills(job["required_skills"]))
            ranked = sorted(sk["projects"], key=lambda p: (-len(want & set(p["skills"] + p["implied"])), -p["year"]))
            n_cite = {"strong": 2, "plain_specific": 1}.get(style, 0)
            cited = [p["id"] for p in ranked[:n_cite]]
            overpriced = bool(job["budget_max"]) and rng.random() < 0.15
            won, replied, _ = STYLES[style][1]
            outcome = str(rng.choice(["won", "replied", "ignored"], p=[won, replied, 1 - won - replied]))
            if overpriced and rng.random() < 0.7:
                outcome = "ignored"
            proposals.append({
                "proposal_id": f"{pid}-pp{i + 1:03d}", "style": style, "cited_projects": cited,
                "job_id": job["job_id"], "job_title": job["title"],
                "job_excerpt": job["description"][:350], "category": job["category"],
                "payment_type": job["payment_type"], "budget_min": job["budget_min"],
                "budget_max": job["budget_max"], "bid": _bid(job, sk, rng, overpriced),
                "overpriced": overpriced, "outcome": outcome,
            })
        # Every three_descriptions project must be cited by at least two proposals.
        for p in sk["projects"]:
            if "three_descriptions" not in p["traps"]:
                continue
            have = sum(p["id"] in pp["cited_projects"] for pp in proposals)
            pool = [pp for pp in proposals if pp["style"] in ("strong", "plain_specific")
                    and p["id"] not in pp["cited_projects"]]
            for pp in pool[: max(0, 2 - have)]:
                pp["cited_projects"] = [p["id"], *pp["cited_projects"]][: 2 if pp["style"] == "strong" else 1]
        # Dates: after every cited project's year.
        for pp in proposals:
            year = max([projects[c]["year"] for c in pp["cited_projects"]] + [2021])
            year = int(min(2025, year + rng.integers(0, 2)))
            pp["date"] = f"{year}-{int(rng.integers(1, 13)):02d}-{int(rng.integers(1, 28)):02d}"
        out[pid] = {"repos": _repo_projects(sk, rng), "proposals": proposals}
    return out


# --- Stage 2: LLM tasks --------------------------------------------------------------------

@dataclass
class Task:
    id: str
    model: str
    system: str
    user: str
    forbidden: list[str] = field(default_factory=list)   # words that must not appear in the output
    expect_ids: list[str] = field(default_factory=list)  # proposal ids the answer must contain


def _facts(p: dict) -> str:
    return (f"Title: {p['title']}\nYear: {p['year']}\nClient industry: {p['client_industry']}\n"
            f"Skills used (may be named): {', '.join(p['skills'])}\nResult: {p['outcome']}")


def _trap_rules(p: dict) -> tuple[str, list[str]]:
    code_only = [t.split(":", 1)[1] for t in p["traps"] if t.startswith("code_only:")]
    indirect = [s for s in p["implied"] if s not in code_only]
    rules, forbidden = [], []
    if indirect:
        rules.append("These technologies were used but must NEVER be named; describe what they did "
                     f"in plain words instead: {', '.join(indirect)}.")
        forbidden += indirect
    if code_only:
        rules.append(f"Do not mention or hint at these at all: {', '.join(code_only)}.")
        forbidden += code_only
    return " ".join(rules), forbidden


def tasks_for(pid: str, sk: dict, pl: dict) -> list[Task]:
    who = f"{sk['name']}, {sk['headline']}"
    projects = {p["id"]: p for p in sk["projects"]}
    out = []
    for p in sk["projects"]:
        rules, forbidden = _trap_rules(p)
        out.append(Task(
            f"{pid}:case:{p['id']}", BIG,
            "You write portfolio case studies for a freelancer. Write only from the given facts; "
            "never invent clients' names, extra numbers or technologies. Reply in JSON.",
            f"Freelancer: {who}\n\nPROJECT\n{_facts(p)}\n\nRules: {rules or 'none'}\n"
            "Write a 250-400 word Markdown case study with the sections '## Context', '## What I built', "
            "'## Results'. Start with '# ' and a title"
            + (" that does NOT reuse the project title above (rephrase it)" if "three_descriptions" in p["traps"] else "")
            + '.\nReturn {"markdown": "..."}', forbidden))
    for rid in pl["repos"]:
        p = projects[rid]
        code_only = [t.split(":", 1)[1] for t in p["traps"] if t.startswith("code_only:")]
        out.append(Task(
            f"{pid}:readme:{rid}", BIG,
            "You write README files for a freelancer's GitHub repositories. Reply in JSON.",
            f"PROJECT\n{_facts(p)}\nOther technologies used: {', '.join(p['implied']) or 'none'}\n\n"
            "Invent a short lowercase code name for the repo (not the project title). Write a 150-300 word "
            "technical README (what it does, architecture, how to run). Describe it in engineering terms, "
            "not marketing terms; use the code name, never the project title."
            + (f" Do not mention: {', '.join(code_only)}." if code_only else "")
            + '\nReturn {"repo_name": "...", "readme": "..."}', code_only))
        out.append(Task(
            f"{pid}:code:{rid}", SMALL,
            "You write small, realistic source files for a portfolio repository. Reply in JSON.",
            f"PROJECT\n{_facts(p)}\nTechnologies the code must visibly use (imports, config or queries): "
            f"{', '.join(p['implied'] + p['skills'][:2])}\n\n"
            "Write 1-2 files, 30-80 lines each, that look like real code from this project. No secrets.\n"
            'Return {"files": [{"path": "...", "content": "..."}]}'))
    rated = [p for p in sk["projects"] if p["rating"] is not None]
    lines = "\n".join(f"- {p['id']}: {p['title']} ({p['client_industry']}, rating {p['rating']}): {p['outcome']}"
                      for p in rated)
    out.append(Task(
        f"{pid}:reviews", SMALL,
        "You write short client reviews left on a freelance marketplace. Reply in JSON.",
        f"Freelancer: {sk['name']}\nProjects:\n{lines}\n\nWrite one review per project, 1-3 sentences, in the "
        "client's voice, matching the rating (5.0 = glowing, 4.5 = good with a small complaint). Do not name "
        "specific technologies.\nReturn {\"reviews\": [{\"project_id\": \"...\", \"text\": \"...\"}]}"))
    props = pl["proposals"]
    for b in range(0, len(props), 6):
        batch = props[b:b + 6]
        items, forbidden = [], []
        for pp in batch:
            cites = []
            for c in pp["cited_projects"]:
                p = projects[c]
                rules, fb = _trap_rules(p)
                forbidden += fb
                how = ("describe it from the client's point of view (their problem and the result) and do NOT use "
                       "its title" if "three_descriptions" in p["traps"] else "refer to it naturally")
                cites.append(f"{p['title']} ({p['year']}, {p['client_industry']}): {p['outcome']}. Skills: "
                             f"{', '.join(p['skills'])}. {rules} Mention it: {how}.")
            unit = "/hr" if pp["payment_type"] == "hourly" else " fixed"
            items.append(f"ID {pp['proposal_id']} | STYLE {pp['style']} ({STYLES[pp['style']][2]} words): "
                         f"{STYLE_GUIDE[pp['style']]}\nJOB: {pp['job_title']}\n{pp['job_excerpt']}\n"
                         f"BID: ${pp['bid']:.0f}{unit}\nPROJECTS TO CITE: {' | '.join(cites) or 'none'}")
        out.append(Task(  # alternate models so both rate limits are used
            f"{pid}:proposals:{b // 6:02d}", SMALL if (b // 6) % 2 == 0 else BIG,
            f"You write Upwork proposals as {who}. Only use the facts given; never invent employers, "
            "certifications, years or results. Reply in JSON.",
            "Write one proposal for each item below, in the requested style and length.\n\n"
            + "\n\n---\n\n".join(items)
            + '\n\nReturn {"proposals": [{"id": "...", "text": "..."}]}', sorted(set(forbidden)),
            [pp["proposal_id"] for pp in batch]))
    return out


def _cache_path(task: Task, nonce: int) -> Path:
    h = hashlib.sha256(json.dumps([task.model, task.system, task.user, nonce]).encode()).hexdigest()[:16]
    return CACHE / f"{task.id.replace(':', '__')}__{h}.json"


def _violations(output: dict, forbidden: list[str]) -> list[str]:
    text = json.dumps(output).lower()
    return [w for w in forbidden if re.search(rf"(?<![a-z0-9]){re.escape(w.lower())}(?![a-z0-9])", text)]


class Runner:
    def __init__(self):
        self.key = os.environ["GROQ_API_KEY"]
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.log: list[str] = []

    def call(self, task: Task, nonce: int) -> dict:
        body = {"model": task.model, "temperature": 0.7, "reasoning_effort": "low",
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": task.system},
                             {"role": "user", "content": task.user + (f"\n(variant {nonce})" if nonce else "")}]}
        for attempt in range(10):
            r = httpx.post(f"{GROQ}/chat/completions", json=body, timeout=180,
                           headers={"Authorization": f"Bearer {self.key}"})
            if r.status_code == 429:
                wait = float(r.headers.get("retry-after", 10))
                if wait > 300:  # daily limit: stop this model, resume later
                    raise RuntimeError(f"daily limit for {task.model} (retry in {wait / 3600:.1f} h)")
                time.sleep(wait + 0.5)
                continue
            if r.status_code >= 500 or (r.status_code == 400 and "json" in r.text.lower()):
                time.sleep(2 ** min(attempt, 5))
                continue
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        raise RuntimeError(f"{task.id}: no answer after retries")

    def run_task(self, task: Task) -> dict | None:
        for nonce in range(3):  # retry with a variant if forbidden words slipped in
            path = _cache_path(task, nonce)
            if path.exists():
                out = json.loads(path.read_text(encoding="utf-8"))
            else:
                out = self.call(task, nonce)
                path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            got = {x.get("id") for x in out.get("proposals", []) if isinstance(x, dict)}
            if task.expect_ids and not set(task.expect_ids) <= got:
                continue  # incomplete batch: try a variant
            if not _violations(out, task.forbidden):
                return out
        with self.lock:
            self.log.append(f"{task.id}: forbidden words remain after 3 tries {_violations(out, task.forbidden)}")
        return out

    def run_all(self, tasks: list[Task]) -> dict[str, dict]:
        CACHE.mkdir(parents=True, exist_ok=True)
        results: dict[str, dict] = {}
        queues = {BIG: queue.Queue(), SMALL: queue.Queue()}
        for t in tasks:
            queues[t.model].put(t)
        total = len(tasks)

        def worker(model):
            while not queues[model].empty():
                t = queues[model].get()
                try:
                    out = self.run_task(t)
                except Exception as exc:  # noqa: BLE001 - report and keep the other model going
                    with self.lock:
                        self.log.append(f"{t.id}: {exc}")
                    if "daily limit" in str(exc):
                        return
                    continue
                with self.lock:
                    results[t.id] = out
                    print(f"[{len(results)}/{total}] {t.id}", flush=True)

        threads = [threading.Thread(target=worker, args=(m,)) for m in queues]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        return results


# --- Stage 3: assemble + check ---------------------------------------------------------------

def write_cv(pid: str, sk: dict) -> None:
    from fpdf import FPDF

    d = ROOT / f"data/personas/{pid}"
    lines = [f"# {sk['name']}", f"**{sk['headline']}**", (f"{sk['location']} · {sk['years_experience']} years "
             f"experience · ${sk['hourly_rate']}/hr"), "", "_Synthetic persona for the GigBid assignment._", "",
             "## Skills", ", ".join(sk["listed_skills"]), "", "## Selected projects"]
    for p in sorted(sk["projects"], key=lambda p: -p["year"]):
        lines.append(f"- **{p['title']}** ({p['year']}, {p['client_industry']}): {p['outcome']}")
    (d / "cv.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    pdf = FPDF()
    pdf.set_creation_date(pd.Timestamp("2026-11-15").to_pydatetime())
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, sk["name"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    for text in (sk["headline"], (f"{sk['location']} - {sk['years_experience']} years experience - "
                 f"${sk['hourly_rate']}/hr"), "Synthetic persona for the GigBid assignment."):
        pdf.multi_cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Skills", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5, ", ".join(sk["listed_skills"]), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 8, "Selected projects", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for p in sorted(sk["projects"], key=lambda p: -p["year"]):
        pdf.multi_cell(0, 5, f"- {p['title']} ({p['year']}, {p['client_industry']}): {p['outcome']}",
                       new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(d / "cv.pdf"))


def assemble(pid: str, sk: dict, pl: dict, results: dict[str, dict], log: list[str]) -> dict:
    d = ROOT / f"data/personas/{pid}"
    projects = {p["id"]: p for p in sk["projects"]}
    write_cv(pid, sk)
    (d / "case_studies").mkdir(parents=True, exist_ok=True)
    n_case = 0
    for p in sk["projects"]:
        r = results.get(f"{pid}:case:{p['id']}")
        if r:
            md = f"<!-- project_id: {p['id']} | synthetic -->\n{r['markdown'].strip()}\n"
            (d / "case_studies" / f"{p['id']}.md").write_text(md, encoding="utf-8", newline="\n")
            n_case += 1
    repos = {}
    for rid in pl["repos"]:
        readme, code = results.get(f"{pid}:readme:{rid}"), results.get(f"{pid}:code:{rid}")
        if not readme:
            continue
        name = re.sub(r"[^a-z0-9-]+", "-", readme["repo_name"].lower()).strip("-") or rid
        rd = d / "repos" / name
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "README.md").write_text(readme["readme"].strip() + "\n", encoding="utf-8", newline="\n")
        files = (code or {}).get("files", [])
        if isinstance(files, dict):  # some answers use {"path": "content"} instead of a list
            files = [{"path": p, "content": c} for p, c in files.items()]
        for f in files:
            if not isinstance(f, dict) or "path" not in f or "content" not in f:
                continue
            rel = Path(*[part for part in Path(f["path"]).parts if part not in ("..", "/", "\\")])
            (rd / rel).parent.mkdir(parents=True, exist_ok=True)
            (rd / rel).write_text(f["content"].rstrip() + "\n", encoding="utf-8", newline="\n")
        (rd / ".project.json").write_text(json.dumps({"project_id": rid, "synthetic": True}) + "\n",
                                          encoding="utf-8", newline="\n")
        repos[rid] = name
    reviews = (results.get(f"{pid}:reviews") or {}).get("reviews", [])
    with (d / "reviews.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in reviews:
            if r.get("project_id") in projects:
                p = projects[r["project_id"]]
                f.write(json.dumps({"project_id": p["id"], "rating": p["rating"], "client_industry":
                                    p["client_industry"], "year": p["year"], "text": r["text"],
                                    "synthetic": True}, ensure_ascii=False) + "\n")
    texts = {}
    for key, r in results.items():
        if key.startswith(f"{pid}:proposals:"):
            texts.update({x["id"]: x["text"] for x in r.get("proposals", []) if "id" in x})
    notes = {"won": "Hired; contract completed.", "replied": "Client replied but did not hire.",
             "ignored": "No response from the client."}
    written = 0
    with (d / "past_proposals.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for pp in pl["proposals"]:
            if pp["proposal_id"] not in texts:
                continue
            rec = {k: pp[k] for k in ("proposal_id", "date", "job_title", "job_excerpt", "category", "bid",
                                      "cited_projects", "style", "overpriced", "outcome")}
            rec.update({"budget": {"min": pp["budget_min"], "max": pp["budget_max"],
                                   "type": pp["payment_type"]},
                        "text": texts[pp["proposal_id"]], "outcome_note": notes[pp["outcome"]],
                        "synthetic": True})
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    # Checks
    checks = []
    for p in sk["projects"]:
        code_only = [t.split(":", 1)[1] for t in p["traps"] if t.startswith("code_only:")]
        cs = d / "case_studies" / f"{p['id']}.md"
        if cs.exists() and code_only:
            bad = _violations({"t": cs.read_text(encoding="utf-8")}, code_only)
            checks.append({"check": f"{p['id']} case study omits {code_only}", "ok": not bad})
        if code_only and p["id"] in repos:
            src = " ".join(x.read_text(encoding="utf-8", errors="ignore").lower()
                           for x in (d / "repos" / repos[p["id"]]).rglob("*") if x.is_file() and x.name != "README.md")
            checks.append({"check": f"{p['id']} code shows {code_only}",
                           "ok": all(c.lower().split()[0] in src for c in code_only)})
        if "three_descriptions" in p["traps"]:
            cites = sum(p["id"] in pp["cited_projects"] and pp["proposal_id"] in texts for pp in pl["proposals"])
            checks.append({"check": f"{p['id']} described three ways (case study, README, >=2 proposals)",
                           "ok": cs.exists() and p["id"] in repos and cites >= 2})
    out = pd.Series([pp["outcome"] for pp in pl["proposals"] if pp["proposal_id"] in texts]).value_counts().to_dict()
    manifest = {
        "persona": pid, "synthetic": True, "seed": SEED, "models": {"long_form": BIG, "short_form": SMALL},
        "counts": {"case_studies": n_case, "repos": len(repos), "reviews": len(reviews),
                   "past_proposals": written},
        "outcomes": out, "repos": repos, "checks": checks,
        "checks_passed": f"{sum(c['ok'] for c in checks)}/{len(checks)}",
        "generation_log": [line for line in log if line.startswith(pid)],
    }
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    pl = plan()
    skeletons = {pid: yaml.safe_load((ROOT / f"data/personas/{pid}/skeleton.yaml").read_text(encoding="utf-8"))
                 for pid in PERSONAS}
    tasks = [t for pid in PERSONAS for t in tasks_for(pid, skeletons[pid], pl[pid])]
    if args.plan_only:
        for pid in PERSONAS:
            props = pd.DataFrame(pl[pid]["proposals"])
            print(pid, "repos:", pl[pid]["repos"])
            print("  styles:", props["style"].value_counts().to_dict(),
                  "outcomes:", props["outcome"].value_counts().to_dict(),
                  "overpriced:", int(props["overpriced"].sum()))
        print("tasks:", pd.Series([t.model for t in tasks]).value_counts().to_dict(),
              "approx prompt tokens:", sum(len(t.system) + len(t.user) for t in tasks) // 4)
        return
    runner = Runner()
    results = runner.run_all(tasks)
    for pid in PERSONAS:
        m = assemble(pid, skeletons[pid], pl[pid], results, runner.log)
        print(json.dumps({k: m[k] for k in ("persona", "counts", "outcomes", "checks_passed")}))
    for line in runner.log:
        print("LOG", line)


if __name__ == "__main__":
    main()
