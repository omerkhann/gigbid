# Persona Corpus Design

Status: agreed scope, 2026-11-15. All persona data is **synthetic**: fictional people, clients and projects.

The assignment provides "three freelancer personas: AI/ML engineer, full-stack web developer, data analyst. Each has a CV, 15 to 25 case studies, repo READMEs and code, client reviews, and about 150 past proposals labelled won, replied or ignored." The corpus is "built to defeat naive RAG: code and prose mixed, the same project described three ways, skills implied rather than named, and past proposals whose outcome matters more than their wording." We build it ourselves from the hand-written skeletons in `data/personas/*/skeleton.yaml`.

## 1. Files per persona

```
data/personas/<id>/
  skeleton.yaml            # hand-written ground truth (projects, skills, traps)
  cv.md, cv.pdf            # generated from the skeleton by a template (no LLM)
  case_studies/<project>.md        # one per project (15-18), LLM-written
  repos/<repo>/README.md + code    # 5-7 repos, LLM-written
  reviews.jsonl            # one client review per rated project, LLM-written
  past_proposals.jsonl     # 150 proposals with outcomes, LLM-written text
  manifest.json            # what was generated, by which model, plus trap index
```

Every file and record carries its `project_id` where it has one, so retrieval results can be scored against `gold_evidence` (which is at project level).

## 2. How the RAG traps are planted

The skeleton already marks each project's traps; the generator follows them.

| Trap (assignment wording) | How it is built |
|---|---|
| Skills implied rather than named | Projects tagged `implied_named_differently`: prompts say "describe X as Y and never write the word X" (Celery as "a background job queue", VBA as "Excel macros", Shopify as "a hosted store platform") |
| Code and prose mixed | Projects tagged `code_only:<skill>`: the case study must not mention the skill; it appears only in the repo's code (an import, a query, a config file) |
| Same project described three ways | Projects tagged `three_descriptions`: the case study uses the project title, the README uses a code name and a technical framing, and at least two past proposals describe it in a third way, from the client's point of view |
| Outcome matters more than wording | Past proposals come in four styles (section 3). Polished but generic proposals usually lost; plain but specific ones often won |
| Outdated evidence | Projects tagged `outdated` (2020–2021, older stack) stay in the corpus and are dated, so retrieval that ignores dates can surface them |

## 3. Past proposals and their outcomes

150 per persona. Each one answers a real historical job: a job post from the 60k dataset that is in **none** of GigSim's sets, so no past proposal can leak a dev or test job.

| Style | Share | What it looks like | Outcome odds (won / replied / ignored) |
|---|---|---|---|
| `strong` | 30% | Opens on the client's problem, cites 1–2 relevant projects with real numbers | 30% / 35% / 35% |
| `plain_specific` | 20% | Short and plain, but names one relevant project and result | 20% / 35% / 45% |
| `polished_generic` | 25% | Fluent, confident, full of buzzwords, no concrete evidence | 3% / 12% / 85% |
| `generic` | 25% | Template that could go to any job | 1% / 6% / 93% |

On top of style, 15% of proposals are overpriced (bid above 1.3× the client's budget); those are pushed to "ignored" 70% of the time.

**Outcomes come from these rules plus a seeded random draw, not from GigSim's client.** Labelling 450 proposals through the client would take about an hour on Groq's free tier. The rules encode the same preferences the client prompt describes (specific openings, concrete evidence, fair price). We will check that on a sample: 30 random past proposals run through the LLM client, reporting how often the two agree.

Each record: `proposal_id`, `date`, `job_title`, `job_excerpt`, `category`, `bid`, `budget`, `text`, `cited_projects`, `style`, `overpriced`, `outcome`, `outcome_note`.

## 4. Generation

- **Models:** gpt-oss-120b (case studies, READMEs) and gpt-oss-20b (code, reviews, past proposals) on Groq. They run in parallel because each model has its own rate limit. The Qwen model used by GigSim's client writes nothing here, so the client never judges text in its own style.
- **Resumable:** every LLM task is cached under `data/processed/persona_gen/` by a hash of its prompt. Stopping and rerunning continues where it left off and never re-pays for finished work.
- **Deterministic plan:** which projects get repos, which jobs, styles, bids and outcomes are all decided by a seeded plan before any LLM call. LLMs only write the text.
- **Checks after generation:** forbidden words absent (implied skills not named in prose, `code_only` skills absent from case studies), each `three_descriptions` project has its case study, README and at least two proposals, and counts per persona.

Command: `python -m pipelines.build_personas` (add `--plan-only` to print the plan without calling any model).

## 5. Results (generated 2026-11-15)

| Persona | Case studies | Repos | Reviews | Past proposals | Won / replied / ignored | Trap checks |
|---|---|---|---|---|---|---|
| ml_engineer | 18 | 7 | 17 (one project unrated) | 150 | 17 / 36 / 97 | 7/7 |
| fullstack_dev | 16 | 6 | 16 | 150 | 18 / 26 / 106 | 7/7 |
| data_analyst | 15 | 5 | 15 | 150 | 23 / 25 / 102 | 5/5 |

Trap checks: each `code_only` skill is absent from its case study and present in its repo's code; each `three_descriptions` project has a case study, a README under a code name and at least two citing proposals. Each persona's `manifest.json` lists every check.

**Spot check (ml-p01, three ways):** case study "Automated Support-Ticket Triage for a SaaS Helpdesk", repo `ticket-ninja`, and a proposal describing "a support-ticket triage system that routed 78% of tickets". PostgreSQL for ml-p02 appears only in `repos/policy-rag/app/celery_tasks.py`.

**Known leak, accepted:** case studies and READMEs never name implied skills. Some *past proposals* do:

| Persona | Proposals naming an implied skill | Of those, because the job itself names it |
|---|---|---|
| ml_engineer | 4 / 150 | 4 |
| fullstack_dev | 51 / 150 | 45 (mostly "Shopify" or "WordPress" jobs) |
| data_analyst | 20 / 150 | 7 (the rest are everyday phrases like "A/B testing") |

A freelancer answering a Shopify job naturally writes "Shopify", so we keep these rather than force awkward wording. The implied-skill trap is about the persona's *evidence* (case studies, repos), and there it holds. Past proposals are also realistic in their flaws: a few make claims a Compliance Guard would reject (for example "zero-risk"), which is useful for learning what not to repeat.

Generation notes: 163 LLM tasks; 19 proposal batches still contained a hidden skill name after 3 attempts (logged in the manifests); one incomplete batch was regenerated.
