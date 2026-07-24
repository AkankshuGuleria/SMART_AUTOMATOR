"""
automation/dev_servers.py — AUTOMATA Automation Layer: dev server management.

Owns:    Starting and stopping development servers for a project
         (backend API, frontend Vite/CRA/Next.js, or any configured server).
Never:   Must not write directly to CockroachDB.
         Must not call Bedrock.
         Process launch failures must be caught and logged — never crash
         the Persistent Memory Engine (see ARCHITECTURE.md §10).
Ref:     ARCHITECTURE.md §3.2c, ROADMAP.md Phase 3.

Phase 0: Stub — all functions log and return immediately.
Phase 3: Implement using subprocess + os_windows.py for process management.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def start_dev_servers(project_id: str, server_configs: list[dict] | None = None) -> dict[str, Any]:
    """
    Start one or more development servers for the given project.

    Args:
        project_id:     UUID of the project being restored.
        server_configs: Optional list of server configs, each with keys:
                        {'name': str, 'command': str, 'cwd': str, 'port': int}
                        If None, reads saved server config from CockroachDB
                        (Phase 3+).

    Returns:
        {'servers': [{'name': str, 'status': 'started'|'error', 'pid': int|None}]}

    Phase 3 implementation:
        - For each config: subprocess.Popen the command in a new terminal/window
          using os_windows.open_terminal_with_command().
        - Track PIDs in memory (not CockroachDB — PIDs are short-lived).
        - Surface status per server in the RestoreWorkspace UI step progress.
    """
    logger.info("start_dev_servers: Phase 0 stub | project_id=%s", project_id)
    return {"servers": [], "status": "skipped"}


def stop_dev_servers(project_id: str) -> dict[str, Any]:
    """
    Stop all tracked dev servers for the given project.

    Phase 3: Terminate tracked PIDs gracefully (SIGTERM → wait → SIGKILL).
    """
    logger.info("stop_dev_servers: Phase 0 stub | project_id=%s", project_id)
    return {"servers": [], "status": "skipped"}
