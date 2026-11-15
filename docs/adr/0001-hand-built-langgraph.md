# 0001 Hand-built LangGraph StateGraph for both graphs

**Context.** The bid flow has parallel analyses, a rule-based decision, a bounded revise loop, a policy gate that can block, and a human approval that may wait for days and must survive a crash. The assignment also asks for a comparison against a single agent and a prebuilt supervisor.

**Decision.** Two hand-written `StateGraph`s: the bid graph (one thread per job) and the conversation graph (one thread per client thread). The three analyses fan out with `Send`; each writes its own state key, so there are no reducer conflicts. Approval is `interrupt()`, resumed with `Command(resume=...)`. Budgets (30 steps, 40k tokens, 2 revisions; `agent/config.yaml`) are checked between nodes and move the run to `needs_attention`.

**Alternatives.** A single ReAct agent with all tools: simplest, but nothing guarantees the order (it can draft before checking risk), and there is no natural place for the approval gate. The prebuilt `langgraph-supervisor`: an LLM routes every hop, which costs tokens and makes the path non-deterministic. Both are baselines for R&D question C.

**Consequences.** Every path is visible in code and in traces, and each edge can be unit-tested. The cost: new behaviour needs a node and an edge, not just a prompt change.
