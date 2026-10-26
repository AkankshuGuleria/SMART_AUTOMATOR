"""
memory/local_store.py — offline-first local memory (SQLite + FTS5 + vectors).

Owns:    The on-device copy of project memory: projects, captured activity,
         chat turns, briefs, decisions, session snapshots. Works with no
         internet and no CockroachDB. Search is BM25 full-text, blended with
         cosine similarity when a local embedding model is available.
Never:   Stores secret values (text passes through redact_secrets first) or
         talks to the network. CockroachDB stays the optional cloud copy,
         reached only through db/client.py.

File: <data_dir>/memory.db  (data_dir() in config.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import struct
import threading
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

KINDS = {
    "commit", "file_edit", "terminal", "todo", "decision", "note", "chat",
    "brief", "task", "architecture", "mistake",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    remote_url TEXT,
    created_at TEXT NOT NULL,
    last_active_at REAL,
    source TEXT NOT NULL DEFAULT 'local'
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    ref TEXT,
    meta TEXT,
    created_at REAL NOT NULL,
    embedding BLOB,
    embedding_model TEXT,
    dedup_key TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_ref ON memories(project_id, kind, ref) WHERE ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_project_time ON memories(project_id, created_at DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, content='memories', content_rowid='id', tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
END;
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    reason TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_project ON snapshots(project_id, created_at DESC);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

_STOP = {
    "the", "and", "for", "what", "did", "was", "were", "how", "why", "who", "when",
    "where", "which", "with", "this", "that", "from", "have", "has", "had", "are",
    "you", "your", "about", "into", "does", "doing", "done", "can", "could", "would",
    "should", "show", "tell", "give", "last", "any", "all",
    # generic question words that match noise rather than the topic
    "recently", "recent", "lately", "today", "yesterday", "now", "please", "just",
    "code", "need", "want", "know", "get", "got", "make", "made", "project",
}

# Which kinds are de-duplicated on write, and over what window. A terminal
# command or TODO is the same fact whenever it recurs; an edit or a planner
# decision is worth one row per day. Commits use their hash (see _dedup_text).
DEDUP_SCOPE = {
    "terminal": "always",
    "todo": "always",
    "architecture": "always",
    "commit": "always",
    "file_edit": "day",
    "decision": "day",
}

# How much each kind counts when answering a question. Terminal lines are
# plentiful and terse, so they need a stronger match to surface.
KIND_WEIGHT = {
    "commit": 1.0, "architecture": 1.0, "note": 1.0, "todo": 0.95, "file_edit": 0.9,
    "mistake": 0.9, "task": 0.85, "brief": 0.8, "decision": 0.7, "chat": 0.6,
    "terminal": 0.5,
}
_TERMINAL_HINT = re.compile(r"\b(command|terminal|shell|ran|run|typed|powershell|cli)\b", re.I)
_COMMIT_PREFIX = re.compile(r"^commit(?:\s+[0-9a-f]{7,40})?\s*:\s*", re.I)
_EDIT_PREFIX = re.compile(r"^(?:edited|file modified:)\s*", re.I)


def _redact(text: str) -> str:
    try:
        from memory.capture import redact_secrets

        return redact_secrets(text)
    except Exception:
        return text


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def query_terms(text: str) -> list[str]:
    """Meaningful, de-duplicated search terms from free text (max 12)."""
    seen: list[str] = []
    for t in re.findall(r"[A-Za-z0-9_]{3,}", text.lower()):
        if t not in _STOP and t not in seen:
            seen.append(t)
    return seen[:12]


def fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR-query of meaningful terms."""
    return " OR ".join(f'"{t}"*' for t in query_terms(text))


def _dedup_text(kind: str, content: str, repo_path: str | None = None) -> str:
    """The part of a memory that decides whether two rows say the same thing.

    Local capture and cloud sync phrase the same event differently
    ("Commit 36c7e051: msg" vs "Commit: msg", "Edited backend\\x.py" vs
    "File modified: D:\\repo\\backend\\x.py"), so those prefixes and the repo
    root are stripped before comparing.
    """
    text = " ".join(content.split()).lower()
    if kind == "commit":
        # Two commits can share a message ("wip"), so the hash decides when known.
        m = re.match(r"^commit\s+([0-9a-f]{7,40})\s*:", text)
        text = f"h:{m.group(1)[:8]}" if m else "m:" + _COMMIT_PREFIX.sub("", text)[:200]
    elif kind == "file_edit":
        text = _EDIT_PREFIX.sub("", text).replace("\\", "/")
        root = (repo_path or "").replace("\\", "/").lower().rstrip("/")
        if root and text.startswith(root + "/"):
            text = text[len(root) + 1:]
    return text


