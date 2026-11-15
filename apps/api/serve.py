"""Start the API: python -m apps.api.serve [--port 8000] [--host 127.0.0.1]

Why not plain `uvicorn ...`: on Windows uvicorn creates a Proactor event loop before the app is
imported, and psycopg's async mode (the Postgres pool and checkpointer) can't run on it. This
launcher starts the server on a selector event loop from the beginning. On Linux it is the same as
running uvicorn directly.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    server = uvicorn.Server(uvicorn.Config("apps.api.main:create_app", factory=True, host=a.host, port=a.port,
                                           log_level="warning", loop="none"))
    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()


if __name__ == "__main__":
    main()
