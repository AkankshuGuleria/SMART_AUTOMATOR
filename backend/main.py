"""
main.py — AUTOMATA background agent entrypoint.
Owns: Process startup: configure logging, load config, start FastAPI server,
            launch background watcher threads.
Never: Does not contain business logic — delegates to memory/, ai/,
            automation/, decision_engine/, and api/.
Ref:     ARCHITECTURE.md §3.2, CONVENTIONS.md §4.
"""

import logging
import os
import threading

import uvicorn

from logging_config import configure_logging

configure_logging()

from config import settings  # noqa: E402

logger = logging.getLogger(__name__)


def _resolve_capture_project() -> tuple[str, str] | None:
    """Return the newest registered project available on this machine."""
    if not settings.db_available:
        return None

    try:
        from db.client import get_projects

        projects = get_projects()
        projects.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
        for project in projects:
            project_id = str(project.get("id", "")).strip()
            repo_path = str(project.get("repo_path", "")).strip()
            if project_id and repo_path and os.path.isdir(repo_path):
                return project_id, repo_path
    except Exception as exc:
        logger.warning("Unable to resolve a registered project for capture: %s", exc)
    return None


def _start_background_watchers() -> None:
    """
    Launch background daemon threads for the Persistent Memory Engine capture pipeline.

    Daemon threads are used so they do not block process shutdown when the
    uvicorn server receives SIGTERM/SIGINT. Each thread is responsible for one
    capture source and writes through db/client.py — never directly to CockroachDB.

    Phase 0: threads are imported but not started (capture.py was a stub).
    Phase 1: uncomment and wire up real capture threads here.
    """
    from memory.capture import FileWatcherThread, GitPollerThread, TerminalCaptureThread

    threads: list[threading.Thread] = []
    project = _resolve_capture_project()
    if project is None:
        logger.info("Background watcher threads: no local registered project available")
        return

    project_id, project_path = project

    # File watcher — watches project files for changes
    fw = FileWatcherThread(
        project_id=project_id,
        project_path=project_path,
        session_id=None,
        daemon=True,
    )
    threads.append(fw)

    # Git poller — polls for new commits
    gp = GitPollerThread(
        project_id=project_id,
        project_path=project_path,
        session_id=None,
        daemon=True,
    )
    threads.append(gp)

    # Terminal capture — captures PowerShell history
    tc = TerminalCaptureThread(
        project_id=project_id,
        session_id=None,
        daemon=True,
        project_path=project_path,
    )
    threads.append(tc)

    for t in threads:
        t.start()
        logger.info("Started background thread: %s", t.name)

    if not threads:
        logger.info("Background watcher threads: DB not configured — not started")


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
