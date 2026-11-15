"""Clean asaniczka/freelance-contracts-dataset-1-3-million-entries into
data/processed/contracts.parquet. This is the real "what freelancers actually got paid"
data the Pricing agent and GigSim's client use.

Run: python -m pipelines.clean_contracts   (or `make data`)

Decisions:
  1. Contract type: a contract with an hourly_rate is hourly, otherwise fixed-price.
  2. Keep $0 contracts but flag them (is_paid=False). They're unfinished or refunded
     contracts, so pricing stats should filter them out, but how often they happen
     is still useful.
  3. Drop impossible dates (after the scrape, e.g. 2055) and pre-2010 contracts
     (fewer than 0.1% of rows, and a different price era).
  4. Flag rate outliers (> MAX_SANE_HOURLY, Upwork's cap is $999) instead of dropping them.
  5. Contracts have only a title, no category. Mapping titles onto the job
     categories is done later (embeddings), not here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/kaggle/freelance-contracts-dataset-1-3-million-entries/contracts.csv"
OUT = ROOT / "data/processed/contracts.parquet"
REPORT = ROOT / "data/processed/contracts_report.json"
SOURCE = "kaggle:asaniczka/freelance-contracts-dataset-1-3-million-entries"

MIN_DATE = pd.Timestamp("2010-01-01")
MAX_DATE = pd.Timestamp("2024-12-31")
MAX_SANE_HOURLY = 300.0


def build() -> dict:
    df = pd.read_csv(RAW, dtype={"job_id": str, "freelancer_id": str})
    report: dict = {"source": SOURCE, "raw_rows": len(df)}

    for col in ("start_date", "end_date"):
        df[col] = pd.to_datetime(df[col], errors="coerce", format="mixed")
    in_range = df["start_date"].between(MIN_DATE, MAX_DATE)
    report["dropped_bad_dates"] = int((~in_range).sum())
    df = df[in_range].copy()

    df["contract_type"] = df["hourly_rate"].notna().map({True: "hourly", False: "fixed"})
    df["is_paid"] = df["total_paid"] > 0
    df["rate_outlier"] = df["hourly_rate"] > MAX_SANE_HOURLY
    df["duration_days"] = (df["end_date"] - df["start_date"]).dt.days
    df["title"] = df["job_title"].str.strip()
    df["source"] = SOURCE

    out = df[["job_id", "source", "title", "contract_type", "start_date", "end_date",
              "duration_days", "freelancer_id", "total_hours", "total_paid", "hourly_rate",
              "is_paid", "rate_outlier"]]

    paid = out[out["is_paid"]]
    report.update({
        "final_rows": len(out),
        "contract_type_counts": out["contract_type"].value_counts().to_dict(),
        "unpaid_share": round(1 - out["is_paid"].mean(), 3),
        "rate_outliers": int(out["rate_outlier"].sum()),
        "fixed_paid_percentiles": paid.loc[paid["contract_type"] == "fixed", "total_paid"]
            .quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(0).to_dict(),
        "hourly_rate_percentiles": paid["hourly_rate"]
            .quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(1).to_dict(),
        "unique_freelancers": int(out["freelancer_id"].nunique()),
    })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    REPORT.write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, default=str))
