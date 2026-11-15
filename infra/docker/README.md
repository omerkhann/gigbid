# Docker

Two images, both built from the repo root by `infra/docker-compose.yml`:

| Image | Dockerfile | Used by |
|---|---|---|
| `gigbid-py` | `python.Dockerfile` (uv, runtime deps only, non-root) | api, worker, gigsim, mcp-marketplace, mcp-workspace, mcp-portfolio |
| `gigbid-web` | `web.Dockerfile` (Next.js production build) | web |

```bash
docker compose -f infra/docker-compose.yml up -d                        # Postgres, Redis, Phoenix only (local dev)
docker compose -f infra/docker-compose.yml --profile app up -d --build  # the whole product
```

UI http://localhost:3000 (reviewer@gigbid.dev / gigbid-review), API http://localhost:8000/docs,
GigSim http://localhost:8100, traces http://localhost:6006.

Choices:
- **Secrets** come from the repo's `.env` (`env_file`); containers override every URL to in-network
  service names, so the same `.env` works for native and container runs.
- **No GPU or Ollama needed.** Containers default to `MODEL_PROFILE=open_hosted` (Groq) and the
  fastembed embedder (bge-small, ONNX on CPU). Set `MODEL_PROFILE=open` to use Ollama on the host
  (`host.docker.internal:11434`).
- **Only the UI, API and GigSim are published** (on 127.0.0.1). The MCP servers are reachable only
  inside the compose network.
- **State** (SQLite files of GigSim and the MCP servers, embedding caches, ONNX models) lives on the
  `appdata` volume; Postgres and Phoenix have their own volumes. The first portfolio search
  downloads the embedding model (~130 MB) and embeds the portfolio, then answers in under a second.
- **API_URL is a build argument of the web image**: Next.js writes rewrites into the build output,
  so the `/api` proxy target is fixed at build time (`http://api:8000`).