def dedup_key(kind: str, content: str, created_at: float, repo_path: str | None = None) -> str | None:
    scope = DEDUP_SCOPE.get(kind)
    if not scope:
        return None
    digest = hashlib.sha1(_dedup_text(kind, content, repo_path).encode("utf-8"), usedforsecurity=False).hexdigest()[:20]
    if scope == "day":
        digest += ":" + time.strftime("%Y-%m-%d", time.localtime(created_at))
    return digest


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]{2,}", text.lower()))


class LocalStore:
    def __init__(self, path: str | Path | None = None) -> None:
        if path is None:
            from config import data_dir

            path = Path(data_dir()) / "memory.db"
        self.path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            if self.path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._migrate()

    # ── schema upgrades ──────────────────────────────────────────────────────

    def _migrate(self) -> None:
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(memories)")}
        if "dedup_key" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN dedup_key TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_dedup ON memories(project_id, kind, dedup_key)"
        )
        if self._conn.execute("SELECT 1 FROM kv WHERE key = 'migration:dedup_v1'").fetchone():
            return
        removed = self._dedupe_existing()
        self._conn.execute(
            "INSERT OR REPLACE INTO kv(key, value) VALUES ('migration:dedup_v1', ?)",
            (json.dumps({"removed": removed, "at": time.time()}),),
        )
        if removed:
            logger.info("local memory: removed %d duplicate rows", removed)

    def _dedupe_existing(self) -> int:
        """One-time clean-up of duplicates written before writes were de-duplicated.

        Keeps the oldest row of each group (so its id and ref survive), moves
        its timestamp to the newest occurrence, and deletes the rest.
        """
        roots = {r["id"]: r["repo_path"] for r in self._conn.execute("SELECT id, repo_path FROM projects")}
        kinds = list(DEDUP_SCOPE)
        rows = self._conn.execute(
            f"SELECT id, project_id, kind, content, created_at FROM memories "  # noqa: S608 — only '?' placeholders are interpolated
            f"WHERE kind IN ({','.join('?' * len(kinds))}) ORDER BY id",
            kinds,
        ).fetchall()
        keep: dict[tuple, tuple[int, float]] = {}
        drop: list[int] = []
        keys: dict[int, str] = {}
        for r in rows:
            key = dedup_key(r["kind"], r["content"], float(r["created_at"]), roots.get(r["project_id"]))
            group = (r["project_id"], r["kind"], key)
            if group in keep:
                first_id, newest = keep[group]
                keep[group] = (first_id, max(newest, float(r["created_at"])))
                drop.append(int(r["id"]))
            else:
                keep[group] = (int(r["id"]), float(r["created_at"]))
                keys[int(r["id"])] = key
        # Older cloud mirrors stored commits as "Commit: <message>" without the
        # hash; drop those when the same project has the hashed local copy.
        hashed_msgs: set[tuple[str, str]] = set()
        for r in rows:
            if r["kind"] == "commit" and re.match(r"^commit\s+[0-9a-f]{7,40}\s*:", r["content"], re.I):
                hashed_msgs.add((r["project_id"], _COMMIT_PREFIX.sub("", " ".join(r["content"].split()).lower())[:200]))
        by_id = {int(r["id"]): r for r in rows}
        for group, (row_id, _) in list(keep.items()):
            pid, kind, _key = group
            if kind != "commit":
                continue
            text = " ".join(by_id[row_id]["content"].split()).lower()
            if not re.match(r"^commit\s+[0-9a-f]{7,40}\s*:", text):
                if (pid, _COMMIT_PREFIX.sub("", text)[:200]) in hashed_msgs:
                    drop.append(row_id)
                    del keep[group]
        self._conn.execute("BEGIN")
        try:
            for (_, _, key), (row_id, newest) in keep.items():
                self._conn.execute(
                    "UPDATE memories SET dedup_key = ?, created_at = ? WHERE id = ?", (key, newest, row_id)
                )
            for i in range(0, len(drop), 500):
                chunk = drop[i:i + 500]
                self._conn.execute(f"DELETE FROM memories WHERE id IN ({','.join('?' * len(chunk))})", chunk)  # noqa: S608 — only '?' placeholders are interpolated
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        return len(drop)

    def _repo_path(self, project_id: str | None) -> str | None:
        if not project_id:
            return None
        row = self._conn.execute("SELECT repo_path FROM projects WHERE id = ?", (str(project_id),)).fetchone()
        return row["repo_path"] if row else None

    # ── projects ─────────────────────────────────────────────────────────────

    def upsert_project(self, project: dict[str, Any], source: str = "cloud") -> dict[str, Any]:
        pid = str(project.get("id") or uuid.uuid4())
        row = {
            "id": pid,
            "name": str(project.get("name") or Path(str(project.get("repo_path", ""))).name or "project"),
            "repo_path": str(project.get("repo_path") or ""),
            "remote_url": project.get("remote_url") or None,
            "created_at": str(project.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S")),
            "source": source,
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO projects(id, name, repo_path, remote_url, created_at, source) "
                "VALUES (:id, :name, :repo_path, :remote_url, :created_at, :source) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, repo_path=excluded.repo_path, "
                "remote_url=excluded.remote_url",
                row,
            )
        return self.get_project(pid) or row

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, repo_path, remote_url, created_at, last_active_at, source "
                "FROM projects ORDER BY COALESCE(last_active_at, 0) DESC, created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, repo_path, remote_url, created_at, last_active_at, source "
                "FROM projects WHERE id = ?",
                (str(project_id),),
            ).fetchone()
        return dict(row) if row else None

    def touch_project(self, project_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE projects SET last_active_at = ? WHERE id = ?", (time.time(), str(project_id))
            )

    # ── memories ─────────────────────────────────────────────────────────────

    def record(
        self,
        project_id: str | None,
        kind: str,
        content: str,
        ref: str | None = None,
        meta: dict[str, Any] | None = None,
        created_at: float | None = None,
        embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> int | None:
        """Insert a memory. Returns its id, or None when it is already stored.

        Idempotent two ways: by *ref* (same source row), and by content for the
        kinds in DEDUP_SCOPE (same fact captured again, or the same event
        arriving from both local capture and cloud sync). A repeat only moves
        the stored row's timestamp forward.
        """
        content = _redact((content or "").strip())
        if not content:
            return None
        if kind not in KINDS:
            raise ValueError(f"unknown memory kind: {kind}")
        when = created_at or time.time()
        pid = str(project_id) if project_id else None
        with self._lock:
            key = dedup_key(kind, content, when, self._repo_path(pid))
            if key:
                existing = self._conn.execute(
                    "SELECT id FROM memories WHERE project_id IS ? AND kind = ? AND dedup_key = ? LIMIT 1",
                    (pid, kind, key),
                ).fetchone()
                if existing:
                    self._conn.execute(
                        "UPDATE memories SET created_at = MAX(created_at, ?) WHERE id = ?",
                        (when, existing["id"]),
                    )
                    return None
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO memories(project_id, kind, content, ref, meta, created_at, "
                "embedding, embedding_model, dedup_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    kind,
                    content[:4000],
                    ref,
                    json.dumps(meta, default=str) if meta else None,
                    when,
                    _pack(embedding) if embedding else None,
                    embedding_model if embedding else None,
                    key,
                ),
            )
            return int(cur.lastrowid) if cur.rowcount else None

    def set_embedding(self, memory_id: int, embedding: list[float], model: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE memories SET embedding = ?, embedding_model = ? WHERE id = ?",
                (_pack(embedding), model, memory_id),
            )

    def missing_embeddings(self, limit: int = 64) -> list[tuple[int, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, content FROM memories WHERE embedding IS NULL ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(int(r["id"]), r["content"]) for r in rows]

    def _row(self, r: sqlite3.Row, score: float | None = None) -> dict[str, Any]:
        out = {
            "id": int(r["id"]),
            "project_id": r["project_id"],
            "kind": r["kind"],
            "table": r["kind"],
            "content": r["content"],
            "ref": r["ref"],
            "meta": json.loads(r["meta"]) if r["meta"] else {},
            "created_at": r["created_at"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(r["created_at"])),
        }
        if score is not None:
            out["score"] = round(score, 4)
        return out

    def recent(
        self, project_id: str | None, kinds: list[str] | None = None, limit: int = 20,
        since: float | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memories WHERE 1=1"
        args: list[Any] = []
        if project_id:
            sql += " AND project_id = ?"
            args.append(str(project_id))
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            args.extend(kinds)
        if since:
            sql += " AND created_at >= ?"
            args.append(since)
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [self._row(r) for r in rows]

    def search(
        self,
        query: str,
        project_id: str | None = None,
        kinds: list[str] | None = None,
        limit: int = 8,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search: keyword match blended with cosine when vectors exist.

        Keyword score = how many of the question's terms a row covers (so a row
        matching "desktop" and "automation" beats one matching only "change"),
        then BM25 relative to the best hit, a per-kind weight, and a small
        recency bonus. Results are de-duplicated by content.
        """
        terms = query_terms(query)
        match = fts_query(query)
        scored: dict[int, tuple[float, sqlite3.Row]] = {}
        filters, args = "", []
        if project_id:
            filters += " AND m.project_id = ?"
            args.append(str(project_id))
        if kinds:
            filters += f" AND m.kind IN ({','.join('?' * len(kinds))})"
            args.extend(kinds)
        weights = dict(KIND_WEIGHT)
        if _TERMINAL_HINT.search(query):
            weights["terminal"] = 1.0
        now = time.time()
        with self._lock:
            if match:
                rows = self._conn.execute(
                    "SELECT m.*, bm25(memories_fts) AS rank FROM memories_fts "  # noqa: S608 — filters contain only '?' placeholders
                    "JOIN memories m ON m.id = memories_fts.rowid "
                    f"WHERE memories_fts MATCH ? {filters} ORDER BY rank LIMIT ?",
                    [match, *args, max(200, limit * 25)],
                ).fetchall()
                best = min((float(r["rank"]) for r in rows), default=-1.0) or -1.0
                for r in rows:
                    words = _tokens(r["content"])
                    covered = sum(1 for t in terms if any(w.startswith(t) for w in words))
                    coverage = covered / len(terms) if terms else 0.0
                    bm25 = float(r["rank"]) / best  # 1.0 for the best hit, toward 0 for weak ones
                    age_days = max(0.0, (now - float(r["created_at"])) / 86400)
                    recency = math.exp(-age_days / 14)
                    kw = (0.65 * coverage + 0.35 * bm25) * weights.get(r["kind"], 0.8)
                    if len(r["content"].strip()) < 12 or r["content"].lstrip().startswith("#"):
                        kw *= 0.5  # bare fragments and shell comments say little
                    scored[int(r["id"])] = (kw * (0.85 + 0.15 * recency), r)
            if query_embedding:
                rows = self._conn.execute(
                    f"SELECT m.* FROM memories m WHERE m.embedding IS NOT NULL {filters} "  # noqa: S608 — filters contain only '?' placeholders
                    "ORDER BY m.created_at DESC LIMIT 2000",
                    args,
                ).fetchall()
                for r in rows:
                    sim = _cosine(query_embedding, _unpack(r["embedding"]))
                    if sim < 0.3:
                        continue
                    prev = scored.get(int(r["id"]), (0.0, r))[0]
                    scored[int(r["id"])] = (0.45 * prev + 0.55 * sim if prev else 0.55 * sim, r)
            roots = {}
            out: list[dict[str, Any]] = []
            seen: set[tuple[str, str]] = set()
            for s, r in sorted(scored.values(), key=lambda x: x[0], reverse=True):
                pid = r["project_id"]
                if pid not in roots:
                    roots[pid] = self._repo_path(pid)
                sig = (r["kind"], _dedup_text(r["kind"], r["content"], roots[pid]))
                if sig in seen:
                    continue
                seen.add(sig)
                out.append(self._row(r, s))
                if len(out) >= limit:
                    break
        return out

    def counts(self, project_id: str | None = None) -> dict[str, int]:
        sql = "SELECT kind, COUNT(*) AS n FROM memories"
        args: list[Any] = []
        if project_id:
            sql += " WHERE project_id = ?"
            args.append(str(project_id))
        sql += " GROUP BY kind"
        with self._lock:
            return {r["kind"]: int(r["n"]) for r in self._conn.execute(sql, args).fetchall()}

    # ── snapshots ────────────────────────────────────────────────────────────

    def save_snapshot(self, project_id: str, data: dict[str, Any], reason: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO snapshots(project_id, created_at, reason, data) VALUES (?, ?, ?, ?)",
                (str(project_id), time.time(), reason, json.dumps(data, default=str)),
            )
            # keep the last 50 per project
            self._conn.execute(
                "DELETE FROM snapshots WHERE project_id = ? AND id NOT IN ("
                "SELECT id FROM snapshots WHERE project_id = ? ORDER BY created_at DESC LIMIT 50)",
                (str(project_id), str(project_id)),
            )
            return int(cur.lastrowid)

    def latest_snapshot(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM snapshots WHERE project_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (str(project_id),),
            ).fetchone()
        if not r:
            return None
        return {
            "id": int(r["id"]),
            "project_id": r["project_id"],
            "created_at": r["created_at"],
            "reason": r["reason"],
            "data": json.loads(r["data"]),
        }

    # ── key/value ────────────────────────────────────────────────────────────

    def get_value(self, key: str, default: Any = None) -> Any:
        with self._lock:
            r = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(r["value"]) if r else default

    def set_value(self, key: str, value: Any) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO kv(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value, default=str)),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


_store: LocalStore | None = None
_store_lock = threading.Lock()


def get_store() -> LocalStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = LocalStore()
        return _store


def set_store(store: LocalStore | None) -> None:
    """Swap the process-wide store (tests use an in-memory one)."""
    global _store
    with _store_lock:
        _store = store


def remember(project_id: str | None, kind: str, content: str, **kwargs: Any) -> int | None:
    """Best-effort write used by capture/chat paths; never raises."""
    try:
        return get_store().record(project_id, kind, content, **kwargs)
    except Exception as exc:
        logger.debug("local_store.remember failed — %s", exc)
        return None
