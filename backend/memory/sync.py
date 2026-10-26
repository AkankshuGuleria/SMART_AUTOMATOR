"""
memory/sync.py — keep the local memory store filled.

Owns:    (1) Mirroring recent CockroachDB activity into the local store so
         memory survives going offline, and (2) filling in vectors for local
         memories whenever an on-device embedding model is available.
Never:   Blocks the API. Runs in one daemon thread; every step is best-effort.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

CLOUD_SYNC_INTERVAL_S = 15 * 60
EMBED_INTERVAL_S = 60
EMBED_BATCH = 32


def _ts(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def backfill_from_cloud(limit: int = 200) -> dict[str, int]:
    """Copy recent cloud rows into the local store (idempotent via ref='db:<table>:<id>')."""
    from db import client as db
    from memory.local_store import get_store

    if db.health_check().get("db") != "connected":
        return {}
    store = get_store()
    counts: dict[str, int] = {}

    def add(project_id: str, kind: str, table: str, row: dict, content: str, when_key: str) -> None:
        if not content or row.get("id") is None:
            return
        new_id = store.record(
            project_id,
            kind,
            content,
            ref=f"db:{table}:{row['id']}",
            created_at=_ts(row.get(when_key)),
        )
        if new_id:
            counts[kind] = counts.get(kind, 0) + 1

    for project in db.get_projects():  # also mirrors the project rows
        if project.get("source") == "local":
            continue
        pid = str(project["id"])
        for row in db.get_commits(pid, limit=limit):
            # Same wording as local capture so the two copies de-duplicate.
            sha = str(row.get("commit_hash") or "")
            msg = str(row.get("message", "")).strip()[:500]
            add(pid, "commit", "commits", row, f"Commit {sha[:8]}: {msg}" if sha else f"Commit: {msg}", "committed_at")
        for row in db.get_file_edits(pid, limit=limit):
            summary = row.get("change_summary") or f"Edited {row.get('file_path', '')}"
            add(pid, "file_edit", "file_edits", row, summary, "edited_at")
        for row in db.get_terminal_commands(pid, limit=limit):
            add(pid, "terminal", "terminal_commands", row, row.get("command", ""), "run_at")
        for row in db.get_todos(pid):
            add(pid, "todo", "todos", row, f"TODO ({row.get('status')}): {row.get('description', '')}", "created_at")
        for row in db.get_decisions(pid, limit=100):
            add(pid, "decision", "decision_log", row,
                f"Decision: {row.get('decision', '')} — {row.get('rationale', '')}", "decided_at")
        for row in db.get_architecture_notes(pid):
            add(pid, "architecture", "architecture_notes", row,
                f"{row.get('title', '')}: {row.get('content', '')}", "updated_at")
    if counts:
        logger.info("memory sync: mirrored from cloud %s", counts)
    return counts


def embed_missing(batch: int = EMBED_BATCH) -> int:
    """Embed local memories that have no vector yet, if a local model is available."""
    from ai.bedrock_client import invoke_local_embedding
    from memory.local_store import get_store

    store = get_store()
    pending = store.missing_embeddings(batch)
    if not pending:
        return 0
    result = invoke_local_embedding([text for _, text in pending])
    if not result:
        return 0
    vectors, model = result
    for (memory_id, _), vec in zip(pending, vectors, strict=False):
        if vec:
            store.set_embedding(memory_id, vec, model)
    return len(pending)


class MemorySyncThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(name="memory-sync", daemon=True)
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        last_cloud = 0.0
        while not self._stop_event.is_set():
            now = time.monotonic()
            if now - last_cloud >= CLOUD_SYNC_INTERVAL_S or last_cloud == 0.0:
                try:
                    backfill_from_cloud()
                except Exception as exc:
                    logger.warning("memory sync: cloud backfill failed — %s", exc)
                last_cloud = now
            try:
                embed_missing()
            except Exception as exc:
                logger.debug("memory sync: embedding skipped — %s", exc)
            self._stop_event.wait(EMBED_INTERVAL_S)


_thread: MemorySyncThread | None = None


def start_sync() -> MemorySyncThread:
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = MemorySyncThread()
        _thread.start()
    return _thread


def stop_sync() -> None:
    global _thread
    if _thread is not None:
        _thread.stop()
        _thread = None
