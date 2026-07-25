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
import subprocess
from typing import Any

from automation.os_windows import open_terminal_with_command

logger = logging.getLogger(__name__)

# Track running dev server processes per project (in-memory only).
# PIDs are short-lived and not persisted to CockroachDB.
_running_servers: dict[str, list[dict]] = {}


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
    if server_configs is None:
        server_configs = _get_default_server_configs(project_id)

    results = []
    for config in server_configs:
        name = config.get("name", "unknown")
        command = config.get("command", "")
        cwd = config.get("cwd", "")
        port = config.get("port")

        if not command:
            results.append({"name": name, "status": "error", "pid": None, "detail": "No command configured"})
            continue

        # Build the command with port if specified
        cmd = command
        if port and "--port" not in command and "-p" not in command:
            cmd = f"{command} --port {port}"

        try:
            pid = open_terminal_with_command(cmd, cwd)
            if pid is not None:
                results.append({"name": name, "status": "started", "pid": pid})
                logger.info("start_dev_servers: started | name=%s pid=%d", name, pid)
            else:
                results.append({"name": name, "status": "error", "pid": None, "detail": "Failed to launch terminal"})
        except Exception as exc:
            results.append({"name": name, "status": "error", "pid": None, "detail": str(exc)})
            logger.error("start_dev_servers: error starting %s — %s", name, exc)

    # Track running servers in memory
    _running_servers[project_id] = [
        {"name": r["name"], "pid": r.get("pid"), "status": r["status"]}
        for r in results
    ]

    return {"servers": results, "status": "ok" if all(r["status"] == "started" for r in results) else "partial"}


def stop_dev_servers(project_id: str) -> dict[str, Any]:
    """
    Stop all tracked dev servers for the given project.

    Phase 3: Terminate tracked PIDs gracefully (SIGTERM → wait → SIGKILL).
    """
    servers = _running_servers.get(project_id, [])
    results = []

    for server in servers:
        pid = server.get("pid")
        name = server.get("name", "unknown")
        if pid is None:
            results.append({"name": name, "status": "skipped", "detail": "No PID tracked"})
            continue

        try:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)
            results.append({"name": name, "status": "ok", "detail": f"Sent SIGTERM to PID {pid}"})
            logger.info("stop_dev_servers: stopped | name=%s pid=%d", name, pid)
        except ProcessLookupError:
            results.append({"name": name, "status": "ok", "detail": "Process already terminated"})
        except PermissionError:
            results.append({"name": name, "status": "error", "detail": "Permission denied — cannot stop process"})
        except Exception as exc:
            results.append({"name": name, "status": "error", "detail": str(exc)})
            logger.error("stop_dev_servers: error stopping %s — %s", name, exc)

    # Clear tracked servers for this project
    _running_servers.pop(project_id, None)

    return {"servers": results, "status": "ok" if all(r["status"] == "ok" for r in results) else "partial"}


def _get_default_server_configs(project_id: str) -> list[dict]:
    """
    Return default dev server configs for a project.
    Phase 3+: Read from CockroachDB or project config file.
    """
    # Default: try common dev server patterns
    return [
        {
            "name": "backend",
            "command": "uv run python main.py",
            "cwd": "",
            "port": 8000,
        },
        {
            "name": "frontend",
            "command": "npm run dev",
            "cwd": "",
            "port": 5173,
        },
    ]
