"""
automation/restore.py — AUTOMATA Automation Layer: workspace restoration.

Owns:    The restore_workspace() interface and its Windows implementation.
          Delegates OS-specific calls to os_windows.py.
Never:   Must not write directly to CockroachDB — reports status back to the
          Persistent Memory Engine (memory/capture.py), which writes.
          Must not call Bedrock.
          Failures must be caught and logged — must never crash the Memory Engine
          or Reasoning Engine (see ARCHITECTURE.md §10).
Ref:     ARCHITECTURE.md §3.2c, PROJECT.md §8 (feature 3), ROADMAP.md Phase 3.

Phase 0: Stub — restore_workspace() returns a status dict with no-op steps.
Phase 3: Implement against os_windows.py OS interface.
"""

import logging
import os
from typing import Any

from automation.dev_servers import start_project_dev_servers
from automation.os_windows import (
    checkout_git_branch,
    launch_editor,
    open_terminal,
)
from db.client import get_project

logger = logging.getLogger(__name__)


def restore_workspace(project_id: str, session_id: str | None = None) -> dict[str, Any]:
    """
    Restore a developer's workspace for the given project.

    Steps (performed in order per PROJECT.md §7 demo flow):
    1. Git branch checkout (restore last known branch).
    2. Terminal session restore.
    3. Dev server start (backend → frontend → any other configured servers).
    4. [Stretch] Editor launch (VS Code / Cursor).
    5. [Stretch] Browser tab restore.

    Returns a status dict with per-step results:
    {
        "project_id": str,
        "steps": [
            {"step": "git_checkout", "status": "ok" | "error" | "skipped", "detail": str},
            ...
        ],
        "overall": "ok" | "partial" | "error"
    }

    The frontend displays per-step progress (see SKILLS.md §3 — RestoreWorkspace UI).
    Callers must treat "partial" as a success — some steps failing (e.g. editor
    unavailable) must not block the developer from continuing work.
    """
    steps: list[dict[str, Any]] = []
    overall = "ok"

    # Step 1: Get project info
    project = get_project(project_id)
    if project is None:
        return {
            "project_id": project_id,
            "steps": [{"step": "git_checkout", "status": "error", "detail": "Project not found"}],
            "overall": "error",
        }

    repo_path = project.get("repo_path", "")
    if not repo_path or not os.path.isdir(repo_path):
        # Without the folder nothing else can be restored; do not open a
        # terminal or editor somewhere unrelated.
        reason = "Skipped: project folder not found"
        return {
            "project_id": project_id,
            "steps": [
                {
                    "step": "git_checkout",
                    "status": "error",
                    "detail": f"Repo path not found: {repo_path or '(empty)'} — re-register the project with its full folder path",
                },
                *(
                    {"step": name, "status": "skipped", "detail": reason}
                    for name in ("terminal", "dev_servers", "editor", "browser")
                ),
            ],
            "overall": "error",
        }
    else:
        # Step 1: Git branch checkout
        try:
            import git

            repo = git.Repo(repo_path)
            current_branch = repo.active_branch.name if repo.active_branch else "main"
            success = checkout_git_branch(repo_path, current_branch)
            steps.append(
                {
                    "step": "git_checkout",
                    "status": "ok" if success else "error",
                    "detail": (
                        f"Checked out branch '{current_branch}'"
                        if success
                        else "Git checkout failed"
                    ),
                }
            )
            if not success:
                overall = "partial"
        except Exception as exc:
            steps.append({"step": "git_checkout", "status": "error", "detail": str(exc)})
            overall = "partial"

    # Step 2: Terminal restore
    try:
        success = open_terminal(repo_path)
        steps.append(
            {
                "step": "terminal",
                "status": "ok" if success else "error",
                "detail": "Terminal opened" if success else "Failed to open terminal",
            }
        )
        if not success:
            overall = "partial"
    except Exception as exc:
        steps.append({"step": "terminal", "status": "error", "detail": str(exc)})
        overall = "partial"

    # Step 3: Dev servers
    try:
        server_results = start_project_dev_servers(repo_path)
        statuses = [r.get("status") for r in server_results]
        if statuses and all(s == "skipped" for s in statuses):
            overall_status = "skipped"
        elif statuses and all(s in {"ok", "skipped"} for s in statuses):
            overall_status = "ok"
        elif any(s == "ok" for s in statuses):
            overall_status = "partial"
        else:
            overall_status = "error"
        detail = "; ".join(
            f"{r.get('server', 'server')}: {r.get('status', '?')}"
            + (f" ({r['detail']})" if r.get("detail") else "")
            for r in server_results
        ) or "No dev servers detected"
        steps.append(
            {
                "step": "dev_servers",
                "status": overall_status,
                "detail": detail,
            }
        )
        if overall_status != "ok":
            overall = "partial"
    except Exception as exc:
        steps.append({"step": "dev_servers", "status": "error", "detail": str(exc)})
        overall = "partial"

    # Step 4: Editor launch (stretch)
    try:
        success = launch_editor(repo_path)
        steps.append(
            {
                "step": "editor",
                "status": "ok" if success else "error",
                "detail": "Editor launched" if success else "Editor not available",
            }
        )
        if not success and overall == "ok":
            overall = "partial"
    except Exception as exc:
        steps.append({"step": "editor", "status": "error", "detail": str(exc)})
        if overall == "ok":
            overall = "partial"

    # Step 5: Browser restore (stretch)
    steps.append(
        {
            "step": "browser",
            "status": "skipped",
            "detail": "Browser tab restore not yet implemented (Phase 3+)",
        }
    )

    return {
        "project_id": project_id,
        "steps": steps,
        "overall": overall,
    }
