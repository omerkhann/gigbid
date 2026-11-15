# 0009 Same-origin UI through a proxy, live updates over SSE

**Context.** The browser needs the session cookie and a live event stream of run progress. Cross-origin SSE with cookies failed in testing.

**Decision.** Next.js rewrites `/api/*` to FastAPI, so the browser talks to one origin: first-party cookies, no CORS. Run progress streams over Server-Sent Events from `/api/runs/stream`. The typed API client is generated from FastAPI's OpenAPI schema (`openapi-typescript`), and CI fails if it drifts.

**Alternatives.** WebSockets: two-way traffic isn't needed. Polling: slower and more load. CORS with credentials: worked for fetch, not for EventSource with cookies.

**Consequences.** The proxy target is fixed at build time (`API_URL` is a build argument of the web image). Bearer tokens are accepted too, and take priority over the cookie, for scripted clients.
