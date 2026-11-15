# 0003 A deliberately simple, deterministic GigSim

**Context.** Students build the marketplace simulator. A first design modelled competing bidders, client moods and market dynamics; most of that could not be checked against data, and it would mainly add noise to the evals.

**Decision.** A FastAPI + SQLite simulator built from the cleaned Kaggle job and contract data. Each job has hidden client preferences. The client is rule-based, or an LLM from a different model family than the Writer, cached in SQLite so reruns cost nothing. Faults and rate limits are seeded, and admin endpoints support the evals. Frozen at tag `gigsim-v1`; CI fails if anything under `gigsim/` changes. Design: [GIGSIM_DESIGN.md](../GIGSIM_DESIGN.md).

**Alternatives.** The richer agent-based market (more realistic in principle, but hard to validate and to explain); testing only against recorded fixtures (no outcomes to measure).

**Consequences.** Reply rates are only as meaningful as the hidden preferences. That is why the GigSim sanity checks are committed (`evals/runners/gigsim_sanity.py`) and the report treats reply rate as a secondary metric.
