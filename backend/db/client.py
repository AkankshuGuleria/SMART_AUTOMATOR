"""
db/client.py — AUTOMATA CockroachDB connection client.

Owns:    The single SQLAlchemy engine and session factory for the entire backend.
          All CockroachDB reads and writes go through this module.
Never:   Does not contain query logic — that belongs in feature modules
          (memory/capture.py, memory/retrieval.py, etc.) which call get_session().
          Does not store secret values — connection string is read from config.py.
Ref:     ARCHITECTURE.md §3.3, DATABASE_SCHEMA.md, TECH_STACK.md "Database".

Usage:
    from db.client import get_session, insert_project, get_projects

    with get_session() as session:
        if session is None:
            return  # DB not available
        projects = get_projects(session)
"""

import logging
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from config import settings

# CockroachDB version string compatibility fix for SQLAlchemy postgresql dialect
PGDialect._get_server_version_info = lambda self, conn: (13, 0, 0)

logger = logging.getLogger(__name__)

# Module-level engine — created once at import time if DB is configured.
# If COCKROACHDB_CONNECTION_STRING is empty, engine is None and all operations
# degrade gracefully (log a warning, return None/empty).
_engine = None
_SessionLocal = None


def _init_engine() -> None:
    """
    Initialize the SQLAlchemy engine.

    Called once at module import. Silently skips if no connection string is
    configured — the rest of the module detects _engine is None and degrades.
    """
    global _engine, _SessionLocal

    if not settings.db_available:
        logger.warning(
            "db/client: DB engine NOT initialized — "
            "COCKROACHDB_CONNECTION_STRING is not set. "
            "All database operations will be no-ops until the connection is configured."
        )
        return

    try:
        _engine = create_engine(
            settings.cockroachdb_connection_string,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"application_name": "automata-agent"},
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False)
        logger.info("db/client: CockroachDB engine initialized successfully")
    except Exception as exc:  # pragma: no cover
        logger.error("db/client: Failed to create DB engine — %s", exc)
        _engine = None
        _SessionLocal = None


_init_engine()


@contextmanager
def get_session() -> Generator[Session | None, None, None]:
    """
    Yield a SQLAlchemy Session, or None if the DB is not configured.

    Callers must handle None:

        with get_session() as session:
            if session is None:
                return  # DB not available
            session.execute(text("SELECT 1"))

    Commits on success, rolls back on exception, always closes.
    """
    if _SessionLocal is None:
        logger.debug("db/client: get_session() called but DB is not configured — yielding None")
        yield None
        return

    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def health_check() -> dict:
    """Return DB connectivity status."""
    if _engine is None:
        return {"db": "disconnected", "reason": "COCKROACHDB_CONNECTION_STRING not set"}

    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "connected"}
    except OperationalError as exc:
        logger.warning("db/client: health check failed — %s", exc)
        return {"db": "error", "reason": str(exc)}


# ─── Projects CRUD ───────────────────────────────────────────────────────────


def insert_project(name: str, repo_path: str, remote_url: str | None = None) -> str | None:
    """Insert a project in CockroachDB and the local store; local-only when offline.

    Returns the project id. When the cloud DB is unreachable the project is
    created locally (source='local') so the workspace keeps working offline.
    """
    from sqlalchemy import text

    from db.client import get_session
    from memory.local_store import get_store

    with get_session() as session:
        if session is not None:
            try:
                result = session.execute(
                    text(
                        "INSERT INTO projects (name, repo_path, remote_url) "
                        "VALUES (:name, :repo_path, :remote_url) "
                        "RETURNING id"
                    ),
                    {"name": name, "repo_path": repo_path, "remote_url": remote_url},
                )
                row = result.fetchone()
                if row:
                    pid = str(row[0])
                    get_store().upsert_project(
                        {"id": pid, "name": name, "repo_path": repo_path, "remote_url": remote_url},
                        source="cloud",
                    )
                    return pid
            except Exception as exc:
                logger.error("db/client: insert_project failed — %s", exc)
    try:
        project = get_store().upsert_project(
            {"name": name, "repo_path": repo_path, "remote_url": remote_url}, source="local"
        )
        logger.info("db/client: project stored locally (cloud DB unavailable) | %s", project["id"])
        return str(project["id"])
    except Exception as exc:
        logger.error("db/client: local insert_project failed — %s", exc)
        return None


