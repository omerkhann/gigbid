"""Fail (exit 1) when an eval result drops below evals/thresholds.yaml. Used by CI and `make eval`.

  python -m evals.check_thresholds rag      evals/results/ci/rag_eval.json
  python -m evals.check_thresholds decision evals/results/ci/decision_eval.json

Thresholds are floors (or ceilings for keys ending in _max) set a little under the committed
baseline, so noise passes but a real regression fails the PR.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def metrics(kind: str, result: dict) -> dict[str, dict]:
    if kind == "rag":
        return {s["variant"]: s for s in result["summary"]}
    if kind == "decision":
        return {"overall": result["overall"]}
    raise SystemExit(f"unknown kind {kind}")


def check(kind: str, path: Path) -> list[str]:
    rules = yaml.safe_load((ROOT / "evals/thresholds.yaml").read_text(encoding="utf-8"))[kind]
    got = metrics(kind, json.loads(path.read_text(encoding="utf-8")))
    failures = []
    for group, limits in rules.items():
        if group not in got:
            failures.append(f"{kind}/{group}: missing from {path}")
            continue
        for key, limit in limits.items():
            name = key.removesuffix("_max")
            value = got[group].get(name)
            ok = value is not None and (value <= limit if key.endswith("_max") else value >= limit)
            print(f"{'ok  ' if ok else 'FAIL'} {kind}/{group}/{name} = {value} ({'<=' if key.endswith('_max') else '>='} {limit})")
            if not ok:
                failures.append(f"{kind}/{group}/{name}")
    return failures


if __name__ == "__main__":
    bad = check(sys.argv[1], Path(sys.argv[2]))
    sys.exit(f"{len(bad)} threshold(s) failed: {', '.join(bad)}" if bad else 0)
