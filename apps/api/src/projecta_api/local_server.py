"""Loopback Uvicorn entry point controlled through the launcher's private stdin pipe."""

from __future__ import annotations

import asyncio
import os
import sys
import threading

import uvicorn


HOST = "127.0.0.1"
PORT = int(os.environ.get("PROJECTA_API_PORT", "18732"))


def _run() -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            "projecta_api.main:app",
            host=HOST,
            port=PORT,
            log_level="warning",
            access_log=False,
            timeout_graceful_shutdown=30,
        )
    )

    def watch_control_pipe() -> None:
        try:
            command = sys.stdin.readline()
        except OSError:
            command = ""
        if not command or command.strip() == "stop":
            server.should_exit = True

    threading.Thread(target=watch_control_pipe, name="projecta-api-control", daemon=True).start()
    asyncio.run(server.serve())


if __name__ == "__main__":
    _run()
