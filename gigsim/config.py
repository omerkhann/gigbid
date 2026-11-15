"""Load gigsim/config.yaml and apply environment overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

GIGSIM_DIR = Path(__file__).resolve().parent
REPO_ROOT = GIGSIM_DIR.parent

_ENV = {
    "GIGSIM_PACK": ("pack", str),
    "GIGSIM_POLICY": ("policy", str),
    "GIGSIM_DB": ("db_path", str),
    "GIGSIM_ADMIN": ("admin_enabled", lambda v: v not in ("0", "false", "no")),
    "GIGSIM_ADMIN_TOKEN": ("admin_token", str),
    "GIGSIM_SPEED": ("speed", float),
}


def load_config(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((GIGSIM_DIR / "config.yaml").read_text(encoding="utf-8"))
    for env, (key, cast) in _ENV.items():
        if env in os.environ:
            cfg[key] = cast(os.environ[env])
    if "GIGSIM_CLIENT_MODE" in os.environ:
        cfg["client"]["mode"] = os.environ["GIGSIM_CLIENT_MODE"]
    if "GIGSIM_ACCOUNTS" in os.environ:
        cfg["accounts"] = json.loads(os.environ["GIGSIM_ACCOUNTS"])
    if "GIGSIM_CLIENT_MODEL" in os.environ:
        cfg["client"]["llm"]["model"] = os.environ["GIGSIM_CLIENT_MODEL"]
    for key, value in (overrides or {}).items():
        cfg[key] = value
    return cfg


def pack_dir(pack: str) -> Path:
    """dev and live ship in the repo; test is generated into data/processed and never committed."""
    if pack == "test":
        return REPO_ROOT / "data/processed/scenarios/test"
    return GIGSIM_DIR / "scenarios" / pack


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p