def get_projects() -> list[dict]:
    """All projects: cloud rows (mirrored locally) plus local-only projects.

    Falls back to the local store when CockroachDB is unreachable.
    """
    from sqlalchemy import text

    from db.client import get_session
    from memory.local_store import get_store

    cloud: list[dict] | None = None
    with get_session() as session:
        if session is not None:
            try:
                result = session.execute(
                    text(
                        "SELECT id, name, repo_path, remote_url, created_at "
                        "FROM projects ORDER BY created_at DESC"
                    )
                )
                cloud = [dict(row._mapping) for row in result.fetchall()]
            except Exception as exc:
                logger.error("db/client: get_projects failed — %s", exc)
    try:
        store = get_store()
        if cloud is None:
            return store.list_projects()
        for project in cloud:
            store.upsert_project(project, source="cloud")
        cloud_ids = {str(p["id"]) for p in cloud}
        local_only = [p for p in store.list_projects() if p["source"] == "local" and p["id"] not in cloud_ids]
        return cloud + local_only
    except Exception as exc:
        logger.warning("db/client: local project store unavailable — %s", exc)
        return cloud or []


def get_project(project_id: str) -> dict | None:
    """Return a single project by id (cloud first, then the local store)."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is not None:
            try:
                result = session.execute(
                    text(
                        "SELECT id, name, repo_path, remote_url, created_at "
                        "FROM projects WHERE id = :id"
                    ),
                    {"id": project_id},
                )
                row = result.fetchone()
                if row:
                    return dict(row._mapping)
            except Exception as exc:
                logger.error("db/client: get_project failed — %s", exc)
    try:
        from memory.local_store import get_store

        return get_store().get_project(str(project_id))
    except Exception:
        return None


# ─── Sessions CRUD ───────────────────────────────────────────────────────────


def insert_session(project_id: str) -> str | None:
    """Start a new session for a project. Returns the session UUID or None."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text("INSERT INTO sessions (project_id) VALUES (:project_id) RETURNING id"),
                {"project_id": project_id},
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_session failed — %s", exc)
            return None


def end_session(
    project_id: str,
    session_id: str,
    summary: str | None = None,
    summary_embedding: str | None = None,
) -> bool:
    """End a session by setting ended_at and optionally a summary.

    After a successful update, fires the Decision Engine on_session_end trigger
    so any autonomous follow-up actions (brief regeneration, next-task suggestion,
    etc.) are queued automatically.
    """
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "UPDATE sessions SET ended_at = now(), summary = :summary, summary_embedding = :summary_embedding "
                    "WHERE id = :session_id AND ended_at IS NULL"
                ),
                {
                    "session_id": session_id,
                    "summary": summary,
                    "summary_embedding": summary_embedding,
                },
            )
        except Exception as exc:
            logger.error("db/client: end_session failed — %s", exc)
            return False

    from decision_engine.triggers import on_session_end

    try:
        on_session_end(project_id, session_id)
    except Exception as exc:
        logger.warning("db/client: on_session_end trigger failed — %s", exc)

    return True


def get_active_session(project_id: str) -> dict | None:
    """Return the currently active (not ended) session for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, started_at, ended_at, summary "
                    "FROM sessions WHERE project_id = :project_id AND ended_at IS NULL"
                ),
                {"project_id": project_id},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
        except Exception as exc:
            logger.error("db/client: get_active_session failed — %s", exc)
            return None


# ─── Commits CRUD ────────────────────────────────────────────────────────────


def insert_commit(
    project_id: str,
    session_id: str | None,
    commit_hash: str,
    message: str,
    author: str,
    committed_at: str,
    message_embedding: str | None = None,
) -> bool:
    """Insert a commit. Returns True on success, False on duplicate or failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "INSERT INTO commits "
                    "(project_id, session_id, commit_hash, message, author, committed_at, message_embedding) "
                    "VALUES (:project_id, :session_id, :commit_hash, "
                    ":message, :author, :committed_at, :message_embedding)"
                ),
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "commit_hash": commit_hash,
                    "message": message[:500],
                    "author": author,
                    "committed_at": committed_at,
                    "message_embedding": message_embedding,
                },
            )
            return True
        except Exception as exc:
            logger.error("db/client: insert_commit failed — %s", exc)
            return False


