# Signature extension: X3, portfolio builder

**Turn a GitHub account into case studies automatically, verified against the code, and feed them to the Portfolio server.**

## Why

A freelancer's best evidence is often code they never wrote up. The persona corpus is built around exactly this: skills *implied* by a project's code but never named in its profile. Retrieval can't cite a case study that doesn't exist. And an LLM asked to "write a case study about this repo" will happily invent clients and results, which GigBid must never claim.

## What it does

```
GitHub account ──(GitHub's official MCP server: search_repositories, get_file_contents; read-only token)──┐
or a folder of repos ─────────────────────────────────────────────────────────────────────────────────────┤
                                                                                                          ▼
  per repo: README + up to 12 source files (bounded, 3k chars each)
     → draft (Writer tier, prompt agent/prompts/portfolio_builder.md): title, summary, Problem / What I built / Stack,
       a [file path] citation after every factual sentence, technologies actually used in the code
     → verify (rag/verify.py, the same verifier the bid graph uses): each claim checked against the files;
       unsupported claims removed
     → write: case_studies/<id>.md, repos/<repo>/ (+ .project.json), skeleton.yaml
  → point the Portfolio MCP server at the folder (PORTFOLIO_DIR or PORTFOLIO_USERS): searchable immediately
```

```bash
python -m rag.ingest.portfolio_builder --github <username> --out my-portfolio     # GITHUB_TOKEN: read-only, public repos
python -m rag.ingest.portfolio_builder --repos path/to/repos --out my-portfolio   # local folder
```

Each generated case study ends with its source and the number of unsupported claims removed, so the freelancer can see what was dropped.

**Trust rationale for GitHub's MCP server (A5):** it is GitHub's own server, run from its published Docker image with a read-only, public-repositories token, and with only the `repos` toolset enabled. It can read code and nothing else.

## How it was measured

`python -m evals.runners.x3_eval --personas ml_engineer`, results in `evals/results/x3_eval.json`. Case studies are built from the persona's **repos only**, then compared with the persona's ground truth (`skeleton.yaml`):

| Metric | Meaning |
|---|---|
| Claims supported before verification | How often the draft model stays inside the evidence by itself |
| Unsupported claims removed | What verification caught (0 remain in the written case studies) |
| Named-skill recall | Profile skills of the project that the case study mentions |
| Implied-skill recall | Skills the project uses but its profile never names: the reason to read the code |

Results are in the R&D report, §7.

## Limits

- Only the first 12 relevant files per repo are read, so large repos are summarised from their README and top-level code.
- The verifier judges support from the files shown. A claim supported only by a file that wasn't selected is removed, which errs on the safe side.
- No results or client names are ever generated. Repos rarely contain them, so generated case studies describe what was built, not how well it did. The freelancer adds outcomes by hand.
