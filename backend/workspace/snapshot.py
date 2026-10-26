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
    "code.exe": "VS Code", "cursor.exe": "Cursor", "antigravity ide.exe": "Antigravity IDE",
    "antigravity.exe": "Antigravity", "windowsterminal.exe": "Windows Terminal",
    "powershell.exe": "PowerShell", "pwsh.exe": "PowerShell",
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "claude.exe": "Claude",
}
# Editors that open a folder: process exe → (label, launcher name for resolve_executable)
EDITORS = {
    "antigravity ide.exe": ("Antigravity IDE", "antigravity-ide"),
    "code.exe": ("VS Code", "code"),
    "cursor.exe": ("Cursor", "cursor"),
}
EDITOR_BY_LABEL = {label: (exe, cmd) for exe, (label, cmd) in EDITORS.items()}
USAGE_LOOKBACK_S = 30 * 86400


def _workspace_folder(title: str, repo: str) -> str | None:
    """Folder a VS Code-style window shows, if it belongs to *repo*.

    Titles look like "file.tsx - folder - Visual Studio Code" or
    "folder - Antigravity IDE - file". The folder is the repo itself or a
    folder directly inside it (D:\\REACT\\vite-project for project D:\\REACT).
    """
    if not repo or not os.path.isdir(repo):
        return None
    parts = [p.strip().lstrip("●✓◔ ").strip() for p in title.split(" - ") if p.strip()]
    base = Path(repo).name.lower()
    try:
        children = {c.name.lower(): str(c) for c in Path(repo).iterdir() if c.is_dir()}
    except OSError:
        children = {}
    for part in parts:
        low = part.lower()
        if low == base:
            return repo
        if low in children and low not in {"node_modules", ".git", "dist", "build"}:
            return children[low]
    return None


def last_editor(project_id: str, repo: str) -> dict[str, Any] | None:
    """Which editor (and folder) the user last worked in for this project.

    Order: an editor window open now → the app-usage history (newest first) →
    the last one remembered. Returns {app, folder, seen_at, source} or None.
    """
    for w in _editor_windows():
        folder = _workspace_folder(w.title, repo)
        if folder:
            return {"app": EDITORS[w.exe.lower()][0], "folder": folder, "seen_at": time.time(), "source": "open window"}
    try:
        import sqlite3

        from monitoring.app_usage import default_db_path

        path = default_db_path()
        if os.path.exists(path):
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
            try:
                rows = conn.execute(
                    "SELECT exe, title, ended_at FROM usage_segments WHERE ended_at > ? "  # noqa: S608 — only '?' placeholders are interpolated
                    f"AND lower(exe) IN ({','.join('?' * len(EDITORS))}) ORDER BY ended_at DESC LIMIT 500",
                    (time.time() - USAGE_LOOKBACK_S, *EDITORS),
                ).fetchall()
            finally:
                conn.close()
            for exe, title, ended in rows:
                folder = _workspace_folder(title or "", repo)
                if folder:
                    return {"app": EDITORS[exe.lower()][0], "folder": folder, "seen_at": ended, "source": "usage history"}
    except Exception as exc:
        logger.debug("last_editor: usage history unavailable — %s", exc)
    try:
        from memory.local_store import get_store

        saved = get_store().get_value(f"last_editor:{project_id}")
        if saved and saved.get("app") in EDITOR_BY_LABEL and os.path.isdir(saved.get("folder") or ""):
            return {**saved, "source": "remembered"}
    except Exception:
        pass
    return None


