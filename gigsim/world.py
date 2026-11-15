"""Read-only world: the scenario pack, market data, persona profiles and the policy.

Loaded once at start-up. Nothing here changes while GigSim runs; all mutable state
(proposals, Connects, threads) lives in SQLite (store.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from gigsim.config import GIGSIM_DIR, REPO_ROOT, pack_dir

# Fields that exist in the pack files but must never leave GigSim.
PRIVATE_JOB_FIELDS = {"source", "release_offset_h"}
PRIVATE_CLIENT_FIELDS = {"source", "message_attack"}


def _jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@dataclass
class World:
    jobs: dict[str, dict]
    jobs_by_release: list[dict]           # sorted by release time
    clients: dict[str, dict]
    hidden: dict[str, dict]
    market_stats: dict
    market_history: list[dict]
    personas: dict[str, dict]
    policy: dict
    sim_start: datetime

    @classmethod
    def load(cls, cfg: dict) -> World:
        d = pack_dir(cfg["pack"])
        sim_start = datetime.fromisoformat(cfg["sim_start"])
        jobs = _jsonl(d / "jobs.jsonl")
        for j in jobs:
            j["posted_at"] = (sim_start + timedelta(hours=j["release_offset_h"])).isoformat()
        jobs.sort(key=lambda j: (j["release_offset_h"], j["job_id"]))
        market = GIGSIM_DIR / "scenarios/market"
        personas = {}
        for p in sorted((REPO_ROOT / "data/personas").glob("*/skeleton.yaml")):
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            personas[s["id"]] = s
        policy = yaml.safe_load((GIGSIM_DIR / "policies" / f"{cfg['policy']}.yaml")
                                .read_text(encoding="utf-8"))
        return cls(
            jobs={j["job_id"]: j for j in jobs},
            jobs_by_release=jobs,
            clients={c["client_id"]: c for c in _jsonl(d / "clients.jsonl")},
            hidden={h["job_id"]: h for h in _jsonl(d / "hidden.jsonl")},
            market_stats=json.loads((market / "stats.json").read_text(encoding="utf-8")),
            market_history=_jsonl(market / "history.jsonl"),
            personas=personas,
            policy=policy,
            sim_start=sim_start,
        )


def public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k not in PRIVATE_JOB_FIELDS}


def public_client(client: dict) -> dict:
    return {k: v for k, v in client.items() if k not in PRIVATE_CLIENT_FIELDS}


def public_profile(persona: dict) -> dict:
    """What a client can see about a freelancer: listed skills and portfolio, not implied skills."""
    return {
        "name": persona["name"],
        "headline": persona["headline"],
        "location": persona["location"],
        "years_experience": persona["years_experience"],
        "hourly_rate": persona["hourly_rate"],
        "skills": persona["listed_skills"],
        "portfolio": [
            {"title": p["title"], "year": p["year"], "client_industry": p["client_industry"],
             "skills": p["skills"], "outcome": p["outcome"], "rating": p["rating"]}
            for p in persona["projects"]
        ],
    }
