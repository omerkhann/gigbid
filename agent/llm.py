"""Model factory: node name -> chat model, from agent/config.yaml. No model names in code.

`structured(node, Schema)` returns a callable that sends messages, validates the answer against
the Pydantic schema, falls back along the tier's chain on failure, and reports token usage.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

import yaml
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

CONFIG_PATH = Path(__file__).with_name("config.yaml")
T = TypeVar("T", bound=BaseModel)


@lru_cache(maxsize=1)
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def profile() -> str:
    return os.environ.get("MODEL_PROFILE", config()["models"]["profile"])


def chain_for(node: str) -> list[str]:
    m = config()["models"]
    tier = m["nodes"][node]
    return list(m["profiles"][profile()][tier])


def _base_url(provider: dict) -> str:
    base = os.environ.get(provider.get("base_url_env", ""), provider["base_url_default"]).rstrip("/")
    return base + provider.get("path", "")


@lru_cache(maxsize=32)
def chat_model(spec: str) -> ChatOpenAI:
    provider_name, model = spec.split(":", 1)
    provider = config()["providers"][provider_name]
    key = provider.get("api_key") or os.environ.get(provider.get("api_key_env", ""), "")
    opts = dict(config()["models"].get("options", {}).get(spec, {}))
    b = config()["budgets"]
    return ChatOpenAI(model=model, base_url=_base_url(provider), api_key=key or "missing",
                      timeout=b["llm_timeout_s"], max_retries=b["llm_retries"], **opts)


@dataclass
class Usage:
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    fallbacks: int


def structured(node: str, schema: type[T]):
    """Callable(messages) -> (parsed, Usage). Tries each model in the node's chain."""

    def call(messages: list[Any]) -> tuple[T, Usage]:
        errors = []
        for i, spec in enumerate(chain_for(node)):
            llm = chat_model(spec).with_structured_output(schema, method="json_schema", include_raw=True)
            t = time.time()
            try:
                out = llm.invoke(messages)
            except Exception as exc:  # noqa: BLE001 - try the next model in the chain
                errors.append(f"{spec}: {exc.__class__.__name__}: {str(exc)[:200]}")
                continue
            if out.get("parsed") is None:
                errors.append(f"{spec}: unparseable output ({out.get('parsing_error')})")
                continue
            meta = getattr(out["raw"], "usage_metadata", None) or {}
            return out["parsed"], Usage(spec, meta.get("input_tokens", 0), meta.get("output_tokens", 0),
                                        round(time.time() - t, 3), i)
        raise RuntimeError(f"All models failed for {node}: " + " | ".join(errors))

    return call


def prompt(name: str) -> str:
    """Versioned prompt text from agent/prompts/<name>.md (front matter stripped)."""
    text = (Path(__file__).with_name("prompts") / f"{name}.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()