def get_commits(project_id: str, limit: int = 20) -> list[dict]:
    """Return recent commits for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, session_id, commit_hash, message, author, committed_at "
                    "FROM commits WHERE project_id = :project_id "
                    "ORDER BY committed_at DESC LIMIT :limit"
                ),
                {"project_id": project_id, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_commits failed — %s", exc)
            return []


# ─── File Edits CRUD ─────────────────────────────────────────────────────────


def insert_file_edit(
    project_id: str,
    session_id: str | None,
    file_path: str,
    change_summary: str | None = None,
) -> bool:
    """Insert a file edit record."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "INSERT INTO file_edits (project_id, session_id, file_path, change_summary) "
                    "VALUES (:project_id, :session_id, :file_path, :change_summary)"
                ),
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "file_path": file_path,
                    "change_summary": change_summary,
                },
            )
            return True
        except Exception as exc:
            session.rollback()
            logger.error("db/client: insert_file_edit failed — %s", exc)
            return False


def get_file_edits(project_id: str, limit: int = 20) -> list[dict]:
    """Return recent file edits for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, session_id, file_path, edited_at, change_summary "
                    "FROM file_edits WHERE project_id = :project_id "
                    "ORDER BY edited_at DESC LIMIT :limit"
                ),
                {"project_id": project_id, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_file_edits failed — %s", exc)
            return []


# ─── Terminal Commands CRUD ──────────────────────────────────────────────────


def insert_terminal_command(
    project_id: str,
    session_id: str | None,
    command: str,
    cwd: str,
    exit_code: int | None = None,
    command_embedding: str | None = None,
) -> bool:
    """Insert a terminal command record."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "INSERT INTO terminal_commands "
                    "(project_id, session_id, command, cwd, exit_code, command_embedding) "
                    "VALUES (:project_id, :session_id, :command, :cwd, :exit_code, :command_embedding)"
                ),
                {
                    "project_id": project_id,
                    "session_id": session_id,
                    "command": command,
                    "cwd": cwd,
                    "exit_code": exit_code,
                    "command_embedding": command_embedding,
                },
            )
            return True
        except Exception as exc:
            logger.error("db/client: insert_terminal_command failed — %s", exc)
            return False


def get_terminal_commands(project_id: str, limit: int = 20) -> list[dict]:
    """Return recent terminal commands for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, session_id, command, cwd, exit_code, run_at "
                    "FROM terminal_commands WHERE project_id = :project_id "
                    "ORDER BY run_at DESC LIMIT :limit"
                ),
                {"project_id": project_id, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_terminal_commands failed — %s", exc)
            return []


# ─── TODOs CRUD ──────────────────────────────────────────────────────────────


def insert_todo(
    project_id: str,
    description: str,
    source: str = "manual",
    status: str = "pending",
    description_embedding: str | None = None,
) -> str | None:
    """Insert a TODO. Returns the TODO UUID or None on failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO todos (project_id, description, source, status, description_embedding) "
                    "VALUES (:project_id, :description, :source, :status, :description_embedding) "
                    "RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "description": description,
                    "source": source,
                    "status": status,
                    "description_embedding": description_embedding,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_todo failed — %s", exc)
            return None


def get_todos(project_id: str, status: str | None = None) -> list[dict]:
    """Return TODOs for a project, optionally filtered by status."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            if status:
                result = session.execute(
                    text(
                        "SELECT id, project_id, description, status, source, "
                        "created_at, resolved_at "
                        "FROM todos WHERE project_id = :project_id AND status = :status "
                        "ORDER BY created_at DESC"
                    ),
                    {"project_id": project_id, "status": status},
                )
            else:
                result = session.execute(
                    text(
                        "SELECT id, project_id, description, status, source, "
                        "created_at, resolved_at "
                        "FROM todos WHERE project_id = :project_id "
                        "ORDER BY created_at DESC"
                    ),
                    {"project_id": project_id},
                )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_todos failed — %s", exc)
            return []


def update_todo_status(todo_id: str, status: str) -> bool:
    """Update a TODO's status. Sets resolved_at only when resolved/done."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            if status in ("done", "resolved"):
                session.execute(
                    text(
                        "UPDATE todos SET status = :status, resolved_at = now() "
                        "WHERE id = :todo_id AND status != :status"
                    ),
                    {"todo_id": todo_id, "status": status},
                )
            else:
                session.execute(
                    text(
                        "UPDATE todos SET status = :status "
                        "WHERE id = :todo_id AND status != :status"
                    ),
                    {"todo_id": todo_id, "status": status},
                )
            return True
        except Exception as exc:
            logger.error("db/client: update_todo_status failed — %s", exc)
            return False


