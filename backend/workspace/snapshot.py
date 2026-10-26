"""
workspace/snapshot.py — "where I left off": capture and resume working state.

Owns:    Building a snapshot of the active project's working state (branch,
         changed files, recently edited files, open dev windows, running dev
         servers, open TODOs, last chat, current task) and resuming from it.
Never:   Stores file contents. Resume only opens things; it never edits files.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_S = 10 * 60
DEV_APPS = {
    "code.exe": "VS Code", "cursor.exe": "Cursor", "antigravity.exe": "Antigravity",
    "windowsterminal.exe": "Windows Terminal", "powershell.exe": "PowerShell", "pwsh.exe": "PowerShell",
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "claude.exe": "Claude",
}
EDITOR_COMMANDS = {"VS Code": "code", "Cursor": "cursor", "Antigravity": "antigravity-ide"}


def _git(repo: str, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _dev_servers(repo: str) -> list[dict[str, Any]]:
    """Listening TCP ports owned by processes whose working folder is inside the repo."""
    try:
        import psutil
    except ImportError:
        return []
    repo_real = os.path.normcase(os.path.realpath(repo))
    found: dict[int, dict[str, Any]] = {}
    try:
        conns = psutil.net_connections(kind="tcp")
    except Exception:
        return []
    for c in conns:
        if c.status != psutil.CONN_LISTEN or not c.pid or not c.laddr:
            continue
        try:
            proc = psutil.Process(c.pid)
            cwd = os.path.normcase(os.path.realpath(proc.cwd()))
        except Exception:
            continue
        if cwd == repo_real or cwd.startswith(repo_real + os.sep):
            found[c.laddr.port] = {
                "port": c.laddr.port,
                "process": proc.name(),
                "cwd": proc.cwd(),
                "command": " ".join(proc.cmdline()[:6]),
            }
    return sorted(found.values(), key=lambda s: s["port"])


def _open_windows(project_name: str, repo: str) -> list[dict[str, str]]:
    try:
        from automation import win32
    except Exception:
        return []
    folder = Path(repo).name.lower()
    out = []
    for w in win32.top_level_windows():
        app = DEV_APPS.get(w.exe.lower())
        if not app:
            continue
        title = w.title
        related = folder in title.lower() or project_name.lower() in title.lower()
        out.append({"app": app, "title": title[:160], "related": related})
    return out


def take_snapshot(project_id: str, reason: str = "manual") -> dict[str, Any]:
    from db.client import get_project
    from memory.local_store import get_store

    project = get_project(project_id)
    if not project:
        return {"success": False, "error": "Project not found"}
    repo = str(project.get("repo_path") or "")
    store = get_store()
    recent_files: list[str] = []
    for m in store.recent(project_id, ["file_edit"], limit=60):
        path = (m.get("meta") or {}).get("file_path")
        if path and path not in recent_files and os.path.exists(path):
            recent_files.append(path)
        if len(recent_files) >= 10:
            break
    todos = [m["content"] for m in store.recent(project_id, ["todo"], limit=10) if "(done)" not in m["content"]]
    last_chat = store.recent(project_id, ["chat"], limit=1)
    has_repo = os.path.isdir(repo)
    data = {
        "project_id": project_id,
        "project_name": project.get("name"),
        "repo_path": repo,
        "branch": _git(repo, "branch", "--show-current") if has_repo else "",
        "changed_files": [ln[3:] for ln in _git(repo, "status", "--short").splitlines() if ln.strip()][:30]
        if has_repo else [],
        "last_commit": _git(repo, "log", "-1", "--pretty=%h %s") if has_repo else "",
        "recent_files": recent_files,
        "open_windows": _open_windows(str(project.get("name") or ""), repo) if has_repo else [],
        "dev_servers": _dev_servers(repo) if has_repo else [],
        "open_todos": todos[:5],
        "last_chat": last_chat[0]["content"][:400] if last_chat else None,
    }
    try:
        from tasks.store import active_task_summary

        data["current_task"] = active_task_summary(project_id)
    except Exception:
        data["current_task"] = None
    snap_id = store.save_snapshot(project_id, data, reason)
    return {"success": True, "id": snap_id, "reason": reason, "created_at": time.time(), "data": data}


def resume(project_id: str, open_editor: bool = True, open_terminal: bool = True,
           start_servers: bool = True) -> dict[str, Any]:
    """Reopen the workspace from the latest snapshot; every step reports what really happened."""
    from automation.os_windows import open_terminal as _open_terminal
    from memory.local_store import get_store

    snap = get_store().latest_snapshot(project_id)
    if not snap:
        return {"success": False, "error": "No snapshot yet for this project.", "steps": []}
    data = snap["data"]
    repo = data.get("repo_path", "")
    steps: list[dict[str, Any]] = []
    if not os.path.isdir(repo):
        return {"success": False, "error": f"Project folder not found: {repo}", "steps": steps}

    if open_editor:
        editor = next(
            (w["app"] for w in data.get("open_windows", []) if w["app"] in EDITOR_COMMANDS and w["related"]),
            "VS Code",
        )
        cmd = EDITOR_COMMANDS[editor]
        files = [f for f in data.get("recent_files", [])[:8] if os.path.exists(f)]
        try:
            import shutil

            exe = shutil.which(cmd) or (cmd if editor != "Antigravity" else None)
            if not exe:
                from automation.agent_bridge import _detect

                exe = _detect("antigravity").app_path
            if exe:
                subprocess.Popen([exe, "-r", repo, *files], shell=False)
                steps.append({"step": "editor", "status": "ok", "detail": f"{editor}: {len(files)} recent files"})
            else:
                steps.append({"step": "editor", "status": "error", "detail": f"{editor} command not found"})
        except Exception as exc:
            steps.append({"step": "editor", "status": "error", "detail": str(exc)})

    if open_terminal:
        ok = _open_terminal(repo)
        steps.append({"step": "terminal", "status": "ok" if ok else "error", "detail": repo})

    if start_servers and data.get("dev_servers"):
        running = {s["port"] for s in _dev_servers(repo)}
        for server in data["dev_servers"]:
            if server["port"] in running:
                steps.append({"step": "dev_server", "status": "skipped", "detail": f"port {server['port']} already running"})
                continue
            try:
                subprocess.Popen(server["command"], cwd=server.get("cwd") or repo, shell=True,
                                 creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                steps.append({"step": "dev_server", "status": "ok", "detail": f"restarted on port {server['port']}"})
            except Exception as exc:
                steps.append({"step": "dev_server", "status": "error", "detail": str(exc)})

    failed = [s for s in steps if s["status"] == "error"]
    return {
        "success": not failed,
        "partial": bool(failed) and len(failed) < len(steps),
        "snapshot": {"created_at": snap["created_at"], "reason": snap["reason"]},
        "summary": {
            "branch": data.get("branch"),
            "last_commit": data.get("last_commit"),
            "changed_files": len(data.get("changed_files", [])),
            "open_todos": data.get("open_todos", []),
            "current_task": data.get("current_task"),
        },
        "steps": steps,
    }


class SnapshotThread(threading.Thread):
    """Snapshots the active project every 10 minutes and when the user goes idle."""

    def __init__(self) -> None:
        super().__init__(name="snapshot", daemon=True)
        self._stop_event = threading.Event()
        self._was_idle = False

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        from workspace.capture_manager import active_project_id

        last = time.monotonic()
        while not self._stop_event.wait(15):
            pid = active_project_id()
            if not pid:
                continue
            idle = False
            try:
                from monitoring.app_usage import tracker_status

                idle = bool(tracker_status().get("idle"))
            except Exception:
                pass
            reason = None
            if idle and not self._was_idle:
                reason = "idle"
            elif time.monotonic() - last >= SNAPSHOT_INTERVAL_S:
                reason = "periodic"
            self._was_idle = idle
            if reason:
                try:
                    take_snapshot(pid, reason)
                except Exception as exc:
                    logger.debug("snapshot failed — %s", exc)
                last = time.monotonic()


_thread: SnapshotThread | None = None


def start_snapshots() -> None:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = SnapshotThread()
        _thread.start()


def stop_snapshots(final: bool = True) -> None:
    global _thread
    if _thread is not None:
        _thread.stop()
        _thread = None
    if final:
        from workspace.capture_manager import active_project_id

        pid = active_project_id()
        if pid:
            try:
                take_snapshot(pid, "shutdown")
            except Exception as exc:
                logger.debug("final snapshot failed — %s", exc)
