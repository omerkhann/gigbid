# Portfolio MCP server

Give an AI assistant (Claude Desktop, Cursor, or GigBid's agents) **read-only** access to your freelance portfolio. It can then answer screening questions, draft proposals and check your fit for a job using *your real evidence*, and cite exactly where each claim comes from.

## What it offers

| Kind | Name | What it does |
|---|---|---|
| Tool | `search_evidence(requirement, k, filters)` | Finds evidence for one job requirement across your CV, case studies, repo READMEs and code, client reviews and past proposals. Each item has its type, source file, date, project and, for past proposals, the outcome (won / replied / ignored). Filters: `types`, `project_id`, `since_year`, `outcomes` |
| Tool | `get_case_study(id)` | A full case study with the project facts, client review and linked repo |
| Tool | `list_skills()` | Skills on your profile or named in projects, with the projects that show each one |
| Resource | `portfolio://case/{id}`, `portfolio://proposal/{id}`, `portfolio://repo/{name}`, `portfolio://cv` | Load a full item into the conversation |
| Prompt | *Answer a screening question from my portfolio* | Short, cited answer; never invents experience |
| Prompt | *Draft a proposal from my portfolio* | One search per requirement, 1–2 cited projects, under 200 words |
| Prompt | *Check my fit for a job* | Each requirement marked strong / partial / missing, plus a bid or skip suggestion |

All tools are read-only. Nothing in your portfolio is changed.

## Your portfolio folder

```
my-portfolio/
  skeleton.yaml            # profile + one entry per project (id, title, year, industry, skills, outcome, rating)
  cv.pdf                   # or cv.md
  case_studies/<project_id>.md
  repos/<repo>/README.md   # plus code; repos/<repo>/.project.json = {"project_id": "..."}
  reviews.jsonl            # {"project_id", "rating", "text"}
  past_proposals.jsonl     # {"proposal_id", "date", "job_title", "text", "cited_projects", "outcome"}
```

Only `skeleton.yaml` is required; every other part is optional. See [`data/personas/data_analyst/`](../../data/personas/data_analyst/) for a complete (synthetic) example.

## Use it from Claude Desktop

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), and [Ollama](https://ollama.com) with `ollama pull nomic-embed-text` (embeddings run locally; nothing about your portfolio leaves your machine).

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "portfolio": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/gigbid", "python", "-m", "mcp_servers.portfolio.server",
               "--stdio", "--portfolio-dir", "/path/to/my-portfolio"]
    }
  }
}
```

The first search embeds your portfolio (a minute or two); after that, embeddings are cached and searches take milliseconds. Adding an item only embeds that item.

## Use it from GigBid (HTTP)

```bash
python -m mcp_servers.portfolio.server     # Streamable HTTP at http://127.0.0.1:8203/mcp, bearer auth
```

`PORTFOLIO_USERS` maps each bearer token to a user and their portfolio folder. Every call is rate-limited and written to an append-only audit log with emails and phone numbers masked.

| Variable | Default | Meaning |
|---|---|---|
| `PORTFOLIO_VARIANT` | `v0_naive` | Retrieval design (see `rag/variants/`); chosen by evaluation |
| `PORTFOLIO_EMBEDDER` | `ollama:nomic-embed-text` | Any Ollama embedding model, or `hash` for offline tests |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama address |

## Design notes

- **Implied skills stay implied.** Metadata lists only skills a project *names*. If a skill appears only in your code, metadata filters won't reveal it; search has to find it in the code itself.
- **Windows stdio fix.** The index is built before the server starts reading stdin. Importing numpy for the first time from a worker thread while stdin is being read deadlocks on Windows.