def update_todo_description(todo_id: str, description: str) -> bool:
    """Update a TODO's description."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text("UPDATE todos SET description = :description WHERE id = :todo_id"),
                {"todo_id": todo_id, "description": description},
            )
            return True
        except Exception as exc:
            logger.error("db/client: update_todo_description failed — %s", exc)
            return False


# ─── Architecture Notes CRUD ─────────────────────────────────────────────────


def insert_architecture_note(
    project_id: str,
    title: str,
    content: str,
    content_embedding: str | None = None,
) -> str | None:
    """Insert an architecture note. Returns the note UUID or None on failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO architecture_notes (project_id, title, content, content_embedding) "
                    "VALUES (:project_id, :title, :content, :content_embedding) "
                    "RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "title": title,
                    "content": content,
                    "content_embedding": content_embedding,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_architecture_note failed — %s", exc)
            return None


def get_architecture_notes(project_id: str) -> list[dict]:
    """Return architecture notes for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, title, content, updated_at "
                    "FROM architecture_notes WHERE project_id = :project_id "
                    "ORDER BY updated_at DESC"
                ),
                {"project_id": project_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_architecture_notes failed — %s", exc)
            return []


# ─── Daily Briefs CRUD ───────────────────────────────────────────────────────


def upsert_daily_brief(
    project_id: str,
    brief_date: str,
    commits_count: int = 0,
    highlights: list[str] | None = None,
    pending_items: list[str] | None = None,
    last_edited_file: str | None = None,
) -> bool:
    """Insert or update a daily brief for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "INSERT INTO daily_briefs "
                    "(project_id, brief_date, commits_count, highlights, "
                    "pending_items, last_edited_file) "
                    "VALUES (:project_id, :brief_date, :commits_count, "
                    ":highlights, :pending_items, :last_edited_file) "
                    "ON CONFLICT (project_id, brief_date) DO UPDATE SET "
                    "commits_count = EXCLUDED.commits_count, "
                    "highlights = EXCLUDED.highlights, "
                    "pending_items = EXCLUDED.pending_items, "
                    "last_edited_file = EXCLUDED.last_edited_file, "
                    "generated_at = now()"
                ),
                {
                    "project_id": project_id,
                    "brief_date": brief_date,
                    "commits_count": commits_count,
                    "highlights": highlights,
                    "pending_items": pending_items,
                    "last_edited_file": last_edited_file,
                },
            )
            return True
        except Exception as exc:
            logger.error("db/client: upsert_daily_brief failed — %s", exc)
            return False


