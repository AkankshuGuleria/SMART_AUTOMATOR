"""
tasks/store.py — local persistence for tasks, steps and needs (<data_dir>/tasks.db).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT NOT NULL,
    request TEXT NOT NULL,
    agent TEXT,
    status TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    summary TEXT
);
CREATE TABLE IF NOT EXISTS task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    policy TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    output TEXT,
    started_at REAL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_steps_task ON task_steps(task_id, idx);
CREATE TABLE IF NOT EXISTS needs (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    project_id TEXT,
    var TEXT NOT NULL,
    kind TEXT NOT NULL,
    provider TEXT,
    title TEXT NOT NULL,
    steps TEXT NOT NULL,
    docs_url TEXT,
    target_file TEXT,
    status TEXT NOT NULL,
    resolution TEXT,
    created_at REAL NOT NULL,
    resolved_at REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_needs_open ON needs(project_id, var) WHERE status = 'open';
"""

TERMINAL = {"done", "failed", "cancelled"}


class TaskStore:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from config import data_dir

            path = Path(data_dir()) / "tasks.db"
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    # ── tasks ────────────────────────────────────────────────────────────────

    def create_task(self, project_id: str | None, title: str, request: str, agent: str,
                    steps: list[dict[str, str]]) -> str:
        tid = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO tasks(id, project_id, title, request, agent, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'planned', ?, ?)",
                (tid, project_id, title, request, agent, now, now),
            )
            for i, step in enumerate(steps):
                self._conn.execute(
                    "INSERT INTO task_steps(task_id, idx, kind, title, policy, status, detail) "
                    "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                    (tid, i, step["kind"], step["title"], step.get("policy", "auto"), step.get("detail", "")),
                )
        return tid

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._conn.execute(f"UPDATE tasks SET {cols} WHERE id = ?", (*fields.values(), task_id))  # noqa: S608

    def update_step(self, task_id: str, idx: int, **fields: Any) -> None:
        if "output" in fields and not isinstance(fields["output"], str | None):
            fields["output"] = json.dumps(fields["output"], default=str)
        cols = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._conn.execute(  # noqa: S608
                f"UPDATE task_steps SET {cols} WHERE task_id = ? AND idx = ?", (*fields.values(), task_id, idx)
            )
        self.update_task(task_id)

    def _step(self, r: sqlite3.Row) -> dict[str, Any]:
        out = dict(r)
        out["output"] = json.loads(r["output"]) if r["output"] else None
        return out

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            t = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not t:
                return None
            steps = self._conn.execute(
                "SELECT * FROM task_steps WHERE task_id = ? ORDER BY idx", (task_id,)
            ).fetchall()
        task = dict(t)
        task["steps"] = [self._step(s) for s in steps]
        task["needs"] = self.list_needs(task_id=task_id, status=None)
        return task

    def list_tasks(self, project_id: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM tasks", []
        if project_id:
            # Tasks for a new project (started from the work bar) have no project yet:
            # show them alongside the selected project's tasks.
            sql += " WHERE project_id = ? OR project_id IS NULL"
            args.append(project_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        out = []
        for r in rows:
            task = dict(r)
            with self._lock:
                counts = self._conn.execute(
                    "SELECT COUNT(*) AS n, SUM(status IN ('done','skipped')) AS d FROM task_steps WHERE task_id = ?",
                    (r["id"],),
                ).fetchone()
            task["steps_total"], task["steps_done"] = int(counts["n"] or 0), int(counts["d"] or 0)
            out.append(task)
        return out

    def interrupted(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT id FROM tasks WHERE status = 'running'").fetchall()
        return [r["id"] for r in rows]

    # ── needs ────────────────────────────────────────────────────────────────

    def add_need(self, project_id: str | None, task_id: str | None, var: str, info: dict[str, Any],
                 target_file: str | None) -> str | None:
        nid = uuid.uuid4().hex[:12]
        title = f"{info.get('provider') or 'Value'} needed: {var}"
        with self._lock:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO needs(id, task_id, project_id, var, kind, provider, title, steps, "
                "docs_url, target_file, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (nid, task_id, project_id, var, info["kind"], info.get("provider"), title,
                 json.dumps(info.get("steps", [])), info.get("docs_url"), target_file, time.time()),
            )
        return nid if cur.rowcount else None

    def list_needs(self, project_id: str | None = None, task_id: str | None = None,
                   status: str | None = "open") -> list[dict[str, Any]]:
        sql, args = "SELECT * FROM needs WHERE 1=1", []
        if project_id:
            sql += " AND project_id = ?"
            args.append(project_id)
        if task_id:
            sql += " AND task_id = ?"
            args.append(task_id)
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [{**dict(r), "steps": json.loads(r["steps"])} for r in rows]

    def get_need(self, need_id: str) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM needs WHERE id = ?", (need_id,)).fetchone()
        return {**dict(r), "steps": json.loads(r["steps"])} if r else None

    def resolve_need(self, need_id: str, resolution: str, status: str = "resolved") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE needs SET status = ?, resolution = ?, resolved_at = ? WHERE id = ?",
                (status, resolution, time.time(), need_id),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: TaskStore | None = None
_lock = threading.Lock()


def get_task_store() -> TaskStore:
    global _store
    with _lock:
        if _store is None:
            _store = TaskStore()
        return _store


def set_task_store(store: TaskStore | None) -> None:
    global _store
    with _lock:
        _store = store


def active_task_summary(project_id: str) -> dict[str, Any] | None:
    """The most recent unfinished task for a project (used by session snapshots)."""
    for task in get_task_store().list_tasks(project_id, limit=10):
        if task["status"] not in TERMINAL:
            return {"id": task["id"], "title": task["title"], "status": task["status"],
                    "progress": f"{task['steps_done']}/{task['steps_total']}"}
    return None
