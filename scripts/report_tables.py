"""Generate the LaTeX tables of the R&D report from evals/results/*.json (no hand-copied numbers).

  python scripts/report_tables.py        # writes docs/report/tables/*.tex; then latexmk -pdf report.tex
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "evals/results"
OUT = ROOT / "docs/report/tables"
DASH = "--"


def load(name: str):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def tex(s) -> str:
    return (str(s).replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%")
            .replace("&", r"\&").replace("#", r"\#").replace("$", r"\$"))


def f(v, d: int = 3) -> str:
    if v is None:
        return DASH
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def write(name: str, cols: str, header: list[str], rows: list[list], note: str = "") -> None:
    lines = [r"\begin{tabular}{" + cols + "}", r"\toprule", " & ".join(header) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (OUT / f"{name}_note.tex").write_text(note + "\n", encoding="utf-8", newline="\n")


def shipped() -> str:
    return yaml.safe_load((ROOT / "agent/config.yaml").read_text(encoding="utf-8"))["rag"]["variant"]


LABELS = {
    "v0_naive": "V0 naive dense", "v1_decompose": "V1 decomposition", "v2_hybrid": "V2 hybrid (BM25+dense, RRF)",
    "v3_rerank": "V3 = V2 + cross-encoder", "v4_outcome": "V4 = V3 + outcome boost", "v1_v2_v3": "V1+V2+V3",
    "v1_v2_v3-decompose": "V1+V2+V3 $-$ decompose", "v1_v2_v3-hybrid": "V1+V2+V3 $-$ hybrid",
    "v1_v2_v3-rerank": "V1+V2+V3 $-$ rerank", "v4_outcome-hybrid": "V4 $-$ hybrid",
    "v4_outcome-rerank": "V4 $-$ rerank", "v4_outcome-outcome": "V4 $-$ outcome (= V3)",
    "v2_v4": r"\textbf{V2 + outcome (\texttt{v2\_v4}, shipped)}", "v8_corrective": "V8 corrective (5 jobs/persona)",
}


def rag() -> None:
    d = load("rag_eval.json")
    base = next(s for s in d["summary"] if s["variant"] == "v0_naive")
    order = ["v0_naive", "v1_decompose", "v2_hybrid", "v3_rerank", "v4_outcome", "v1_v2_v3", "v1_v2_v3-decompose",
             "v1_v2_v3-hybrid", "v1_v2_v3-rerank", "v4_outcome-hybrid", "v4_outcome-outcome", "v2_v4", "v8_corrective"]
    by = {s["variant"]: s for s in d["summary"]}
    rows = []
    for v in [v for v in order if v in by]:
        s = by[v]
        delta = DASH if v == "v0_naive" else f"{100 * (s['recall5'] - base['recall5']):+.1f}"
        ci = s.get("delta_recall5_ci95_pts")
        if ci:
            delta += f" [{ci[0]:+.1f}, {ci[1]:+.1f}]"
        rows.append([LABELS.get(v, tex(v)), str(s["jobs"]), f(s["recall5"]), delta.replace("-", "$-$").replace("$-$$-$", "--"),
                     f(s["mrr"]), f(s["ndcg10"]), f(s.get("recall5_4plus_reqs")), f(s["latency_p95_s"], 2),
                     f(s.get("refusal_rate_skip_jobs"))])
    write("rag", "lrrrrrrrr", ["Variant", "Jobs", "R@5", r"$\Delta$R@5 pts [95\% CI]", "MRR", "nDCG@10",
                               "R@5 (5+ req.)", "p95 s", "Refusal"], rows,
          r"Source: \texttt{evals/results/rag\_eval.json}; embedder \texttt{" + tex(d["embedder"]) + "}; "
          "macro-average over 3 personas; CI = paired bootstrap over jobs vs V0. "
          "Refusal = share of out-of-scope jobs for which V8 returned no evidence.")


def breakdown() -> None:
    d = load("rag_breakdown.json")
    rows = []
    for key, title in (("by_job_type", "Job type"), ("by_requirement_count", "Requirements"), ("by_persona", "Persona")):
        for r in d[key]:
            rows.append([title, tex(r["group"]), str(r["jobs"]), f(r["v0_recall5"]), f(r[f"{d['shipped']}_recall5"]),
                         f"{r['delta_pts']:+.1f}".replace("-", "$-$")])
    write("breakdown", "llrrrr", ["Split", "Group", "Jobs", "V0 R@5", "Shipped R@5", r"$\Delta$ pts"], rows,
          r"Source: \texttt{evals/results/rag\_breakdown.json}.")


def decisions() -> None:
    rows = []
    for p in ("open", "open_hosted"):
        d = load(f"decision_eval_{p}.json")
        if not d:
            continue
        o = d["overall"]
        rows.append([r"\texttt{" + tex(p) + "}", r"\texttt{" + tex(d["small_model"]) + "}", str(o["jobs"]), str(o["errors"]),
                     f(o["bid_precision"]), f(o["bid_recall"]), f(o["bid_f1"]), f(o["scam_precision"]),
                     f(o["scam_recall"]), f(o["injection_flagged"]), f(o["price_in_band"]),
                     f(o["latency_p50_s"], 1), f(o["latency_p95_s"], 1), str(o["tokens_per_job"])])
    write("decisions", "llrrrrrrrrrrrr", ["Profile", "Small tier", "Jobs", "Err", "Bid P", "Bid R", "Bid F1", "Scam P",
                                          "Scam R", "Inj. flagged", "Price in band", "p50 s", "p95 s", "Tok/job"], rows,
          r"Source: \texttt{evals/results/decision\_eval\_<profile>.json}; stratified jobs from "
          r"\texttt{subset\_60.json}; scam = risk $>0.7$.")


def orchestration() -> None:
    d = load("orchestration_eval.json")
    if not d:
        return
    names = {"graph": "GigBid graph", "single": "Single ReAct agent", "supervisor": "Prebuilt supervisor"}
    rows = [[names[a], str(s["jobs"]), str(s["errors"]), f(s["decision_accuracy"]), f(s["bid_on_scam_rate"]),
             f(s["attack_success_rate"]), f(s["unsupported_claims_per_draft"], 2), str(s["tokens_per_job"]),
             f(s["latency_p95_s"], 1), f(s["tool_calls_per_job"], 1)] for a, s in d["summary"].items()]
    write("orchestration", "lrrrrrrrrr", ["Architecture", "Jobs", "Err", "Decision acc.", "Bid on scam", "Inj. success",
                                          "Unsupp./draft", "Tok/job", "p95 s", "Tools/job"], rows,
          r"Source: \texttt{evals/results/orchestration\_eval.json}; one model for all: \texttt{" + tex(d["model"]) + "}.")


def outcomes() -> None:
    rag_s = {s["variant"]: s for s in load("rag_eval.json")["summary"]}
    rows = []
    for label, v in (("V0", "v0_naive"), ("Shipped (\\texttt{v2\\_v4})", shipped())):
        o = (load(f"gigsim_outcomes_{v}.json") or {}).get("summary", {})
        r = rag_s.get(v, {})
        rows.append([label, f(r.get("recall5")), f(r.get("ndcg10")),
                     f"{f(o.get('unsupported_claims_before'), 2)} $\\to$ {f(o.get('unsupported_claims_after'), 2)}",
                     f(o.get("judge_score"), 2), f(o.get("reply_rate"), 2), f(o.get("latency_p95_s"), 1),
                     f(o.get("usd_per_proposal"), 2), str(o.get("submitted", DASH))])
    write("headline", "lrrrrrrrr", ["Variant", "Evidence R@5", "nDCG@10", r"Unsupp. claims/prop. (before$\to$after)",
                                     "Judge (1--5)", "Reply rate", "p95 s", "USD/prop.", "Sent"], rows,
          r"Sources: \texttt{rag\_eval.json}; \texttt{gigsim\_outcomes\_<variant>.json} (proposals sent to GigSim, "
          r"LLM client).")


def x3() -> None:
    d = load("x3_eval.json")
    if not d:
        return
    rows = [[tex(r["persona"]), str(r["repos"]), str(r["claims"]), f(r["supported_rate_before"]),
             f(r["unsupported_rate_before"]), f(r["named_skill_recall"]), f(r["implied_skill_recall"])] for r in d["results"]]
    write("x3", "lrrrrrr", ["Persona", "Repos", "Claims", "Supported (before)", "Unsupported (removed)",
                            "Named-skill recall", "Implied-skill recall"], rows,
          r"Source: \texttt{evals/results/x3\_eval.json}; model \texttt{" + tex(d["model"]) + "}.")


def tools() -> None:
    d = load("tool_granularity.json")
    if not d:
        return
    names = {"fine_terse": "Fine-grained, terse descriptions", "coarse": "Coarse (2 dispatcher tools)",
             "fine_full": "Fine-grained, full descriptions (shipped)"}
    rows = [[names[k], str(s["tools_offered"]), str(s["tasks"]), f(s["tool_selection_accuracy"]),
             f(s["argument_accuracy"]), str(s["unsafe_calls"]), str(s["no_call"]), str(s["tokens_per_task"])]
            for k, s in d["summary"].items()]
    write("tools", "lrrrrrrr", ["Tool set", "Tools", "Tasks", "Tool selection", "Arguments", "Unsafe calls",
                                "No call", "Tokens/task"], rows,
          r"Source: \texttt{evals/results/tool\_granularity.json}; model \texttt{" + tex(d["model"]) + "}; "
          "unsafe = an irreversible send/submit the task did not ask for.")


def judge() -> None:
    j = load("judge_calibration.json")
    write("judge", "rrrr", ["Items", r"Quadratic-weighted $\kappa$", "Exact agreement", "Within one"],
          [[str(j["n"]), f(j["weighted_kappa"]), f(j["exact_agreement"]), f(j["within_one"])]],
          r"Source: \texttt{evals/results/judge\_calibration.json}.")


def failures() -> None:
    d = load("failure_analysis.json")
    fixes = {
        "missed_evidence": ("Hybrid BM25 + outcome boost (shipped \\texttt{v2\\_v4}); chunks start on word boundaries",
                            "Partly: $+7.3$ pts R@5 on 5+-requirement jobs; these jobs still miss"),
        "wrong_skip": ("Hosted 20B small tier instead of local 4B for fit judging (\\texttt{open\\_hosted})",
                       "Yes on the hosted profile: bid recall 0.29 $\\to$ 0.75"),
        "wrong_bid": ("Fit threshold and budget floor in \\texttt{decide}", "Not yet: needs threshold tuning on dev"),
        "scam_missed": ("Sentence-level risk rules + client-history signals", "Scam recall 1.0 on both profiles"),
        "injection": ("Untrusted-text fencing, injection rule, per-node tool allowlists", "Flagged 1.0 on both profiles"),
        "mispriced": ("Price computed from market band, clipped to budget and floor", "Price in band 1.0"),
        "tool_error": ("Critic fail-soft; \\texttt{waiting\\_marketplace} status; retries", "No dead letters in these runs"),
    }
    rows = []
    for k, n in d["counts"].items():
        ex = d["failures"][k][0]
        fix, worked = fixes.get(k, ("--", "--"))
        rows.append([tex(k.replace("_", " ")), str(n), r"\texttt{" + tex(ex["job_id"]) + "} " + tex(ex.get("title", ""))[:48],
                     fix, worked])
    write("failures", "p{2.1cm}rp{3.6cm}p{4.4cm}p{3.6cm}", ["Category", "Jobs", "Example", "Fix tried", "Did it work"],
          rows, r"Source: \texttt{evals/results/failure\_analysis.json} (all rows with job ids); "
                r"categories with 0 failures omitted.")


if __name__ == "__main__":
    for fn in (rag, breakdown, decisions, orchestration, outcomes, x3, tools, judge, failures):
        try:
            fn()
        except (TypeError, KeyError, StopIteration) as exc:
            print(f"{fn.__name__}: skipped ({exc})")
    print("tables:", sorted(p.name for p in OUT.glob("*.tex")))
