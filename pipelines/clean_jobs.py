"""Clean the ahmedmyalo/upwork-freelance-jobs-60k dataset into data/processed/jobs.parquet.

Run: python -m pipelines.clean_jobs   (or `make data`)

Decisions (each is logged in the report, and explained in docs/DATA_CARD.md):
  1. Drop exact duplicate URLs (same job scraped twice) and posts < MIN_DESC_CHARS.
  2. Keep reposts (same title and description, different URL) but link each one to
     the first copy via `natural_dup_of`. These are real duplicates Scout must catch, with
     labels we didn't have to invent.
  3. Mask emails and phone numbers in descriptions (real clients' PII).
  4. Keep client spend as-is (it has outliers up to $70M); anything that uses it
     should work on thresholds or logs, never the raw mean.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pipelines.parsing import (
    clean_text,
    normalise_for_dedup,
    parse_duration,
    parse_hours_ago,
    parse_money,
    parse_money_range,
    stable_id,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/kaggle/upwork-freelance-jobs-60k/Final_Upwork_Dataset.csv"
OUT = ROOT / "data/processed/jobs.parquet"
REPORT = ROOT / "data/processed/jobs_report.json"
SOURCE = "kaggle:ahmedmyalo/upwork-freelance-jobs-60k"

MIN_DESC_CHARS = 50
# Reposts are only linked when the text is long enough to be distinctive;
# two different clients can both write "Need a logo for my brand".
MIN_DUP_CHARS = 150

CATEGORY = {"Developer": "development", "Marketing": "marketing",
            "3D": "3d_design", "Data_science": "data_science"}
EXPERIENCE = {"Entry level": "entry", "Intermediate": "intermediate", "Expert": "expert"}


def _skills(row: pd.Series) -> list[str]:
    seen: dict[str, None] = {}
    for i in range(1, 10):
        val = row.get(f"Category_{i}")
        if isinstance(val, str) and val.strip():
            seen.setdefault(val.strip(), None)
    return list(seen)


def _budget(row: pd.Series) -> tuple[float | None, float | None]:
    if row["payment_type"] == "fixed":
        cost = parse_money(row["Job_Cost"])
        return (cost, cost)
    lo, hi = parse_money(row["Start_rate"]), parse_money(row["End_rate"])
    if lo is None and hi is None:
        lo, hi = parse_money_range(row["Hourly_Rate"])
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return (lo, hi if hi is not None else lo)


def build() -> dict:
    df = pd.read_csv(RAW, low_memory=False)
    report: dict = {"source": SOURCE, "raw_rows": len(df)}

    df = df.drop_duplicates(subset="Job_URL", keep="first")
    report["after_url_dedup"] = len(df)

    df["description"] = df["Description"].map(clean_text)
    df = df[df["description"].str.len() >= MIN_DESC_CHARS].copy()
    report["after_short_desc_drop"] = len(df)
    report["descriptions_with_masked_email"] = int(df["description"].str.contains(r"\[EMAIL\]").sum())
    report["descriptions_with_masked_phone"] = int(df["description"].str.contains(r"\[PHONE\]").sum())

    df["job_id"] = df["Job_URL"].map(lambda u: stable_id("job", u))
    df["payment_type"] = df["Payment_type"].map({"Hourly": "hourly", "Fixed-price": "fixed"})
    budgets = df.apply(_budget, axis=1, result_type="expand")
    df["budget_min"], df["budget_max"] = budgets[0], budgets[1]
    durations = df["Time_Limitation"].map(parse_duration)
    df["duration"] = durations.map(lambda d: d[0])
    df["workload"] = durations.map(lambda d: d[1])

    # Link reposts to the first copy with the same normalised title AND description.
    # Text alone over-matches: one agency posts "Chinese proofreader" and "Portuguese
    # proofreader" with identical text, and those are different jobs.
    norm_desc = df["description"].map(normalise_for_dedup)
    key = df["Job Title"].map(clean_text).map(normalise_for_dedup) + "|" + norm_desc
    first_id = df.groupby(key)["job_id"].transform("first")
    is_repost = (first_id != df["job_id"]) & (norm_desc.str.len() >= MIN_DUP_CHARS)
    df["natural_dup_of"] = first_id.where(is_repost)
    report["natural_reposts_linked"] = int(is_repost.sum())

    out = pd.DataFrame({
        "job_id": df["job_id"],
        "source": SOURCE,
        "source_url": df["Job_URL"],
        "title": df["Job Title"].map(clean_text),
        "description": df["description"],
        "category": df["Search_Keyword"].map(CATEGORY),
        "required_skills": df.apply(_skills, axis=1),
        "experience_level": df["EX_level_demand"].map(EXPERIENCE),
        "payment_type": df["payment_type"],
        "budget_min": df["budget_min"],
        "budget_max": df["budget_max"],
        "currency": "USD",
        "duration": df["duration"],
        "workload": df["workload"],
        "connects_cost": df["Connects_Num"].astype("Int64"),
        "applicants": df["Applicants_Num"],
        "freelancers_needed": df["Freelancers_Num"].astype("Int64"),
        "posted_hours_ago": df["Posted_from"].map(parse_hours_ago),
        "client_payment_verified": df["Payment_Situation"].map(
            {"Payment verified": True, "Payment unverified": False}).astype("boolean"),
        "client_total_spent": df["Spent($)"],
        "client_rating": df["Rating"],
        "client_feedback_count": df["Feedback_Num"].astype("Int64"),
        "client_country": df["Client_Country"],
        "client_enterprise": df["Enterprise_Client"].eq("Enterprise"),
        "natural_dup_of": df["natural_dup_of"],
    })

    report["final_rows"] = len(out)
    report["null_rate"] = {c: round(float(v), 3) for c, v in out.isna().mean().items() if v > 0}
    report["payment_type_counts"] = out["payment_type"].value_counts(dropna=False).to_dict()
    report["category_counts"] = out["category"].value_counts(dropna=False).to_dict()
    report["client_spent_p99"] = float(out["client_total_spent"].quantile(0.99))
    report["client_spent_max"] = float(out["client_total_spent"].max())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    REPORT.write_text(json.dumps(report, indent=2, default=str))
    return report


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, default=str))
