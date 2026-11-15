"""Evaluation of the signature extension X3 (portfolio builder from repositories).

  python -m evals.runners.x3_eval --personas ml_engineer

Builds case studies from a persona's repos only (data/personas/<p>/repos), exactly as it would from a
GitHub account, then measures against the persona's ground truth (skeleton.yaml):
- claims: share supported / unsupported before verification, and how many were removed;
- named-skill recall: project skills the generated case study mentions;
- implied-skill recall: skills the project uses but its hand-written profile never names (the
  corpus's "implied" trap), the reason to generate case studies from code at all.
Writes evals/results/x3_eval.json; the generated folders go to data/processed/x3/<persona>.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def mentioned(skill: str, text: str) -> bool:
    s = skill.lower().replace("python ", "")
    return s in text.lower()


def evaluate(persona: str) -> dict:
    from rag.ingest.portfolio_builder import build, local_repos

    sk = yaml.safe_load((ROOT / f"data/personas/{persona}/skeleton.yaml").read_text(encoding="utf-8"))
    truth = {p["id"]: p for p in sk["projects"]}
    out = ROOT / "data/processed/x3" / persona
    report = build(local_repos(ROOT / f"data/personas/{persona}/repos"), out, profile_name=f"{persona} (from repos)")
    rows = []
    for r in report:
        t = truth.get(r["project_id"], {})
        text = " ".join([r["body_after"], *r["skills"]])
        named, implied = t.get("skills", []), t.get("implied", [])
        rows.append({"repo": r["repo"], "project_id": r["project_id"], "claims": r["claims"],
                     "supported": r["supported"], "unsupported_removed": r["unsupported"],
                     "named_skill_recall": round(sum(mentioned(s, text) for s in named) / len(named), 3) if named else None,
                     "implied_skill_recall": round(sum(mentioned(s, text) for s in implied) / len(implied), 3) if implied else None,
                     "implied": implied, "generated_skills": r["skills"],
                     "body_before": r["body_before"], "body_after": r["body_after"]})   # what verification removed
    claims = sum(r["claims"] for r in rows)

    def avg(key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(statistics.mean(vals), 3) if vals else None
    return {"persona": persona, "repos": len(rows), "claims": claims,
            "supported_rate_before": round(sum(r["supported"] for r in rows) / claims, 3) if claims else None,
            "unsupported_rate_before": round(sum(r["unsupported_removed"] for r in rows) / claims, 3) if claims else None,
            "unsupported_after": 0,   # removed by verification before writing (see body_before/body_after)
            "named_skill_recall": avg("named_skill_recall"), "implied_skill_recall": avg("implied_skill_recall"),
            "rows": rows}


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--personas", nargs="+", default=["ml_engineer"])
    a = ap.parse_args()
    from agent.llm import chain_for

    results = [evaluate(p) for p in a.personas]
    path = ROOT / "evals/results/x3_eval.json"
    path.write_text(json.dumps({"model": chain_for("portfolio_builder")[0], "results": results}, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    print(json.dumps([{k: v for k, v in r.items() if k != "rows"} for r in results], indent=2))
