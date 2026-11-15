"""Retrieval results by job type (marketplace category) and by requirement count, V0 vs the shipped
variant, from the per-job scores in evals/results/rag_eval.json. No model calls.

  python -m evals.runners.rag_breakdown      # writes evals/results/rag_breakdown.json
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    data = json.loads((ROOT / "evals/results/rag_eval.json").read_text(encoding="utf-8"))
    shipped = yaml.safe_load((ROOT / "agent/config.yaml").read_text(encoding="utf-8"))["rag"]["variant"]
    jobs = {j["job_id"]: j for j in map(json.loads, (ROOT / "gigsim/scenarios/dev/jobs.jsonl").open(encoding="utf-8"))}
    scores: dict[str, dict] = defaultdict(dict)
    for r in data["by_persona"]:
        if r["variant"] in ("v0_naive", shipped):
            for j in r.get("per_job", []):
                scores[r["variant"]][(r["persona"], j["job_id"])] = j
    common = scores["v0_naive"].keys() & scores[shipped].keys()

    def group(keyfn) -> list[dict]:
        groups = defaultdict(list)
        for k in common:
            groups[keyfn(k)].append(k)
        rows = []
        for g, ks in sorted(groups.items(), key=lambda x: -len(x[1])):
            v0 = statistics.mean(scores["v0_naive"][k]["recall5"] for k in ks)
            sh = statistics.mean(scores[shipped][k]["recall5"] for k in ks)
            rows.append({"group": g, "jobs": len(ks), "v0_recall5": round(v0, 3), f"{shipped}_recall5": round(sh, 3),
                         "delta_pts": round(100 * (sh - v0), 1)})
        return rows

    out = {"shipped": shipped, "jobs": len(common),
           "by_job_type": group(lambda k: jobs[k[1]].get("category", "unknown")),
           "by_requirement_count": group(lambda k: "5+ requirements" if scores[shipped][k]["many_reqs"] else "under 5"),
           "by_persona": group(lambda k: k[0])}
    (ROOT / "evals/results/rag_breakdown.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
