"""Retrieval evaluation (assignment B4): Recall@5, MRR and nDCG@10 against gold evidence, per variant,
per persona, and for jobs with four or more requirements.

  python -m evals.runners.rag_eval                          # all cheap variants, every bid job
  python -m evals.runners.rag_eval --variants v8_corrective --limit 20   # LLM-heavy variant on a subset
  python -m evals.runners.rag_eval --variants v1_v2_v3 --ablate v1_v2_v3  # best, then best minus each part

Gold evidence is at project level (data/personas/<p>/skeleton.yaml projects), so retrieved chunks are
mapped to their project and de-duplicated in rank order before scoring. Writes
evals/results/rag_eval.json and evals/results/rag_eval.csv (merged with earlier variants' rows).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

from rag.retriever import VARIANTS, Retriever
from rag.variants.v1_decompose import requirements

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals/results"
PERSONAS = ("ml_engineer", "fullstack_dev", "data_analyst")
CHEAP = ["v0_naive", "v1_decompose", "v2_hybrid", "v3_rerank", "v4_outcome", "v1_v2_v3"]


def projects_in_order(results) -> list[str]:
    seen, out = set(), []
    for chunk, _ in results:
        p = chunk.doc.project_id
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def recall_at(ranked: list[str], gold: set[str], k: int) -> float:
    return len(set(ranked[:k]) & gold) / len(gold)


def mrr(ranked: list[str], gold: set[str]) -> float:
    return next((1 / (i + 1) for i, p in enumerate(ranked) if p in gold), 0.0)


def ndcg_at(ranked: list[str], gold: set[str], k: int) -> float:
    dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(ranked[:k]) if p in gold)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / ideal if ideal else 0.0


def load(persona: str):
    jobs = {j["job_id"]: j for j in map(json.loads, (ROOT / "gigsim/scenarios/dev/jobs.jsonl").open(encoding="utf-8"))}
    labels = [r for r in map(json.loads, (ROOT / "evals/datasets/dev/labels.jsonl").open(encoding="utf-8"))
              if r["persona"] == persona]
    bid = [(jobs[r["job_id"]], set(r["gold_evidence"])) for r in labels if r["bid"] and r["gold_evidence"]]
    skip = [jobs[r["job_id"]] for r in labels if r["skip_reason"] in ("out_of_category", "low_skill_coverage")]
    return bid, skip


def options(variant: str) -> dict:
    """'v1_v2_v3' -> its config; 'v1_v2_v3-rerank' -> the same with one component removed (ablation)."""
    base, *drop = variant.split("-")
    opts = dict(VARIANTS[base])
    for component in drop:
        if component not in opts:
            raise SystemExit(f"{base} has no component {component!r} (has {sorted(opts)})")
        del opts[component]
    return opts


def ablations(base: str) -> list[str]:
    return [f"{base}-{c}" for c in VARIANTS[base]]


def evaluate(variant: str, limit: int | None, embedder: str) -> list[dict]:
    rows, opts = [], options(variant)
    for persona in PERSONAS:
        bid, skip = load(persona)
        if limit:
            bid, skip = bid[:limit], skip[: max(1, limit // 2)]
        r = Retriever(ROOT / "data/personas" / persona, variant, embedder, ROOT / "data/processed/rag_cache",
                      options=opts)
        per_job, latencies = [], []
        for job, gold in bid:
            t = time.time()
            ranked = projects_in_order(r.impl.retrieve_job(job, k=20))
            latencies.append(time.time() - t)
            per_job.append({"job_id": job["job_id"], "recall5": recall_at(ranked, gold, 5), "mrr": mrr(ranked, gold),
                            "ndcg10": ndcg_at(ranked, gold, 10), "many_reqs": len(requirements(job)) >= 5})
        row = {"variant": variant, "persona": persona, "jobs": len(per_job)}
        for key in ("recall5", "mrr", "ndcg10"):
            row[key] = round(statistics.mean(j[key] for j in per_job), 3)
        many = [j for j in per_job if j["many_reqs"]]
        row["recall5_4plus_reqs"] = round(statistics.mean(j["recall5"] for j in many), 3) if many else None
        row["latency_p50_s"] = round(statistics.median(latencies), 3)
        row["latency_p95_s"] = round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 3)
        if opts.get("corrective"):   # refusal: no evidence returned for a job to skip
            refused = sum(1 for job in skip if not r.impl.retrieve_job(job, k=5))
            row["refusal_rate_skip_jobs"] = round(refused / len(skip), 3)
        print(json.dumps(row), flush=True)
        row["per_job"] = [{k: round(v, 4) if isinstance(v, float) else v for k, v in j.items()} for j in per_job]
        rows.append(row)
    return rows


def paired_ci(rows: list[dict], variant: str, base: str = "v0_naive", key: str = "recall5",
              n_boot: int = 2000, seed: int = 0) -> list[float] | None:
    """95% paired-bootstrap interval of mean(variant - base) over the jobs both were run on, in points."""
    def scores(v):
        return {(r["persona"], j["job_id"]): j[key] for r in rows if r["variant"] == v for j in r.get("per_job", [])}
    a, b = scores(variant), scores(base)
    diffs = [a[k] - b[k] for k in sorted(a.keys() & b.keys())]   # sorted: set order varies per process
    if len(diffs) < 10:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(n_boot))
    return [round(100 * means[int(0.025 * n_boot)], 1), round(100 * means[int(0.975 * n_boot) - 1], 1)]


def summarise(rows: list[dict]) -> list[dict]:
    """Macro-average over personas per variant, plus the paired 95% CI of the Recall@5 change vs V0."""
    out = []
    for v in dict.fromkeys(r["variant"] for r in rows):
        vr = [r for r in rows if r["variant"] == v]
        s = {"variant": v, "persona": "all", "jobs": sum(r["jobs"] for r in vr)}
        for key in ("recall5", "mrr", "ndcg10", "recall5_4plus_reqs", "latency_p50_s", "latency_p95_s",
                    "refusal_rate_skip_jobs"):
            vals = [r[key] for r in vr if r.get(key) is not None]
            if vals:
                s[key] = round(statistics.mean(vals), 3)
        if v != "v0_naive":
            s["delta_recall5_ci95_pts"] = paired_ci(rows, v)
        out.append(s)
    return out


def main() -> None:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", nargs="+", default=CHEAP)
    ap.add_argument("--ablate", help="also run this variant with each component removed in turn")
    ap.add_argument("--limit", type=int, default=None, help="max bid jobs per persona")
    ap.add_argument("--embedder", default="ollama:nomic-embed-text")
    ap.add_argument("--out", type=Path, default=RESULTS / "rag_eval.json", help="CI smoke runs write elsewhere")
    a = ap.parse_args()
    out = a.out
    names = a.variants + (ablations(a.ablate) if a.ablate else [])
    fresh = []
    for v in names:
        fresh += evaluate(v, a.limit, a.embedder)
    # Read earlier rows only now, so two runs of different variants can overlap without losing rows.
    previous = json.loads(out.read_text(encoding="utf-8"))["by_persona"] if out.exists() else []
    rows = [r for r in previous if r["variant"] not in names] + fresh
    summary = summarise(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"embedder": a.embedder, "summary": summary, "by_persona": rows}, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    keys = ["variant", "persona", "jobs", "recall5", "mrr", "ndcg10", "recall5_4plus_reqs", "latency_p50_s",
            "latency_p95_s", "refusal_rate_skip_jobs"]
    with out.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(summary + rows)
    print("\nSUMMARY")
    for s in summary:
        print(f"{s['variant']:<14} R@5 {s['recall5']:.3f}  MRR {s['mrr']:.3f}  nDCG@10 {s['ndcg10']:.3f}  "
              f"R@5(5+ reqs) {s.get('recall5_4plus_reqs', 0):.3f}  p95 {s['latency_p95_s']:.2f}s")


if __name__ == "__main__":
    main()
