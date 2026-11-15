# One image for every Python service (API, worker, GigSim, the three MCP servers); compose picks
# the command. Built from the repo root: docker build -f infra/docker/python.Dockerfile .
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /app

# Dependencies first (cached unless the lockfile changes); runtime deps only, no dev or data extras.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-install-project --no-dev

COPY agent agent
COPY apps/api apps/api
COPY apps/__init__.py apps/
COPY pipelines/__init__.py pipelines/parsing.py pipelines/
COPY worker worker
COPY gigsim gigsim
COPY mcp_servers mcp_servers
COPY rag rag
COPY data/personas data/personas
COPY data/policy_pack data/policy_pack

# Runtime state (SQLite files, embedding caches, downloaded ONNX models) lives on a volume.
ENV FASTEMBED_CACHE_PATH=/app/data/processed/models RERANKER_CACHE=/app/data/processed/models
RUN useradd --create-home --uid 1000 gigbid && mkdir -p data/processed && chown -R gigbid data/processed
USER gigbid
EXPOSE 8000
CMD ["python", "-m", "apps.api.serve", "--host", "0.0.0.0", "--port", "8000"]