def get_daily_brief(project_id: str, brief_date: str | None = None) -> dict | None:
    """Get the daily brief for a project (defaults to today)."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            if brief_date is None:
                result = session.execute(
                    text(
                        "SELECT * FROM daily_briefs "
                        "WHERE project_id = :project_id "
                        "ORDER BY brief_date DESC LIMIT 1"
                    ),
                    {"project_id": project_id},
                )
            else:
                result = session.execute(
                    text(
                        "SELECT * FROM daily_briefs "
                        "WHERE project_id = :project_id AND brief_date = :brief_date"
                    ),
                    {"project_id": project_id, "brief_date": brief_date},
                )
            row = result.fetchone()
            return dict(row._mapping) if row else None
        except Exception as exc:
            logger.error("db/client: get_daily_brief failed — %s", exc)
            return None


# ─── Taste Preferences CRUD ──────────────────────────────────────────────────


def insert_taste_preference(
    developer_id: str,
    category: str,
    description: str,
    confidence: float = 0.5,
    evidence_count: int = 1,
) -> str | None:
    """Insert a taste preference. Returns the preference UUID or None on failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO taste_preferences "
                    "(developer_id, category, description, confidence, evidence_count) "
                    "VALUES (:developer_id, :category, :description, :confidence, :evidence_count) "
                    "RETURNING id"
                ),
                {
                    "developer_id": developer_id,
                    "category": category,
                    "description": description,
                    "confidence": confidence,
                    "evidence_count": evidence_count,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_taste_preference failed — %s", exc)
            return None


def get_taste_preferences(developer_id: str) -> list[dict]:
    """Return taste preferences for a developer."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, developer_id, category, description, confidence, "
                    "evidence_count, last_observed_at "
                    "FROM taste_preferences WHERE developer_id = :developer_id "
                    "ORDER BY last_observed_at DESC"
                ),
                {"developer_id": developer_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_taste_preferences failed — %s", exc)
            return []


# ─── Credential Refs CRUD ────────────────────────────────────────────────────


def insert_credential_ref(
    project_id: str | None,
    ref_name: str,
    purpose: str,
    expires_at: str | None = None,
) -> str | None:
    """Insert a credential reference (never the actual secret value)."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO credential_refs (project_id, ref_name, purpose, expires_at) "
                    "VALUES (:project_id, :ref_name, :purpose, :expires_at) "
                    "RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "ref_name": ref_name,
                    "purpose": purpose,
                    "expires_at": expires_at,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_credential_ref failed — %s", exc)
            return None


def get_credential_refs(project_id: str | None = None) -> list[dict]:
    """Return credential references, optionally scoped to a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            if project_id:
                result = session.execute(
                    text(
                        "SELECT id, project_id, ref_name, purpose, expires_at, last_used_at "
                        "FROM credential_refs WHERE project_id = :project_id "
                        "ORDER BY last_used_at DESC"
                    ),
                    {"project_id": project_id},
                )
            else:
                result = session.execute(
                    text(
                        "SELECT id, project_id, ref_name, purpose, expires_at, last_used_at "
                        "FROM credential_refs ORDER BY last_used_at DESC"
                    ),
                )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_credential_refs failed — %s", exc)
            return []


# ─── Decision Log CRUD ───────────────────────────────────────────────────────


def insert_decision(
    project_id: str | None,
    decision: str,
    rationale: str,
    rationale_embedding: str | None = None,
) -> str | None:
    """Insert a decision log entry. Returns the decision UUID or None on failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO decision_log (project_id, decision, rationale, rationale_embedding) "
                    "VALUES (:project_id, :decision, :rationale, :rationale_embedding) "
                    "RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "decision": decision,
                    "rationale": rationale,
                    "rationale_embedding": rationale_embedding,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_decision failed — %s", exc)
            return None


def get_decisions(project_id: str | None = None, limit: int = 20) -> list[dict]:
    """Return decision log entries."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            if project_id:
                result = session.execute(
                    text(
                        "SELECT id, project_id, decision, rationale, decided_at "
                        "FROM decision_log WHERE project_id = :project_id "
                        "ORDER BY decided_at DESC LIMIT :limit"
                    ),
                    {"project_id": project_id, "limit": limit},
                )
            else:
                result = session.execute(
                    text(
                        "SELECT id, project_id, decision, rationale, decided_at "
                        "FROM decision_log ORDER BY decided_at DESC LIMIT :limit"
                    ),
                    {"limit": limit},
                )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_decisions failed — %s", exc)
            return []


# ─── Mistake Log CRUD ────────────────────────────────────────────────────────


def insert_mistake(
    project_id: str,
    symptom: str,
    root_cause: str,
    fix: str,
    module: str | None = None,
    root_cause_embedding: str | None = None,
) -> str | None:
    """Insert a mistake log entry. Returns the mistake UUID or None on failure."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "INSERT INTO mistake_log "
                    "(project_id, symptom, root_cause, fix, module, root_cause_embedding) "
                    "VALUES (:project_id, :symptom, :root_cause, :fix, :module, :root_cause_embedding) "
                    "RETURNING id"
                ),
                {
                    "project_id": project_id,
                    "symptom": symptom,
                    "root_cause": root_cause,
                    "fix": fix,
                    "module": module,
                    "root_cause_embedding": root_cause_embedding,
                },
            )
            row = result.fetchone()
            return str(row[0]) if row else None
        except Exception as exc:
            logger.error("db/client: insert_mistake failed — %s", exc)
            return None


