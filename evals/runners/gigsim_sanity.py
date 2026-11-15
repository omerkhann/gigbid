"""Check that GigSim's simulated client prefers good proposals (design section 5.4).

Runs GigSim in-process (no server needed) in eval mode against the dev pack, submits the
hand-written proposals from evals/datasets/gigsim_sanity.yaml and records each decision.

  python -m evals.runners.gigsim_sanity            # LLM client (needs GROQ_API_KEY)
  python -m evals.runners.gigsim_sanity heuristic  # keyword client, no API key

Writes evals/results/gigsim_sanity_<mode>.json.
"""

from __future__ import annotations

import json
import sys
import tempfile
import uuid
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from gigsim.app import create_app

ROOT = Path(__file__).resolve().parents[2]
TOKENS = {"data_analyst": "dev-data-analyst", "ml_engineer": "dev-ml-engineer",
          "fullstack_dev": "dev-fullstack-dev"}
ADMIN = {"Authorization": "Bearer dev-admin"}
POSITIVE = ("reply", "interview")


def run(mode: str) -> dict:
    load_dotenv(ROOT / ".env")
    spec = yaml.safe_load((ROOT / "evals/datasets/gigsim_sanity.yaml").read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        # A fresh sim per variant, so "one proposal per job" doesn't block the comparison.
        # The LLM cache is separate per run here, so the API is called for every proposal.
        for variant in ("good", "generic", "fabricated"):
            app = create_app({"db_path": str(Path(tmp) / f"{variant}.sqlite3"),
                              "faults": {"error_rate": 0, "latency_ms": [0, 0], "seed": 1},
                              "client": {**_client_cfg(), "mode": mode}})
            client = TestClient(app)
            client.post("/admin/release_all", json={"on": True}, headers=ADMIN)
            auth = {"Authorization": f"Bearer {TOKENS[spec['persona']]}"}
            for job in spec["jobs"]:
                if variant == "generic":
                    letter, answers = job["generic"], []
                else:
                    letter, answers = job["good"], job.get("good_answers", [])
                    if variant == "fabricated":
                        letter = f"{letter}\n\n{spec['fabricated_suffix']}"
                r = client.post("/proposals", json={"job_id": job["job_id"], "cover_letter": letter,
                                                    "bid_amount": job["bid"], "screening_answers": answers},
                                headers={**auth, "Idempotency-Key": uuid.uuid4().hex})
                r.raise_for_status()
                pid = r.json()["proposal_id"]
                client.post(f"/proposals/{pid}/submit", headers={**auth, "Idempotency-Key": uuid.uuid4().hex})
                detail = client.get(f"/admin/proposals/{pid}", headers=ADMIN).json()
                d = detail["decision"]
                results.append({"job_id": job["job_id"], "variant": variant, "decision": d["decision"],
                                "reason": d["reason"], "unsupported_claims": d.get("unsupported_claims", [])})
                print(f"{variant:10s} {job['job_id']}  {d['decision']:9s}  {d['reason'][:90]}")
            app.state.engine.store.conn.close()

    rate = {v: sum(r["decision"] in POSITIVE for r in results if r["variant"] == v) / len(spec["jobs"])
            for v in ("good", "generic", "fabricated")}
    flagged = sum(bool(r["unsupported_claims"]) for r in results if r["variant"] == "fabricated")
    out = {"mode": mode, "model": _client_cfg()["llm"]["model"] if mode == "llm" else None,
           "positive_rate": rate, "fabricated_flagged": f"{flagged}/{len(spec['jobs'])}",
           "checks": {"good_beats_generic": rate["good"] > rate["generic"],
                      "good_beats_fabricated": rate["good"] > rate["fabricated"] or flagged == len(spec["jobs"])},
           "results": results}
    path = ROOT / f"evals/results/gigsim_sanity_{mode}.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out


def _client_cfg() -> dict:
    from gigsim.config import load_config
    return load_config()["client"]


if __name__ == "__main__":
    summary = run(sys.argv[1] if len(sys.argv) > 1 else "llm")
    print(json.dumps({k: summary[k] for k in ("mode", "model", "positive_rate", "fabricated_flagged",
                                              "checks")}, indent=2))
