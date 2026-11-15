"""GigSim API behaviour that GigBid and the viva depend on."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gigsim.app import create_app

ROOT = Path(__file__).resolve().parents[2]
ANALYST = {"Authorization": "Bearer dev-data-analyst"}
ADMIN = {"Authorization": "Bearer dev-admin"}
NO_FAULTS = {"error_rate": 0.0, "latency_ms": [0, 0], "seed": 7}


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


def make(tmp_path, **overrides):
    app = create_app({"db_path": str(tmp_path / "sim.sqlite3"), "faults": NO_FAULTS, **overrides})
    return TestClient(app), app.state.engine


@pytest.fixture
def sim(tmp_path):
    client, engine = make(tmp_path)
    client.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    return client, engine


def labels(persona: str) -> list[dict]:
    rows = [json.loads(line) for line in (ROOT / "evals/datasets/dev/labels.jsonl").open(encoding="utf-8")]
    return [r for r in rows if r["persona"] == persona]


def good_letter(engine, job_id: str) -> tuple[str, list[str], float]:
    """A proposal the heuristic client should like: specific, shows must-haves, answers questions."""
    job = engine.world.jobs[job_id]
    must = [m["skill"] for m in engine.world.hidden[job_id]["must_have"]]
    letter = (f"{job['title']}: I have delivered this kind of work before. "
              f"I used {', '.join(must)} on a sales dashboard that cut reporting time by 80%.")
    answers = ["Yes - a Power BI project for 40 managers."] * len(job["screening_questions"])
    bid = job["budget_max"] or 30.0
    return letter, answers, bid


def draft(client, job_id, letter="Hello", bid=50.0, answers=None):
    r = client.post("/proposals", json={"job_id": job_id, "cover_letter": letter, "bid_amount": bid,
                                        "screening_answers": answers or []}, headers={**ANALYST, **key()})
    assert r.status_code == 201, r.text
    return r.json()["proposal_id"]


def test_auth_required(sim):
    client, _ = sim
    assert client.get("/jobs").status_code == 401
    assert client.get("/jobs", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_jobs_are_released_over_time(tmp_path):
    client, engine = make(tmp_path)
    early = client.get("/jobs", headers=ANALYST).json()["total"]
    client.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    assert early < client.get("/jobs", headers=ANALYST).json()["total"] == len(engine.world.jobs)


def test_private_fields_never_leak(sim):
    client, engine = sim
    page = client.get("/jobs", params={"limit": 100}, headers=ANALYST).json()["jobs"]
    for job in page:
        assert "source" not in job and "release_offset_h" not in job
        assert "must_have" not in json.dumps(job) and "budget_ceiling" not in json.dumps(job)
    attacked = next(c for c in engine.world.clients.values() if c["message_attack"])
    view = client.get(f"/clients/{attacked['client_id']}", headers=ANALYST).json()
    assert "message_attack" not in view and "source" not in view


def test_submit_is_exactly_once(sim):
    client, _ = sim
    job_id = labels("data_analyst")[0]["job_id"]
    pid = draft(client, job_id)
    cost = client.post(f"/proposals/{pid}/submit?dry_run=true", headers=ANALYST).json()["connects_cost"]
    k = key()
    first = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **k})
    replay = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **k})
    assert first.status_code == replay.status_code == 200
    assert replay.headers["Idempotent-Replay"] == "true" and replay.json() == first.json()
    again = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **key()})
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_submitted"
    assert client.get("/connects", headers=ANALYST).json()["balance"] == 80 - cost


def test_lost_responses_still_charge_once(tmp_path):
    """Injected errors (some after the work is done) + retries with the same key never double-charge."""
    client, engine = make(tmp_path, faults={"error_rate": 0.6, "latency_ms": [0, 0], "seed": 3})
    client.post("/admin/release_all", json={"on": True}, headers=ADMIN)
    job_id = labels("data_analyst")[1]["job_id"]
    k = key()
    for _ in range(20):  # retry the draft until it gets through
        r = client.post("/proposals", json={"job_id": job_id, "cover_letter": "Hi", "bid_amount": 40},
                        headers={**ANALYST, **k})
        if r.status_code == 201:
            break
    pid = r.json()["proposal_id"]
    k = key()
    codes = []
    for _ in range(20):
        r = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **k})
        codes.append(r.status_code)
        if r.status_code == 200:
            break
    assert 200 in codes
    charges = engine.store.q("SELECT * FROM ledger WHERE reason = 'submit' AND ref = ?", (pid,))
    assert len(charges) == 1


def test_idempotency_key_required_and_not_reusable(sim):
    client, _ = sim
    job_id = labels("data_analyst")[2]["job_id"]
    body = {"job_id": job_id, "cover_letter": "Hi", "bid_amount": 40}
    assert client.post("/proposals", json=body, headers=ANALYST).status_code == 400
    k = key()
    assert client.post("/proposals", json=body, headers={**ANALYST, **k}).status_code == 201
    other = client.post("/proposals", json={**body, "bid_amount": 99}, headers={**ANALYST, **k})
    assert other.status_code == 422 and other.json()["error"]["code"] == "idempotency_key_reused"


def test_policy_violation_blocks_submit_and_charges_nothing(sim):
    client, _ = sim
    job_id = labels("data_analyst")[3]["job_id"]
    pid = draft(client, job_id, letter="Great fit! Email me at someone@example.com to continue.")
    preview = client.post(f"/proposals/{pid}/submit?dry_run=true", headers=ANALYST).json()
    assert preview["policy_violations"][0]["rule_id"] == "no_contact_details"
    r = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **key()})
    assert r.status_code == 422 and r.json()["error"]["violations"][0]["rule_id"] == "no_contact_details"
    assert client.get("/connects", headers=ANALYST).json()["balance"] == 80


def test_insufficient_connects(sim):
    client, engine = sim
    engine.world.policy["connects"]["cost_multiplier"] = 100
    pid = draft(client, labels("data_analyst")[4]["job_id"])
    r = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **key()})
    assert r.status_code == 402


def test_rate_limit(tmp_path):
    client, _ = make(tmp_path, rate_limit={"requests_per_minute": 3, "submits_per_minute": 1})
    codes = [client.get("/connects", headers=ANALYST).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_outage_switch(sim):
    client, _ = sim
    client.post("/admin/faults", json={"down": True}, headers=ADMIN)
    assert client.get("/jobs", headers=ANALYST).status_code == 503
    assert client.get("/health").status_code == 200
    client.post("/admin/faults", json={"down": False}, headers=ADMIN)
    assert client.get("/jobs", headers=ANALYST).status_code == 200


def test_bid_over_ceiling_is_ignored(sim):
    client, engine = sim
    lab = next(r for r in labels("data_analyst") if r["bid"])
    letter, answers, _ = good_letter(engine, lab["job_id"])
    ceiling = engine.world.hidden[lab["job_id"]]["budget_ceiling"]
    pid = draft(client, lab["job_id"], letter, ceiling * 2, answers)
    r = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **key()}).json()
    assert r["status"] == "lost" and [h["status"] for h in r["history"]][-2:] == ["viewed", "lost"]


def test_conversation_to_interview_and_message_attack(sim):
    client, engine = sim
    # A bid-worthy job whose client has a planted message attack.
    lab = next(r for r in labels("data_analyst")
               if r["bid"] and engine.world.clients[engine.world.jobs[r["job_id"]]["client_id"]]["message_attack"])
    letter, answers, bid = good_letter(engine, lab["job_id"])
    pid = draft(client, lab["job_id"], letter, bid, answers)
    sub = client.post(f"/proposals/{pid}/submit", headers={**ANALYST, **key()}).json()
    assert sub["status"] in ("replied", "interview"), client.get(f"/admin/proposals/{pid}", headers=ADMIN).json()
    thread = client.get(f"/threads/{sub['thread_id']}", headers=ANALYST).json()
    attack = engine.world.clients[engine.world.jobs[lab["job_id"]]["client_id"]]["message_attack"]
    assert attack["text"] in thread["messages"][0]["body"]
    r = client.post(f"/threads/{sub['thread_id']}/messages",
                    json={"body": "I can do Tuesday 3pm or Wednesday 11am UTC."}, headers={**ANALYST, **key()})
    assert r.json()["status"] == "interview"


def test_admin_can_be_disabled(tmp_path):
    client, _ = make(tmp_path, admin_enabled=False)
    assert client.post("/admin/release_all", json={"on": True}, headers=ADMIN).status_code == 404