def get_mistakes(project_id: str) -> list[dict]:
    """Return mistake log entries for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, symptom, root_cause, fix, module, occurred_at "
                    "FROM mistake_log WHERE project_id = :project_id "
                    "ORDER BY occurred_at DESC"
                ),
                {"project_id": project_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_mistakes failed — %s", exc)
            return []


# ─── Workflow engine CRUD ──────────────────────────


def insert_workflow_run(
    workflow_id: str,
    workflow_version: int,
    inputs_json: str,
    project_id: str,
    initiated_by: str = "user",
) -> str | None:
    """Insert a new workflow run and return its ID."""
    from sqlalchemy import text

    run_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    with get_session() as session:
        if session is None:
            return None
        try:
            session.execute(
                text(
                    "INSERT INTO workflow_runs "
                    "(id, workflow_id, workflow_version, status, inputs_json, "
                    "started_at, initiated_by, project_id) "
                    "VALUES "
                    "(:id, :workflow_id, :workflow_version, 'running', :inputs_json, "
                    ":started_at, :initiated_by, :project_id)"
                ),
                {
                    "id": run_id,
                    "workflow_id": workflow_id,
                    "workflow_version": workflow_version,
                    "inputs_json": inputs_json,
                    "started_at": now,
                    "initiated_by": initiated_by,
                    "project_id": project_id,
                },
            )
            session.commit()
            return run_id
        except Exception as exc:
            logger.error("db/client: insert_workflow_run failed — %s", exc)
            return None


def update_workflow_run_status(run_id: str, status: str, completed_at: str | None = None) -> bool:
    """Update the status of a workflow run."""
    from sqlalchemy import text

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "UPDATE workflow_runs SET status = :status, "
                    "completed_at = :completed_at WHERE id = :id"
                ),
                {
                    "status": status,
                    "completed_at": completed_at,
                    "id": run_id,
                },
            )
            session.commit()
            return True
        except Exception as exc:
            logger.error("db/client: update_workflow_run_status failed — %s", exc)
            return False


def insert_workflow_step(
    run_id: str,
    step_def_id: str,
    tool: str,
    policy: str,
    status: str = "running",
    rendered_inputs_json: str | None = None,
    output_json: str | None = None,
    redactions_json: str | None = None,
) -> str | None:
    """Insert a new workflow step and return its ID."""
    from sqlalchemy import text

    step_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    with get_session() as session:
        if session is None:
            return None
        try:
            session.execute(
                text(
                    "INSERT INTO workflow_steps "
                    "(id, run_id, step_def_id, tool, policy, status, "
                    "rendered_inputs_json, output_json, redactions_json, started_at) "
                    "VALUES "
                    "(:id, :run_id, :step_def_id, :tool, :policy, :status, "
                    ":rendered_inputs_json, :output_json, :redactions_json, :started_at)"
                ),
                {
                    "id": step_id,
                    "run_id": run_id,
                    "step_def_id": step_def_id,
                    "tool": tool,
                    "policy": policy,
                    "status": status,
                    "rendered_inputs_json": rendered_inputs_json,
                    "output_json": output_json,
                    "redactions_json": redactions_json,
                    "started_at": now,
                },
            )
            session.commit()
            return step_id
        except Exception as exc:
            logger.error("db/client: insert_workflow_step failed — %s", exc)
            return None


def update_workflow_step(
    step_id: str,
    status: str,
    output_json: str | None = None,
    completed_at: str | None = None,
    approved_by: str | None = None,
    approved_at: str | None = None,
) -> bool:
    """Update a workflow step's status and output."""
    from sqlalchemy import text

    with get_session() as session:
        if session is None:
            return False
        try:
            session.execute(
                text(
                    "UPDATE workflow_steps SET status = :status, "
                    "output_json = :output_json, completed_at = :completed_at, "
                    "approved_by = :approved_by, approved_at = :approved_at "
                    "WHERE id = :id"
                ),
                {
                    "status": status,
                    "output_json": output_json,
                    "completed_at": completed_at,
                    "approved_by": approved_by,
                    "approved_at": approved_at,
                    "id": step_id,
                },
            )
            session.commit()
            return True
        except Exception as exc:
            logger.error("db/client: update_workflow_step failed — %s", exc)
            return False


