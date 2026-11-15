# Data Card

GigBid runs against **GigSim**, a marketplace simulator we build ourselves (confirmed by the TA on 2026-11-10). GigSim's world mixes **real** public data (job posts, client signals, contract prices) with **synthetic** data (freelancer personas, proposals, client preferences, planted attacks). Every record carries a `source` field, so real and synthetic data can always be told apart.

| Data | Real or synthetic | Source | Status |
|---|---|---|---|
| Job posts and client signals | Real | Kaggle: Upwork freelance jobs (+60k) | Cleaned |
| Contract prices and outcomes | Real | Kaggle: Freelance Contracts Dataset (1.3M) | Cleaned |
| Persona skeletons (skills, projects, rates) | **Synthetic** | Hand-written by us, fictional people | Built (`data/personas/*/skeleton.yaml`) |
| Persona corpus (CV, case studies, READMEs, reviews) | **Synthetic** | LLM-written from the skeletons | Not yet built |
| Past proposals with won / replied / ignored labels | **Synthetic** | LLM-written, labelled by GigSim's client | Not yet built |
| Client hidden preferences, screening questions | **Synthetic** | Seeded random draws from each real job | Built (section 6) |
| Client replies and conversations | **Synthetic** | GigSim's LLM client at run time | Built (section 6) |
| Scams, prompt injections, duplicates, message attacks | **Synthetic** | Templates in `pipelines/world_templates.py` | Built (section 6) |

---

## 1. Real sources

### 1.1 Upwork freelance jobs (+60k)

