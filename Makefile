.PHONY: install api test lint eval data
install:
	uv sync --extra dev --extra data

api:
	uvicorn apps.api.main:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check .

eval:
	python -m evals.runners.run_demo_eval

# Rebuild data/processed/ from data/raw/kaggle/ (needs: uv sync --extra data)
data:
	python -m pipelines.clean_jobs
	python -m pipelines.clean_contracts
