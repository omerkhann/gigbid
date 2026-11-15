"""Schema snapshot (assignment A7): fail CI when a tool's signature changes unintentionally.

If a change is intended, regenerate and commit the snapshot:
    UPDATE_SNAPSHOTS=1 uv run pytest tests/contract
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from mcp_servers.marketplace.server import Settings, build_server

SNAPSHOTS = Path(__file__).parent / "snapshots"


async def _surface(server) -> dict:
    tools = await server.list_tools()
    return {t.name: {"title": t.title, "description": t.description, "annotations": t.annotations.model_dump(),
                     "input": t.inputSchema, "output": t.outputSchema} for t in sorted(tools, key=lambda t: t.name)}


async def test_marketplace_tool_schemas_match_snapshot(tmp_path):
    current = await _surface(build_server(Settings(db_path=tmp_path / "m.sqlite3"), backend=object()))
    path = SNAPSHOTS / "marketplace_tools.json"
    if os.environ.get("UPDATE_SNAPSHOTS") or not path.exists():
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    saved = json.loads(path.read_text(encoding="utf-8"))
    changed = sorted(n for n in set(saved) | set(current) if saved.get(n) != current.get(n))
    assert not changed, f"Tool schemas changed: {changed}. If intended: UPDATE_SNAPSHOTS=1 pytest tests/contract"
