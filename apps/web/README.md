# GigBid web app

Next.js 16 (App Router) + TypeScript + Tailwind. The human stays in control here: every proposal and message is approved, edited or rejected on these screens before anything reaches a client.

## Run

```bash
npm install
npm run dev            # http://localhost:3000; /api/* is proxied to the FastAPI backend (API_URL, default http://127.0.0.1:8000)
```

Start the backend first (see [docs/RUNBOOK.md](../../docs/RUNBOOK.md)). Sign in as `reviewer@gigbid.dev`.

## Screens

| Route | Screen |
|---|---|
| `/login` | Sign in, or create an account and pick a portfolio persona |
| `/inbox` | Analysed jobs ranked by fit, with risk badges, recommended action, price and Connects cost; filters; Run Scout; analyse a job by id |
| `/jobs/[id]` | JobSpec, risk report, requirement-to-evidence matrix, price rationale, bid/skip reasoning, live agent steps |
| `/studio/[id]` | Proposal studio: evidence on hover for every claim, claim checks, Critic and Compliance comments, editor, regenerate one paragraph, the dry-run preview of exactly what is sent and what it costs, approve / edit / reject |
| `/pipeline` | Kanban: drafted, submitted, viewed, replied, interview, hired, lost |
| `/messages`, `/messages/[id]` | Client threads with the suggested reply, scam warnings and offered interview slots; approve before sending |
| `/runs`, `/runs/[id]` | Live node-by-node progress streamed from LangGraph, with a link to the full trace |
| `/analytics` | Reply and hire rate by category, Connects spent vs outcomes, cost and latency, top skip reasons |
| `/settings` | Rates, autonomy, Connects budget, saved searches, connected accounts, and the memory viewer (see and delete what GigBid learned) |

## Typed API contract

`src/lib/api/schema.d.ts` is generated from FastAPI's OpenAPI schema. Never edit it by hand:

```bash
npm run gen:api        # exports openapi.json from the backend, then regenerates the TypeScript types
```

CI fails if the generated client is out of date.

## Tests

```bash
npm run lint && npm run typecheck && npm run build
npx playwright install chromium --no-shell
npm run test:e2e
```

The Playwright tests start `apps/api/e2e_server.py`: the real API on in-process GigSim and MCP servers with a scripted LLM, so they are fast and repeatable (Postgres from docker compose is needed). They cover onboarding, approving a proposal (with evidence on hover), rejecting with a reason, editing a draft (Compliance re-checks it), the marketplace-unavailable banner, and the phone layout.
