"""Marketplace rules: job visibility, search, proposals, Connects, threads.

Framework-free on purpose (app.py is the only FastAPI code), so the rules can be unit-tested
directly and read in one place.

Time: sim hours since sim_start, = wall seconds since reset x speed / 3600. Future status
changes ("viewed in 5 sim hours") are stored with a future at_h and only become visible once
the clock passes them, so GigSim needs no background worker. In eval mode (POST
/admin/release_all) every job is visible and clients answer instantly.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import timedelta

from gigsim import policy as pol
from gigsim.client import SimulatedClient
from gigsim.store import Store
from gigsim.world import World, public_client, public_job, public_profile

STATUSES = ("draft", "submitted", "viewed", "replied", "interview", "hired", "lost")


class SimError(Exception):
    def __init__(self, status: int, code: str, detail: str, extra: dict | None = None):
        super().__init__(detail)
        self.status, self.code, self.detail, self.extra = status, code, detail, extra or {}


def _hash_unit(*parts: str) -> float:
    """Deterministic number in [0, 1) from the given strings."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:12], 16) / 16**12


def _sid(prefix: str, *parts: str) -> str:
    return f"{prefix}-{hashlib.sha1('|'.join(parts).encode()).hexdigest()[:12]}"


class Engine:
    def __init__(self, cfg: dict, world: World, store: Store):
        self.cfg, self.world, self.store = cfg, world, store
        self.client = SimulatedClient(cfg, store)
        self.accounts = {a["token"]: a for a in cfg["accounts"]}
        if store.get_meta("start_wall") is None:
            store.set_meta("start_wall", time.time())

    # --- clock ---------------------------------------------------------------------------

    def now_h(self) -> float:
        return (time.time() - self.store.get_meta("start_wall")) * self.cfg["speed"] / 3600

    def eval_mode(self) -> bool:
        return bool(self.store.get_meta("eval_mode", False))

    def iso(self, at_h: float) -> str:
        return (self.world.sim_start + timedelta(hours=at_h)).isoformat()

    def _delay(self, key: str, rng: list[float]) -> float:
        return 0.0 if self.eval_mode() else rng[0] + (rng[1] - rng[0]) * _hash_unit(key)

    # --- jobs and clients ----------------------------------------------------------------

    def _visible(self, job: dict) -> bool:
        return self.eval_mode() or job["release_offset_h"] <= self.now_h()

    def _open(self, job: dict) -> bool:
        return self.eval_mode() or self.now_h() <= job["release_offset_h"] + self.cfg["job_open_hours"]

    def _job(self, job_id: str) -> dict:
        job = self.world.jobs.get(job_id)
        if job is None or not self._visible(job):
            raise SimError(404, "job_not_found", f"No job {job_id}")
        return job

    def search_jobs(self, q: str | None, category: str | None, skills: list[str],
                    min_budget: float | None, since: str | None, cursor: int, limit: int) -> dict:
        terms = [t for t in (q or "").lower().split() if t]
        want_skills = {s.lower() for s in skills}
        hits = []
        for job in reversed(self.world.jobs_by_release):          # newest first
            if not self._visible(job):
                continue
            if category and job["category"] != category:
                continue
            if since and job["posted_at"] <= since:
                continue
            if min_budget is not None and (job["budget_max"] or 0) < min_budget:
                continue
            if want_skills and not want_skills & {s.lower() for s in job["required_skills"]}:
                continue
            text = f"{job['title']} {job['description']}".lower()
            if terms and not all(t in text for t in terms):
                continue
            hits.append(job)
        page = hits[cursor: cursor + limit]
        nxt = cursor + limit if cursor + limit < len(hits) else None
        return {"jobs": [self._job_view(j) for j in page], "total": len(hits),
                "next_cursor": None if nxt is None else str(nxt)}

    def _job_view(self, job: dict) -> dict:
        view = public_job(job)
        view["open"] = self._open(job)
        view["connects_cost"] = pol.connects_cost(self.world.policy, job)
        return view

    def get_job(self, job_id: str) -> dict:
        return self._job_view(self._job(job_id))

    def get_client(self, client_id: str) -> dict:
        client = self.world.clients.get(client_id)
        posted = [j for j in self.world.jobs_by_release
                  if j["client_id"] == client_id and self._visible(j)]
        if client is None or not posted:
            raise SimError(404, "client_not_found", f"No client {client_id}")
        view = public_client(client)
        view["jobs_posted"] = [{"job_id": j["job_id"], "title": j["title"], "posted_at": j["posted_at"]}
                               for j in posted]
        return view

    # --- accounts and Connects -----------------------------------------------------------

    def account(self, token: str) -> dict:
        acc = self.accounts.get(token)
        if acc is None:
            raise SimError(401, "unauthorized", "Unknown or missing bearer token")
        return acc

    def me(self, acc: dict) -> dict:
        return {"freelancer_id": acc["freelancer_id"], "persona": acc["persona"],
                "profile": public_profile(self.world.personas[acc["persona"]])}

    def _grant_weeks(self, fid: str) -> None:
        grant = self.world.policy["connects"]["weekly_grant"]
        for week in range(math.floor(self.now_h() / 168) + 1):
            self.store.run("INSERT OR IGNORE INTO ledger(freelancer_id, delta, reason, ref, at_h) "
                           "VALUES (?, ?, 'weekly_grant', ?, ?)", (fid, grant, f"week-{week}", week * 168))

    def balance(self, fid: str) -> int:
        self._grant_weeks(fid)
        return self.store.one("SELECT COALESCE(SUM(delta), 0) AS b FROM ledger WHERE freelancer_id = ?",
                              (fid,))["b"]

    def connects(self, fid: str) -> dict:
        bal = self.balance(fid)
        rows = self.store.q("SELECT delta, reason, ref, at_h FROM ledger WHERE freelancer_id = ? "
                            "ORDER BY id", (fid,))
        return {"balance": bal, "ledger": [{"delta": r["delta"], "reason": r["reason"],
                                            "ref": r["ref"], "at": self.iso(r["at_h"])} for r in rows]}

    # --- proposals -----------------------------------------------------------------------

    def upsert_draft(self, fid: str, job_id: str, cover_letter: str, bid_amount: float,
                     screening_answers: list[str]) -> dict:
        job = self._job(job_id)
        if not self._open(job):
            raise SimError(409, "job_closed", "This job no longer accepts proposals")
        pid = _sid("prop", fid, job_id)
        with self.store.lock:
            row = self.store.one("SELECT submitted_at FROM proposals WHERE proposal_id = ?", (pid,))
            if row and row["submitted_at"]:
                raise SimError(409, "already_submitted", "A proposal for this job was already submitted",
                               {"proposal_id": pid})
            bid_type = "hourly" if job["payment_type"] == "hourly" else "fixed"
            now = self.now_h()
            self.store.run(
                "INSERT INTO proposals(proposal_id, freelancer_id, job_id, bid_amount, bid_type, "
                "cover_letter, answers_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(proposal_id) DO UPDATE SET bid_amount = excluded.bid_amount, "
                "cover_letter = excluded.cover_letter, answers_json = excluded.answers_json",
                (pid, fid, job_id, bid_amount, bid_type, cover_letter, json.dumps(screening_answers),
                 self.iso(now)))
            if not row:
                self.store.run("INSERT INTO status_events(proposal_id, status, at_h) VALUES (?, 'draft', ?)",
                               (pid, now))
        return self.get_proposal(fid, pid)

    def _proposal_row(self, fid: str, pid: str):
        row = self.store.one("SELECT * FROM proposals WHERE proposal_id = ? AND freelancer_id = ?",
                             (pid, fid))
        if row is None:
            raise SimError(404, "proposal_not_found", f"No proposal {pid}")
        return row

    def submit(self, fid: str, pid: str, dry_run: bool) -> dict:
        with self.store.lock:
            row = self._proposal_row(fid, pid)
            if row["submitted_at"]:
                raise SimError(409, "already_submitted", "This proposal was already submitted")
            job = self._job(row["job_id"])
            if not self._open(job):
                raise SimError(409, "job_closed", "This job no longer accepts proposals")
            answers = json.loads(row["answers_json"])
            text = "\n".join([row["cover_letter"], *answers])
            found = pol.violations(self.world.policy, text)
            cost = pol.connects_cost(self.world.policy, job)
            balance = self.balance(fid)
            day = math.floor(self.now_h() / 24)
            today = self.store.one(
                "SELECT COUNT(*) AS n FROM status_events e JOIN proposals p USING(proposal_id) "
                "WHERE p.freelancer_id = ? AND e.status = 'submitted' AND e.at_h >= ? AND e.at_h < ?",
                (fid, day * 24, day * 24 + 24))["n"]
            limit = self.world.policy["limits"]["max_submits_per_sim_day"]
            preview = {
                "would_send": {"job_id": job["job_id"], "bid_amount": row["bid_amount"],
                               "bid_type": row["bid_type"], "cover_letter": row["cover_letter"],
                               "screening_answers": answers},
                "connects_cost": cost, "balance": balance, "balance_after": balance - cost,
                "policy_violations": found, "policy_version": self.world.policy["version"],
            }
            if dry_run:
                return {"dry_run": True, **preview}
            if found:
                raise SimError(422, "policy_violation", "Proposal breaks marketplace policy",
                               {"violations": found})
            if today >= limit:
                raise SimError(422, "policy_violation", "Daily submission limit reached",
                               {"violations": [{"rule_id": "max_submits_per_sim_day",
                                                "description": f"At most {limit} per sim day"}]})
            if balance < cost:
                raise SimError(402, "insufficient_connects", f"Need {cost} Connects, have {balance}")
            now = self.now_h()
            self.store.run("INSERT INTO ledger(freelancer_id, delta, reason, ref, at_h) "
                           "VALUES (?, ?, 'submit', ?, ?)", (fid, -cost, pid, now))
            self.store.run("UPDATE proposals SET submitted_at = ?, connects_cost = ? WHERE proposal_id = ?",
                           (self.iso(now), cost, pid))
            self.store.run("INSERT INTO status_events(proposal_id, status, at_h) VALUES (?, 'submitted', ?)",
                           (pid, now))
        # The client decision may call an LLM, so it runs outside the lock. If it fails it is
        # retried on the next read (_ensure_decision), and the submit itself is already safe.
        self._ensure_decision(pid)
        return self.get_proposal(fid, pid)

    def _ensure_decision(self, pid: str) -> None:
        row = self.store.one("SELECT * FROM proposals WHERE proposal_id = ?", (pid,))
        if row is None or not row["submitted_at"] or row["decision_json"]:
            return
        job = self.world.jobs[row["job_id"]]
        hidden = self.world.hidden[job["job_id"]]
        client = self.world.clients[job["client_id"]]
        acc = next(a for a in self.accounts.values() if a["freelancer_id"] == row["freelancer_id"])
        persona = self.world.personas[acc["persona"]]
        proposal = {"bid_amount": row["bid_amount"], "cover_letter": row["cover_letter"],
                    "screening_answers": json.loads(row["answers_json"])}
        try:
            decision = self.client.decide(job, hidden, client, persona, proposal)
        except Exception as exc:  # noqa: BLE001 - client failures must not break the marketplace
            self.store.set_meta(f"decision_error:{pid}", str(exc))
            return
        with self.store.lock:
            if self.store.one("SELECT decision_json FROM proposals WHERE proposal_id = ?", (pid,))["decision_json"]:
                return
            sub = self.store.one("SELECT at_h FROM status_events WHERE proposal_id = ? AND status = 'submitted'",
                                 (pid,))["at_h"]
            ccfg = self.cfg["client"]
            viewed = sub + self._delay(f"{pid}:view", ccfg["view_delay_hours"])
            events = [("viewed", viewed)]
            if decision["decision"] == "ignore":
                events.append(("lost", viewed + (0 if self.eval_mode() else self.cfg["ignored_to_lost_hours"])))
            else:
                at = viewed + self._delay(f"{pid}:reply", ccfg["reply_delay_hours"])
                status = "interview" if decision["decision"] == "interview" else "replied"
                events.append((status, at))
                tid = _sid("thr", pid)
                self.store.run("INSERT OR IGNORE INTO threads(thread_id, proposal_id, freelancer_id, job_id, "
                               "client_id, state, opened_at_h) VALUES (?, ?, ?, ?, ?, 'open', ?)",
                               (tid, pid, row["freelancer_id"], job["job_id"], job["client_id"], at))
                body = decision.get("message") or "Thanks for your proposal - could you tell me more?"
                attack = client.get("message_attack")
                if attack:
                    body = f"{body}\n\n{attack['text']}"
                self.store.run("INSERT INTO messages(thread_id, sender, body, at_h, meta_json) "
                               "VALUES (?, 'client', ?, ?, ?)",
                               (tid, body, at, json.dumps({"attack": attack["type"] if attack else None})))
            for status, at in events:
                self.store.run("INSERT INTO status_events(proposal_id, status, at_h) VALUES (?, ?, ?)",
                               (pid, status, at))
            self.store.run("UPDATE proposals SET decision_json = ? WHERE proposal_id = ?",
                           (json.dumps(decision), pid))

    def get_proposal(self, fid: str, pid: str) -> dict:
        self._ensure_decision(pid)
        row = self._proposal_row(fid, pid)
        now = self.now_h()
        events = self.store.q("SELECT status, at_h FROM status_events WHERE proposal_id = ? "
                              "AND (at_h <= ? OR ?) ORDER BY at_h, id", (pid, now, self.eval_mode()))
        thread = self.store.one("SELECT thread_id, opened_at_h FROM threads WHERE proposal_id = ?", (pid,))
        visible_thread = thread and (self.eval_mode() or thread["opened_at_h"] <= now)
        return {
            "proposal_id": pid, "job_id": row["job_id"],
            "status": events[-1]["status"] if events else "draft",
            "bid_amount": row["bid_amount"], "bid_type": row["bid_type"],
            "cover_letter": row["cover_letter"], "screening_answers": json.loads(row["answers_json"]),
            "connects_cost": row["connects_cost"], "created_at": row["created_at"],
            "submitted_at": row["submitted_at"],
            "history": [{"status": e["status"], "at": self.iso(e["at_h"])} for e in events],
            "thread_id": thread["thread_id"] if visible_thread else None,
        }

    def list_proposals(self, fid: str, status: str | None) -> list[dict]:
        rows = self.store.q("SELECT proposal_id FROM proposals WHERE freelancer_id = ? ORDER BY created_at",
                            (fid,))
        views = [self.get_proposal(fid, r["proposal_id"]) for r in rows]
        return [v for v in views if status is None or v["status"] == status]

    # --- threads -------------------------------------------------------------------------

    def _thread_row(self, fid: str, tid: str):
        row = self.store.one("SELECT * FROM threads WHERE thread_id = ? AND freelancer_id = ?", (tid, fid))
        if row is None or not (self.eval_mode() or row["opened_at_h"] <= self.now_h()):
            raise SimError(404, "thread_not_found", f"No thread {tid}")
        return row

    def _messages(self, tid: str, visible_only: bool = True) -> list[dict]:
        rows = self.store.q("SELECT sender, body, at_h FROM messages WHERE thread_id = ? "
                            "AND (at_h <= ? OR ? OR ?) ORDER BY at_h, id",
                            (tid, self.now_h(), self.eval_mode(), not visible_only))
        return [{"sender": r["sender"], "body": r["body"], "at": self.iso(r["at_h"])} for r in rows]

    def list_threads(self, fid: str) -> list[dict]:
        rows = self.store.q("SELECT thread_id FROM threads WHERE freelancer_id = ? ORDER BY opened_at_h", (fid,))
        out = []
        for r in rows:
            try:
                out.append(self.get_thread(fid, r["thread_id"], include_messages=False))
            except SimError:
                continue
        return out

    def get_thread(self, fid: str, tid: str, include_messages: bool = True) -> dict:
        row = self._thread_row(fid, tid)
        status = self.get_proposal(fid, row["proposal_id"])["status"]
        view = {"thread_id": tid, "proposal_id": row["proposal_id"], "job_id": row["job_id"],
                "client_id": row["client_id"], "status": status,
                "accepting_messages": self._accepting(row, status)}
        if include_messages:
            view["messages"] = self._messages(tid)
        return view

    def _accepting(self, row, status: str) -> bool:
        sent = self.store.one("SELECT COUNT(*) AS n FROM messages WHERE thread_id = ? AND sender = 'freelancer'",
                              (row["thread_id"],))["n"]
        return status in ("replied", "interview") and sent < self.cfg["client"]["max_freelancer_messages"]

    def post_message(self, fid: str, tid: str, body: str) -> dict:
        with self.store.lock:
            row = self._thread_row(fid, tid)
            status = self.get_proposal(fid, row["proposal_id"])["status"]
            if not self._accepting(row, status):
                raise SimError(409, "thread_closed", "This conversation is not accepting messages")
            found = pol.violations(self.world.policy, body)
            if found:
                raise SimError(422, "policy_violation", "Message breaks marketplace policy",
                               {"violations": found})
            now = self.now_h()
            self.store.run("INSERT INTO messages(thread_id, sender, body, at_h) VALUES (?, 'freelancer', ?, ?)",
                           (tid, body, now))
            prop = self.store.one("SELECT decision_json FROM proposals WHERE proposal_id = ?",
                                  (row["proposal_id"],))
        job = self.world.jobs[row["job_id"]]
        acc = next(a for a in self.accounts.values() if a["freelancer_id"] == fid)
        reply = self.client.reply(job, self.world.hidden[job["job_id"]], self.world.clients[row["client_id"]],
                                  self.world.personas[acc["persona"]], json.loads(prop["decision_json"]),
                                  self._messages(tid, visible_only=False))
        with self.store.lock:
            n = self.store.one("SELECT COUNT(*) AS n FROM messages WHERE thread_id = ?", (tid,))["n"]
            at = now + self._delay(f"{tid}:{n}", self.cfg["client"]["reply_delay_hours"])
            self.store.run("INSERT INTO messages(thread_id, sender, body, at_h) VALUES (?, 'client', ?, ?)",
                           (tid, reply["message"], at))
            if reply["decision"] in ("interview", "hired", "hire", "lost"):
                status = "hired" if reply["decision"] in ("hire", "hired") else reply["decision"]
                self.store.run("INSERT INTO status_events(proposal_id, status, at_h) VALUES (?, ?, ?)",
                               (row["proposal_id"], status, at))
        return self.get_thread(fid, tid)

    # --- admin ---------------------------------------------------------------------------

    def admin_proposal(self, pid: str) -> dict:
        """Everything about a proposal, including the client's hidden reasoning. Admin only."""
        row = self.store.one("SELECT * FROM proposals WHERE proposal_id = ?", (pid,))
        if row is None:
            raise SimError(404, "proposal_not_found", f"No proposal {pid}")
        return {**dict(row), "decision": json.loads(row["decision_json"] or "null"),
                "hidden_preferences": self.world.hidden[row["job_id"]],
                "events": [dict(e) for e in self.store.q(
                    "SELECT status, at_h FROM status_events WHERE proposal_id = ? ORDER BY at_h, id", (pid,))]}
