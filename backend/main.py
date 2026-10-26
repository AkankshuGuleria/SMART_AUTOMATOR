"""
main.py — AUTOMATA background agent entrypoint.
Owns: Process startup: configure logging, load config, start FastAPI server,
            launch background watcher threads.
Never: Does not contain business logic — delegates to memory/, ai/,
            automation/, decision_engine/, and api/.
Ref:     ARCHITECTURE.md §3.2, CONVENTIONS.md §4.
"""

import logging

import uvicorn

from automation.no_console import install as _hide_child_consoles
from logging_config import configure_logging

# Before anything can start a subprocess: no console windows popping up.
_hide_child_consoles()
configure_logging()

from config import settings  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("AUTOMATA agent starting up")
    logger.info(
        "Status | db_available=%s | bedrock_available=%s | embedding_available=%s",
        settings.db_available,
        settings.bedrock_available,
        settings.embedding_available,
    )

    # Capture threads, memory sync, snapshots, the usage tracker and the system
    # sampler all start inside the API lifespan (api/server.py) so they run the
    # same way under `python main.py` and `uvicorn api.server:app`.
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
