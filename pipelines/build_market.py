"""Build GigSim's pricing data from the cleaned contracts.

Writes gigsim/scenarios/market/:
  stats.json     price percentiles per (category, contract_type), served by GET /market/stats
  history.jsonl  ~1,500 sampled paid contracts, served by GET /market/history

Run: python -m pipelines.build_market   (needs data/processed/contracts.parquet)

Decisions:
  - Paid contracts only, rate outliers excluded: stats describe what work actually paid.
  - Only contracts starting 2021 or later, so prices are close to the jobs' 2023 snapshot.
  - Categories come from keyword rules on the title (pipelines/categories.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipelines.categories import CATEGORIES, categorise
from pipelines.parsing import clean_text, stable_id

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "data/processed/contracts.parquet"
OUT_DIR = ROOT / "gigsim/scenarios/market"

SINCE = pd.Timestamp("2021-01-01")
HISTORY_PER_CATEGORY = 300  # 5 groups (4 categories + other) -> 1,500 rows
SEED = 42
QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9)


def _percentiles(series: pd.Series) -> dict[str, float]:
    return {f"p{int(q * 100)}": round(float(series.quantile(q)), 2) for q in QUANTILES}


def build() -> dict:
    df = pd.read_parquet(CONTRACTS)
    df = df[df["is_paid"] & ~df["rate_outlier"] & (df["start_date"] >= SINCE)].copy()
    df["category"] = df["title"].map(categorise)

    stats: dict = {"source": "kaggle:asaniczka/freelance-contracts-dataset-1-3-million-entries",
                   "filter": f"paid, no rate outliers, start_date >= {SINCE.date()}",
                   "groups": {}}
    for cat in (*CATEGORIES, "other", "all"):
        sub = df if cat == "all" else df[df["category"] == cat]
        fixed = sub[sub["contract_type"] == "fixed"]
        hourly = sub[sub["contract_type"] == "hourly"]
        stats["groups"][cat] = {
            "fixed": {"n": len(fixed), "total_paid": _percentiles(fixed["total_paid"])},
            "hourly": {"n": len(hourly), "hourly_rate": _percentiles(hourly["hourly_rate"]),
                       "total_hours": _percentiles(hourly["total_hours"])},
        }

    history = (df.groupby("category", group_keys=False)
                 .sample(n=HISTORY_PER_CATEGORY, random_state=SEED))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "history.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for row in history.itertuples():
            f.write(json.dumps({
                "contract_id": stable_id("ctr", str(row.job_id)),
                "title": clean_text(row.title),
                "category": row.category,
                "contract_type": row.contract_type,
                "start_date": row.start_date.date().isoformat(),
                "total_hours": round(float(row.total_hours), 2),
                "total_paid": round(float(row.total_paid), 2),
                "hourly_rate": None if pd.isna(row.hourly_rate) else float(row.hourly_rate),
                "source": "real",
            }) + "\n")
    (OUT_DIR / "stats.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8",
                                        newline="\n")

    return {"contracts_used": len(df),
            "category_share": df["category"].value_counts(normalize=True).round(3).to_dict(),
            "history_rows": len(history)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
