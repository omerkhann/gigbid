## Overview
`finfast-batchapi` is a Python‑based service that exposes two FastAPI endpoints: a real‑time inference path (`/predict`) and a batch processing path (`/batch`). The real‑time endpoint handles single‑request predictions with sub‑200 ms latency, while the batch endpoint aggregates incoming requests, groups them into configurable chunks, and processes them asynchronously via Celery workers. The service is containerised with Docker and deployed on AWS (ECS/Fargate) behind an Application Load Balancer.

## Architecture
- **FastAPI**: lightweight ASGI server exposing HTTP/JSON APIs.
- **Celery + Redis**: task queue for batch jobs; workers pull batches, run the model, and store results in S3.
- **Docker**: two images – `api` (FastAPI) and `worker` (Celery). Multi‑stage builds keep images small.
- **AWS**: ECS task definitions for both containers, ALB routing, IAM role for S3 access, CloudWatch for logs/metrics.
- **Model**: loaded once per worker process to avoid reload overhead; uses `torch` (or `sklearn`) depending on the model type.

## Getting Started
```bash
# Clone repository
git clone https://github.com/yourusername/finfast-batchapi.git
cd finfast-batchapi

# Build Docker images
docker compose build

# Run locally (API on 8000, Redis on 6379, Celery worker)
docker compose up -d
```
The API is reachable at `http://localhost:8000`. Use `POST /predict` with a JSON payload for immediate inference, or `POST /batch` to enqueue a batch job. Job IDs can be polled via `GET /batch/{job_id}`.

## Configuration
Environment variables (via `.env` or ECS task definition):
- `MODEL_PATH` – path to serialized model file.
- `REDIS_URL` – connection string for the broker.
- `S3_BUCKET` – bucket for batch result storage.
- `BATCH_SIZE` – max records per Celery task.
- `BATCH_TIMEOUT` – seconds to wait before flushing an incomplete batch.

## Performance
Load testing with `hey` at 50 req/s yields a p95 latency of ~120 ms for the real‑time endpoint. Batch throughput scales linearly with the number of Celery workers.

## Deployment
Push images to ECR, update ECS service definitions, and let the ALB handle traffic routing. Use CloudWatch alarms on latency and queue depth to auto‑scale workers.
