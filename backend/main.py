"""
main.py — AUTOMATA background agent entrypoint.

Owns:    Process startup: configure logging, load config, start FastAPI server,
         launch background watcher threads.
Never:   Does not contain business logic — delegates to memory/, ai/,
         automation/, decision_engine/, and api/.
Ref:     ARCHITECTURE.md §3.2, CONVENTIONS.md §4.

Run with:
    uv run python main.py
    # or, for hot-reload during development:
    uv run uvicorn api.server:app --reload --host 127.0.0.1 --port 8000
"""

import logging
import sys

# Configure logging FIRST — before any other local imports so that
# all module-level loggers inherit the correct handler and level.
from logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

import threading

import uvicorn

from config import settings


def _start_background_watchers() -> None:
    """
    Launch background daemon threads for the Persistent Memory Engine capture pipeline.

    Daemon threads are used so they do not block process shutdown when the
    uvicorn server receives SIGTERM/SIGINT. Each thread is responsible for one
    capture source and writes through db/client.py — never directly to CockroachDB.

    Phase 0: threads are imported but not started (capture.py is a stub).
    Phase 1: uncomment and wire up real capture threads here.
    """
    # Placeholder — capture threads are started here in Phase 1.
    # from memory.capture import FileWatcherThread, GitPollerThread, TerminalCaptureThread
    # threads = [
    #     FileWatcherThread(daemon=True),
    #     GitPollerThread(daemon=True),
    #     TerminalCaptureThread(daemon=True),
    # ]
    # for t in threads:
    #     t.start()
    #     logger.info("Started background thread: %s", t.name)
    logger.info("Background watcher threads: Phase 0 stub — not yet started")


def main() -> None:
    logger.info("AUTOMATA agent starting up")
    logger.info(
        "Status | db_available=%s | bedrock_available=%s | embedding_available=%s",
        settings.db_available,
        settings.bedrock_available,
        settings.embedding_available,
    )

    _start_background_watchers()

    logger.info("Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_config=None,  # Suppress uvicorn's default logging — we use our own
        access_log=True,
    )


if __name__ == "__main__":
    main()
