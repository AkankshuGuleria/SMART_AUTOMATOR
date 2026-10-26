"""
workspace/capture_manager.py — capture follows the active project.

Owns:    Starting/stopping the file watcher, git poller and terminal capture
         for whichever project is active, and remembering that choice.
Never:   Runs more than one set of capture threads at a time.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_KEY = "active_project_id"


class CaptureManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self.project_id: str | None = None
        self.project_path: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_path": self.project_path,
            "threads": [t.name for t in self._threads if t.is_alive()],
        }

    def stop(self) -> None:
        with self._lock:
            for t in self._threads:
                stop = getattr(t, "stop", None)
                if callable(stop):
                    stop()
            self._threads = []
            self.project_id = self.project_path = None

    def activate(self, project_id: str) -> dict[str, Any]:
        """Point capture at *project_id* (no-op if it is already active)."""
        from db.client import get_project
        from memory.capture import FileWatcherThread, GitPollerThread, TerminalCaptureThread
        from memory.local_store import get_store

        project = get_project(project_id)
        if not project:
            return {"success": False, "error": "Project not found"}
        path = str(project.get("repo_path") or "")
        if not os.path.isdir(path):
            return {"success": False, "error": f"Project folder not found: {path}"}
        try:
            store = get_store()
            store.set_value(_ACTIVE_KEY, str(project_id))
            store.touch_project(str(project_id))
        except Exception:
            pass
        if self.project_id == str(project_id) and any(t.is_alive() for t in self._threads):
            return {"success": True, "changed": False, **self.status()}
        self.stop()
        with self._lock:
            pid = str(project_id)
            self._threads = [
                FileWatcherThread(project_id=pid, project_path=path, session_id=None, daemon=True),
                GitPollerThread(project_id=pid, project_path=path, session_id=None, daemon=True),
                TerminalCaptureThread(project_id=pid, session_id=None, daemon=True, project_path=path),
            ]
            for t in self._threads:
                t.start()
            self.project_id, self.project_path = pid, path
        logger.info("capture: following %s (%s)", project.get("name"), path)
        return {"success": True, "changed": True, **self.status()}

    def start_default(self) -> dict[str, Any] | None:
        """On startup: the last active project, else the newest one with a real folder."""
        from db.client import get_projects
        from memory.local_store import get_store

        candidates: list[str] = []
        try:
            remembered = get_store().get_value(_ACTIVE_KEY)
            if remembered:
                candidates.append(str(remembered))
        except Exception:
            pass
        projects = get_projects()
        projects.sort(key=lambda p: str(p.get("created_at") or ""), reverse=True)
        candidates += [str(p["id"]) for p in projects if os.path.isdir(str(p.get("repo_path") or ""))]
        for pid in candidates:
            result = self.activate(pid)
            if result.get("success"):
                return result
        logger.info("capture: no registered project with a local folder")
        return None


_manager = CaptureManager()


def get_manager() -> CaptureManager:
    return _manager


def active_project_id() -> str | None:
    if _manager.project_id:
        return _manager.project_id
    try:
        from memory.local_store import get_store

        value = get_store().get_value(_ACTIVE_KEY)
        return str(value) if value else None
    except Exception:
        return None
