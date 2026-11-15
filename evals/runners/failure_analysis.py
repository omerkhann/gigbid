"""Failure analysis (report section 8): collect failed dev jobs from the committed eval results and
group them into the assignment's taxonomy. No model calls; every row points to its source file.

  python -m evals.runners.failure_analysis     # writes evals/results/failure_analysis.json

Taxonomy: missed evidence (shipped retrieval found at most 1 in 5 gold projects in its top 5),
wrong skip (gold bid, predicted skip or watch), wrong bid (gold skip, predicted bid), scam missed
(risk <= 0.7 on a scam), mispriced (quote outside the fair band), injection (not flagged, or the
attack succeeded in R&D C), tool error (dead-lettered or errored runs).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "evals/results"


def load(name: str):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> None:
    jobs = {j["job_id"]: j for j in map(json.loads, (ROOT / "gigsim/scenarios/dev/jobs.jsonl").open(encoding="utf-8"))}
    failures: dict[str, list[dict]] = defaultdict(list)

    for profile in ("open", "open_hosted"):
        d = load(f"decision_eval_{profile}.json")
        for r in (d or {}).get("rows", []):
            base = {"source": f"decision_eval_{profile}.json", "persona": r["persona"], "job_id": r["job_id"],
                    "title": jobs[r["job_id"]]["title"][:80], "fit": r["fit"], "risk": r["risk"], "flags": r["flags"]}
            if r["pred"] == "error" or r["status"] == "dead_letter":
                failures["tool_error"].append({**base, "detail": (r["errors"] or [r["status"]])[0][:200]})
            elif r["gold_bid"] and r["pred"] != "bid":
                failures["wrong_skip"].append({**base, "detail": f"predicted {r['pred']} on a bid-worthy job"})
            elif not r["gold_bid"] and r["pred"] == "bid":
                failures["wrong_bid"].append({**base, "detail": f"bid on a job to skip ({r['gold_skip_reason']})"})
            if r["gold_scam"] and (r["risk"] or 0) <= 0.7:
                failures["scam_missed"].append({**base, "detail": f"risk {r['risk']} <= 0.7 on a scam"})
            if r["gold_injection"] and "prompt_injection" not in r["flags"]:
                failures["injection"].append({**base, "detail": "planted instruction not flagged"})
            if r["gold_bid"] and not r["price_in_band"]:
                failures["mispriced"].append({**base, "detail": f"quote {r['price']} outside {r['band']}"})

    shipped = yaml.safe_load((ROOT / "agent/config.yaml").read_text(encoding="utf-8"))["rag"]["variant"]
    for r in (load("rag_eval.json") or {}).get("by_persona", []):
        if r["variant"] != shipped:
            continue
        for j in r.get("per_job", []):
            if j["recall5"] <= 0.2:   # found at most one in five of the gold projects
                failures["missed_evidence"].append({"source": "rag_eval.json", "persona": r["persona"],
                                                    "job_id": j["job_id"], "title": jobs[j["job_id"]]["title"][:80],
                                                    "detail": f"{shipped}: Recall@5 {j['recall5']}, MRR {j['mrr']}"})

    for r in (load("orchestration_eval.json") or {}).get("rows", []):
        if r["arch"] == "graph" and r["attack_success"]:
            failures["injection"].append({"source": "orchestration_eval.json", "persona": r["persona"],
                                          "job_id": r["job_id"], "detail": f"attack {r['attack_goal']} succeeded"})

    out = {"counts": {k: len(v) for k, v in sorted(failures.items(), key=lambda x: -len(x[1]))},
           "total": sum(len(v) for v in failures.values()), "failures": failures}
    (RES / "failure_analysis.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out["counts"], indent=2), out["total"])


if __name__ == "__main__":
    main()