def get_workflow_run(run_id: str) -> dict | None:
    """Return a single workflow run by ID."""
    from sqlalchemy import text

    with get_session() as session:
        if session is None:
            return None
        try:
            result = session.execute(
                text(
                    "SELECT id, workflow_id, workflow_version, status, inputs_json, "
                    "started_at, completed_at, initiated_by, project_id "
                    "FROM workflow_runs WHERE id = :id"
                ),
                {"id": run_id},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
        except Exception as exc:
            logger.error("db/client: get_workflow_run failed — %s", exc)
            return None


def get_workflow_runs(project_id: str, status: str | None = None) -> list[dict]:
    """Return workflow runs for a project."""
    from sqlalchemy import text

    with get_session() as session:
        if session is None:
            return []
        try:
            query = (
                "SELECT id, workflow_id, workflow_version, status, inputs_json, "
                "started_at, completed_at, initiated_by, project_id "
                "FROM workflow_runs WHERE project_id = :project_id"
            )
            params: dict[str, Any] = {"project_id": project_id}

            if status:
                query += " AND status = :status"
                params["status"] = status

            query += " ORDER BY started_at DESC"

            result = session.execute(text(query), params)
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_workflow_runs failed — %s", exc)
            return []


def get_workflow_steps(run_id: str) -> list[dict]:
    """Return workflow steps for a run."""
    from sqlalchemy import text

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, run_id, step_def_id, tool, policy, status, "
                    "rendered_inputs_json, output_json, redactions_json, "
                    "started_at, completed_at, approved_by, approved_at "
                    "FROM workflow_steps WHERE run_id = :run_id "
                    "ORDER BY started_at"
                ),
                {"run_id": run_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_workflow_steps failed — %s", exc)
            return []


# ─── Analytics Helpers ──────────────────────────────────────────────────


def get_sessions(project_id: str) -> list[dict]:
    """Return all sessions for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT id, project_id, started_at, ended_at, summary "
                    "FROM sessions WHERE project_id = :project_id "
                    "ORDER BY started_at DESC"
                ),
                {"project_id": project_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_sessions failed — %s", exc)
            return []


def get_commits_over_time(project_id: str, days: int = 7) -> list[dict]:
    """Return commit counts per day for the last N days."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT CAST(committed_at AS DATE) AS day, "  # noqa: S608 — days is int(); project_id is a bound parameter
                    "COUNT(*) AS count "
                    f"FROM commits WHERE project_id = :project_id "
                    f"AND committed_at >= now() - INTERVAL '{int(days)} days' "
                    f"GROUP BY CAST(committed_at AS DATE) "
                    f"ORDER BY day DESC"
                ),
                {"project_id": project_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_commits_over_time failed — %s", exc)
            return []


def get_file_edits_over_time(project_id: str, days: int = 7) -> list[dict]:
    """Return file edit counts per day for the last N days."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT CAST(edited_at AS DATE) AS day, "  # noqa: S608 — days is int(); project_id is a bound parameter
                    "COUNT(*) AS count "
                    f"FROM file_edits WHERE project_id = :project_id "
                    f"AND edited_at >= now() - INTERVAL '{int(days)} days' "
                    f"GROUP BY CAST(edited_at AS DATE) "
                    f"ORDER BY day DESC"
                ),
                {"project_id": project_id},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_file_edits_over_time failed — %s", exc)
            return []


def get_top_files(project_id: str, limit: int = 10) -> list[dict]:
    """Return the most edited files for a project."""
    from sqlalchemy import text

    from db.client import get_session

    with get_session() as session:
        if session is None:
            return []
        try:
            result = session.execute(
                text(
                    "SELECT file_path, COUNT(*) AS edit_count "
                    "FROM file_edits WHERE project_id = :project_id "
                    "GROUP BY file_path "
                    "ORDER BY edit_count DESC "
                    "LIMIT :limit"
                ),
                {"project_id": project_id, "limit": limit},
            )
            return [dict(row._mapping) for row in result.fetchall()]
        except Exception as exc:
            logger.error("db/client: get_top_files failed — %s", exc)
            return []
