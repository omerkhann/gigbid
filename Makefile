.PHONY: install api test lint eval eval-rag eval-decision eval-outcomes eval-smoke data
install:
	uv sync --extra dev --extra data

api:
	uvicorn apps.api.main:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check .

# Full evals (real models; ~1-2 h on a laptop). Results land in evals/results/.
eval: eval-rag eval-decision eval-outcomes

eval-rag:
	python -m evals.runners.rag_eval
	python -m evals.runners.rag_eval --variants v8_corrective --limit 15

eval-decision:
	python -m evals.runners.decision_eval
	MODEL_PROFILE=open_hosted python -m evals.runners.decision_eval

eval-outcomes:
	python -m evals.runners.gigsim_outcomes

# What CI runs on every PR: no LLM for RAG; decisions on 30 jobs with hosted models
eval-smoke:
	python -m evals.runners.rag_eval --variants v0_naive v2_hybrid --limit 10 --embedder fastembed:BAAI/bge-small-en-v1.5 --out evals/results/ci/rag_eval.json
	python -m evals.check_thresholds rag evals/results/ci/rag_eval.json

# Rebuild data/processed/ from data/raw/kaggle/ (needs: uv sync --extra data)
data:
	python -m pipelines.clean_jobs
	python -m pipelines.clean_contracts
	python -m pipelines.build_market
	python -m pipelines.build_world
