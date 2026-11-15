"""Repository rules the assignment says CI must enforce (the GigSim freeze is a CI step of its own):
no secrets in the repo, every prompt lives in agent/prompts/, every README number comes from
evals/results/ (tested in test_results_tables.py)."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_DIRS = ("agent", "rag", "apps/api", "worker", "mcp_servers", "evals")

SECRET_PATTERNS = {
    "groq": r"gsk_[A-Za-z0-9]{20,}",
    "openrouter": r"sk-or-v1-[A-Za-z0-9]{20,}",
    "openai": r"sk-(proj-)?[A-Za-z0-9_-]{32,}",
    "github": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [ROOT / p for p in out.splitlines()]


def test_no_env_file_tracked():
    names = {p.relative_to(ROOT).as_posix() for p in tracked_files()}
    assert ".env" not in names


def test_no_secrets_in_tracked_files():
    hits = []
    for path in tracked_files():
        if not path.is_file() or path.suffix in {".png", ".pdf", ".gif", ".sqlite3", ".npz", ".lock"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{path.relative_to(ROOT)}: {name}" for name, pat in SECRET_PATTERNS.items() if re.search(pat, text)]
    assert not hits, hits


def _python_files():
    for d in CODE_DIRS:
        yield from (ROOT / d).rglob("*.py")


def _is_text_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp):
        return _is_text_literal(node.left) or _is_text_literal(node.right)
    return False


def test_system_prompts_come_from_agent_prompts():
    """A SystemMessage built from a string literal is a prompt living outside agent/prompts/."""
    offenders = []
    for path in _python_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "SystemMessage"
                    and node.args and _is_text_literal(node.args[0])):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, offenders


def test_every_prompt_reference_has_a_file():
    names = set()
    for path in _python_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "prompt"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                names.add(node.args[0].value)
    missing = [n for n in names if not (ROOT / "agent/prompts" / f"{n}.md").exists()]
    assert names and not missing, missing