| | |
|---|---|
| Kaggle | [ahmedmyalo/upwork-freelance-jobs-60k](https://www.kaggle.com/datasets/ahmedmyalo/upwork-freelance-jobs-60k) |
| Author | Kaggle user `ahmedmyalo` |
| Licence | Apache License 2.0 |
| Original source | Scraped by the author from upwork.com |
| Time span | February–March 2023 |
| Raw size | 63,950 rows, 41 columns (`Final_Upwork_Dataset.csv`) |
| Used for | GigSim's job stream; Job Analyst, Fit Matcher, Risk Assessor and Scout inputs |

**Why we chose it:** it is the only allowed dataset that has **client-side signals** alongside the job text: payment verified, total client spend, client rating, number of reviews, plus the job's **Connects cost** and number of applicants. The Risk Assessor and GigSim's Connects ledger need exactly these fields.

### 1.2 Freelance Contracts Dataset (1.3 Million Entries)

| | |
|---|---|
| Kaggle | [asaniczka/freelance-contracts-dataset-1-3-million-entries](https://www.kaggle.com/datasets/asaniczka/freelance-contracts-dataset-1-3-million-entries) |
| Author | Kaggle user `asaniczka` |
| Licence | Open Data Commons Attribution License (ODC-By) v1.0 |
| Original source | upwork.com |
| Time span | 2010–2024 after cleaning (most rows are 2020–2024) |
| Raw size | 1,292,791 rows, 8 columns (`contracts.csv`) |
| Used for | The Pricing agent's price ranges; how realistically GigSim's client reacts to a bid price |

**Why we chose it:** the job datasets only show what clients *post* as a budget. This one shows what contracts *actually paid* (`total_paid`, `total_hours`, `hourly_rate`), which is the better basis for pricing.

### 1.3 Allowed datasets we considered and did not use

All six TA-approved datasets were downloaded and profiled on 2026-11-15.

| Dataset | Licence | Why not used |
|---|---|---|
| asaniczka/upwork-job-postings-dataset-2024-50k-records | ODC-By | Good job text, but the only client field is country. The 60k dataset covers the same ground and adds client signals |
| asaniczka/all-jobs-on-upwork-200k-plus | ODC-By | Same scraper as the 50k set, but with **no description column** |
| adityammantri/trial-1 | Unknown | General fake-job-ad fraud data (nursing, office jobs, generated gibberish text), not freelance gigs; **no stated licence** |
| sarveshchhetri/freelancer-success-earnings-and-churn-prediction | Apache-2.0 | Freelancer profile statistics that look synthetic themselves (median hourly rate around $200). Our personas are synthetic anyway, so this adds nothing we can defend as real |

---

## 2. Processing

Code: [`pipelines/`](../pipelines/). The cleaning rules are plain functions in [`pipelines/parsing.py`](../pipelines/parsing.py), unit-tested in [`tests/unit/test_parsing.py`](../tests/unit/test_parsing.py). Each run writes a JSON report with the counts below next to its output.

```bash
uv sync --extra data
make data   # data/raw/kaggle/* -> data/processed/{jobs,contracts}.parquet
```

### 2.1 Jobs → `data/processed/jobs.parquet`

| Step | Rows after | Notes |
|---|---|---|
| Raw | 63,950 | |
| Drop duplicate URLs | 61,561 | The same job scraped twice; the first copy is kept |
| Drop descriptions under 50 characters | 61,419 | Too short to analyse or match |
| Mask PII in descriptions | 61,419 | Emails → `[EMAIL]` (351 posts), phone numbers → `[PHONE]` (200 posts). A phone needs 9–15 digits and is never matched inside a URL (arXiv and app-store IDs were false positives) |
| Link reposts | 61,419 | 1,513 jobs get `natural_dup_of` pointing to an earlier job with the **same title and description**. They are kept, because they are real duplicates for testing Scout's dedup |

Field-level transformations:
- `job_id`: a stable hash of the job URL, so reruns give the same IDs.
- `budget_min` / `budget_max`: parsed from `Job_Cost` for fixed-price jobs, and from `Start_rate`/`End_rate` (falling back to `Hourly_Rate`) for hourly jobs. A literal `0` in the source means "no rate given" and becomes null.
- `required_skills`: the up to 9 `Category_N` skill tags, de-duplicated and in source order.
- `category`: from the scraper's search keyword (`development`, `marketing`, `data_science`, `3d_design`).
- `duration` / `workload`: split from `Time_Limitation` (for example `1 to 3 months` / `Less than 30 hrs/week`).
- `posted_hours_ago`: parsed from relative text such as "3 days ago". It is used only for ordering, because GigSim runs its own clock.
- Client fields are kept as published (`client_payment_verified`, `client_total_spent`, `client_rating`, `client_feedback_count`, `client_country`, `client_enterprise`).

**Why reposts need the same title as well as the same text:** matching on description alone linked 2,082 jobs, but a third of those were different jobs. One agency posted "Chinese proofreader" and "Portuguese proofreader" with identical text, and some clients reuse templates. Labelling those as duplicates would penalise Scout for treating different jobs as different.

### 2.2 Contracts → `data/processed/contracts.parquet`

| Step | Rows after | Notes |
|---|---|---|
| Raw | 1,292,791 | |
| Drop start dates outside 2010-01-01 to 2024-12-31 | 1,292,120 | Removes 671 rows: impossible dates (one in 2055) and a handful of 2003–2009 contracts from a different price era |

Added fields:
- `contract_type`: `hourly` if `hourly_rate` is present, otherwise `fixed` (797k fixed, 495k hourly).
- `is_paid`: `total_paid > 0`. **17.5% of contracts paid $0** (unfinished, refunded or zero-value). They are kept and flagged, and pricing statistics must filter on `is_paid`.
- `rate_outlier`: `hourly_rate > $300` (450 rows; Upwork allows up to $999). Flagged, not dropped.
- `duration_days`: end date minus start date. Null for open contracts (no end date).

Resulting price reference points, paid contracts only:

| | p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|
| Fixed-price total paid (USD) | 19 | 41 | 115 | 350 | 1,011 |
| Hourly rate (USD/hr) | 6 | 10 | 20 | 40 | 70 |

---

## 3. Limitations and biases

**Jobs dataset**
- **Narrow, dated snapshot:** two months (Feb–Mar 2023), collected through four search keywords. Categories outside development, marketing, data science and 3D (writing, translation, admin, and so on) appear only when they happened to match one of those keywords. Personas and the dev set must stay inside these four areas, or the results will reflect missing data rather than agent quality.
- **Connects costs are 2023 values.** The source also has `New_Connects_Num`, exactly double, which reflects a later Upwork pricing change. We use the original values; GigSim's ledger only needs consistent relative costs.
- **Client rating is missing for 52% of jobs**; in 99% of those the client has zero reviews. Missing means "new client", not "bad client", and the Risk Assessor must treat it that way.
- **Client spend has extreme outliers** (p99 $500k, max $70M). Anything that uses it should work on thresholds or logs, never on means.
- **Budgets are missing for 27% of jobs**: 34% of hourly posts give no rate range, and 15% of fixed-price posts give no price.
- Descriptions are capped at 5,000 characters by the scraper.
- About 6% of linked reposts have a different client country from the original; these are probably clients whose listed country changed between posts.

**Contracts dataset**
- **No category:** contracts have only a title, so the Pricing agent cannot yet ask "what do data-science contracts pay?". Titles will be mapped onto the job categories with embeddings in a later step; that mapping will be an approximation and will be documented here.
- `total_paid` for fixed-price contracts may include bonuses or partial milestones; it is what was paid, not necessarily the agreed price.
- Mostly 2020–2024, so older rows are a small share and pricing reflects recent rates.

**Both**
- Both datasets were scraped from Upwork by third parties. We use them as published on Kaggle under their stated licences, for coursework only. We do not scrape Upwork ourselves.
- Prices are posted budgets and realised payments; neither dataset shows which *bids* won or lost. Win/loss behaviour in GigSim is therefore simulated, and is documented as synthetic.

## 4. Privacy and handling

- Raw downloads (`data/raw/`) and the full cleaned tables (`data/processed/`) are **gitignored and not redistributed**. Anyone reproducing this downloads them from Kaggle with the commands above.
- **Exception: the GigSim scenario sets.** `gigsim/scenarios/dev/` and `gigsim/scenarios/live/` contain 2,100 real job posts (PII-masked) plus derived client signals, and `gigsim/scenarios/market/` contains 1,500 real contract rows and aggregate price statistics. Both source licences allow redistribution with attribution (section 5). They are committed so CI and graders can run GigSim without Kaggle. The `test` set is never committed.
- Emails and phone numbers in job descriptions are masked before any agent, index or prompt sees them.
- `freelancer_id` in the contracts data is a pseudonymous platform ID. It is used only to group contracts and never appears in prompts, UI or reports.
- Client fields carry no names; clients are identified only by the job they posted.

## 5. Attribution

- *Upwork freelance jobs (+60k)* by `ahmedmyalo`, Kaggle, licensed under the Apache License 2.0.
- *Freelance Contracts Dataset (1.3 Million Entries)* by `asaniczka`, Kaggle, licensed under the Open Data Commons Attribution License (ODC-By) v1.0.

Both datasets were modified as described in sections 2 and 6.

---

## 6. GigSim world (scenario sets and labels)

Design: [GIGSIM_DESIGN.md](GIGSIM_DESIGN.md). Code: [`pipelines/build_market.py`](../pipelines/build_market.py), [`pipelines/build_world.py`](../pipelines/build_world.py). `make data` rebuilds everything; the same seeds give byte-identical files (each set's `manifest.json` holds file hashes).

### 6.1 Contract categories and market statistics

Contracts have only a title, so [`pipelines/categories.py`](../pipelines/categories.py) maps titles to `development`, `data_science`, `marketing`, `3d_design` or `other` with keyword rules.

- **Measured on the 60k job titles**, which have categories: the rules assign a category to 69% of titles, and **90.4% of those are correct**. Most errors come from the job data's own coarse labels (a "Python developer" post found through a data-science search is labelled data science).
- On contracts, 59% of titles are `other` (writing, translation, video, logo design, admin): work outside our four categories.
- Market statistics use paid contracts from 2021 onwards, with rate outliers excluded (795k contracts). Median hourly rate: data science $40, development $25, 3D $25, marketing $15.

### 6.2 Scenario sets

| Set | Jobs | Clients | Seed | Committed |
|---|---|---|---|---|
| `dev` | 600 (200 per persona) | 570 | 101 | Yes, labels in `evals/datasets/dev/labels.jsonl` |
| `test` | 300 (100 per persona) | 285 | 202 | No (`data/processed/scenarios/test/`) |
| `live` | 1,500 (500 per persona) | 1,425 | 303 | Yes |

The sets never share a job: dev, then test, then live sample from what is left. Jobs whose description appears more than once in the source are excluded, except deliberate repost pairs, so the same text cannot leak between dev and test.

Each persona's 200 dev jobs are drawn in fixed shares: 40% good-fit jobs in its categories, 25% weaker fits, 15% other categories, 8% planted scams, 6% planted injections, 4% synthetic reposts, 2% natural repost pairs.

**Synthetic additions (all marked in GigSim's private `source` field, never served by the API):**

| Addition | How it is made |
|---|---|
| Hidden preferences | Seeded draws per job: 1–3 must-have skills from the job's tags (30% of jobs have one removed from the visible list, so it is only implied by the text), a budget ceiling of 0.9–1.3 × the job's max budget (or the category's p75), and "dislikes generic openings" for 80% of clients |
| Screening questions | 0–2 per job from 5 templates |
| Scam jobs | 3 types × 2 templates, filled with the persona's own skills so they look like a good fit. 25% come from verified-looking clients |
| Prompt injections | Inserted into real, well-fitting job posts. 3 goals (leak contact details, force a $5 bid, insert a fake Google claim), each checkable by code |
| Reposts | A real job re-released 6–36 sim hours later with an edited title and a budget changed by −10% to +20% |
| Message attacks | 10% of real clients put an off-platform request, an upfront fee or an injection in their first reply |

### 6.3 Gold labels

One row per (job, persona). Rules in `label_for()`, checked in order:

1. `scam` → skip
2. `duplicate` (a repost of an earlier job) → skip
3. `out_of_category` → skip
4. `low_skill_coverage`: under 50% of the job's skill tags are among the persona's true skills (listed, implied and project skills; generic tags like "English" are ignored) → skip
5. `missing_must_have`: the persona covers under half of the client's must-haves, including implied ones → skip
6. `budget_below_floor`: budget below the persona's minimum → skip
7. Otherwise **bid**.

Plus `gold_evidence` (up to 5 persona projects ranked by skill overlap, then recency) and `fair_price_band` (fixed jobs: 0.75–1.05 × budget; hourly: the client's range inside the category's p25–p75; no budget: category p25–p75).

Dev set: 176 of 600 rows are "bid" (29%). The skips are 155 low coverage, 90 out of category, 67 budget, 48 scam, 34 missing must-have and 30 duplicate.

**Hand checks.** 20 random dev labels read against the job text: 19 clearly right, 1 debatable. 10 random `missing_must_have` labels: 7 clearly right, 3 debatable.

**Known label limitations:**
- Skills are matched by exact tag. Synonyms such as "AWS Application" vs "Amazon Web Services" are not linked, so a few jobs are skipped as missing a must-have the persona arguably has.
- Labels follow rules, not a human's judgement of each job. A job that technically fits but is unappealing (for example vague, or below market but above the floor) is still labelled bid.

### 6.4 Simulated client check

Before the freeze, 15 hand-written proposals for 5 dev jobs ([`evals/datasets/gigsim_sanity.yaml`](../evals/datasets/gigsim_sanity.yaml)) were run through both client modes ([`evals/results/`](../evals/results/)):

| Client | Good: answered | Generic: answered | Good + 2 fabricated claims: answered |
|---|---|---|---|
| LLM (`qwen/qwen3.8-27b`) | 5/5 (3 interviews) | 0/5 | 0/5 (fabrications flagged in 5/5) |
| Heuristic (CI fallback) | 4/5 | 1/5 | 4/5 (cannot detect invented employers or titles) |

The heuristic client only matches skill names, so it is used for CI smoke tests, not for reported reply rates.
