# 0005 Postgres for state and memory, Arq on Redis for background work

**Context.** Runs pause for human approval for an unknown time; the worker can crash between "approved" and "submitted"; the UI needs run history and live progress.

**Decision.** One Postgres (pgvector image) holds three things:
- LangGraph checkpoints (`AsyncPostgresSaver`);
- long-term memory (`PostgresStore`);
- app tables: users, encrypted MCP credentials, runs, saved searches.

Background work (graph runs, Scout, outcome polling) goes through Arq on Redis. Job ids are deterministic, so a double-clicked approval queues once. Marketplace writes carry idempotency keys derived from the thread and payload, so a resumed run never submits twice.

**Alternatives.** SQLite checkpoints: fine locally, but not shared between the API and worker processes. Celery: heavier and sync-first. Running graphs inside API requests: a long run would die with the request.

**Consequences.** Two infrastructure services to run; both are in the compose file. On Windows, psycopg's async mode needs a selector event loop, handled in `apps/api/serve.py` and the worker.