def _editor_windows():
    try:
        from automation import win32

        return [w for w in win32.top_level_windows() if w.exe.lower() in EDITORS and w.title]
    except Exception:
        return []


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
    data["editor"] = last_editor(project_id, repo) if has_repo else None
    if data["editor"]:
        store.set_value(f"last_editor:{project_id}",
                        {k: data["editor"][k] for k in ("app", "folder", "seen_at")})
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
        steps.append(_reopen_editor(project_id, repo, data))

    if open_terminal:
        ok = _open_terminal(repo)
        steps.append({"step": "terminal", "status": "ok" if ok else "error", "detail": repo})

    if start_servers and data.get("dev_servers"):
        running = {s["port"] for s in _dev_servers(repo)}
        for server in data["dev_servers"]:
            if server["port"] in running:
                steps.append({"step": "dev_server", "status": "skipped", "detail": f"port {server['port']} already running"})
                continue
            # Never re-run a stored command line: use the run book AUTOMATA derives
            # from the project's manifest ("npm run dev") for that folder.
            cwd = server.get("cwd") or repo
            cmd = _run_book_command(repo, cwd)
            if not cmd:
                steps.append({"step": "dev_server", "status": "skipped",
                              "detail": f"no dev command found for {Path(cwd).name}"})
                continue
            try:
                subprocess.Popen(cmd, cwd=cwd, shell=True,  # noqa: S602  # nosec B602 — run-book command, user-approved
                                 creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                steps.append({"step": "dev_server", "status": "ok", "detail": f"`{cmd}` for port {server['port']}"})
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


def _run_book_command(repo: str, cwd: str) -> str | None:
    """The project's own dev/start command for *cwd* (from the detected run book)."""
    try:
        from intelligence.profile import detect

        profile = detect(repo)
    except Exception:
        return None
    target = os.path.normcase(os.path.realpath(cwd))
    for entry in profile.get("run_book", []):
        folder = os.path.join(repo, entry["path"]) if entry["path"] != "." else repo
        if os.path.normcase(os.path.realpath(folder)) == target:
            return entry["commands"].get("dev") or entry["commands"].get("start")
    return None


def describe_resume(project_id: str, opts: dict[str, Any] | None = None) -> str:
    """What Resume will do, in plain words (shown in the permission prompt)."""
    from memory.local_store import get_store

    opts = opts or {}
    snap = get_store().latest_snapshot(project_id)
    data = (snap or {}).get("data", {})
    repo = data.get("repo_path", "")
    parts = []
    if opts.get("open_editor", True):
        editor = last_editor(project_id, repo) if repo else None
        parts.append(f"open {editor['app']} in {Path(editor['folder']).name}" if editor else "open your editor")
    if opts.get("open_terminal", True):
        parts.append("open a terminal")
    servers = [s["port"] for s in data.get("dev_servers", [])]
    if opts.get("start_servers", True) and servers:
        parts.append("restart dev server" + ("s" if len(servers) > 1 else "") + " on port " + ", ".join(map(str, servers)))
    return "Resume your workspace: " + ", ".join(parts) if parts else "Resume your workspace"


def _reopen_editor(project_id: str, repo: str, data: dict[str, Any]) -> dict[str, Any]:
    """Open the editor the user last used for this project, in the folder they had open."""
    from automation.os_windows import resolve_executable

    # Fresh look first (the user may have switched editors since the snapshot).
    editor = last_editor(project_id, repo) or data.get("editor")
    if not editor:
        installed = [label for exe, (label, cmd) in EDITORS.items() if resolve_executable(cmd)]
        if not installed:
            return {"step": "editor", "status": "error", "detail": "No supported editor found (Antigravity IDE, VS Code, Cursor)."}
        editor = {"app": installed[0], "folder": repo, "source": "default (no editor recorded yet)"}
    label = editor["app"]
    folder = editor.get("folder") if os.path.isdir(editor.get("folder") or "") else repo
    cmd = EDITOR_BY_LABEL.get(label, (None, None))[1]
    exe = resolve_executable(cmd) if cmd else None
    if not exe:
        return {"step": "editor", "status": "error", "detail": f"{label} is not installed any more."}
    files = [f for f in data.get("recent_files", [])[:8]
             if os.path.exists(f) and os.path.normcase(f).startswith(os.path.normcase(folder))]
    try:
        # The real .exe (not a .cmd launcher), so no console window appears.
        subprocess.Popen([exe, folder, *files], cwd=folder, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"step": "editor", "status": "error", "detail": f"Could not start {label}: {exc}"}
    when = editor.get("seen_at")
    seen = f", last used {time.strftime('%d %b %H:%M', time.localtime(when))}" if when else ""
    return {"step": "editor", "status": "ok", "app": label, "folder": folder,
            "detail": f"{label} in {Path(folder).name}{seen} ({editor.get('source')}); {len(files)} recent files"}


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
