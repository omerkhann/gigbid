# Architecture decision records

One short record per major choice: the context, what was decided, what else was considered, and what it costs.

| # | Decision |
|---|---|
| [0001](0001-hand-built-langgraph.md) | Hand-built LangGraph `StateGraph` for both graphs |
| [0002](0002-mcp-as-tool-boundary.md) | Every external capability behind an MCP server, with per-agent allowlists |
| [0003](0003-simple-gigsim.md) | A deliberately simple, deterministic GigSim |
| [0004](0004-open-models-per-node.md) | Open-weight models, chosen per node in config, with fallback chains |
| [0005](0005-postgres-and-arq.md) | Postgres for checkpoints, memory and app data; Arq on Redis for background work |
| [0006](0006-verify-before-critic.md) | Claim verification before the Critic; the Critic fails soft |
| [0007](0007-rules-for-decisions.md) | Rules, not an LLM, for skip/watch/bid and for the risk score |
| [0008](0008-retrieval-pipeline-switches.md) | One retrieval pipeline with switchable components; CPU reranker choice |
| [0009](0009-same-origin-ui.md) | Same-origin UI through a proxy, live updates over SSE |
