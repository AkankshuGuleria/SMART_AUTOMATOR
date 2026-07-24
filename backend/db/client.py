"""
db/client.py — AUTOMATA CockroachDB connection client.

Owns:    The single SQLAlchemy engine and session factory for the entire backend.
         All CockroachDB reads and writes go through this module.
Never:   Does not contain query logic — that belongs in feature modules
         (memory/capture.py, memory/retrieval.py, etc.) which call get_session().
         Does not store secret values — connection string is read from config.py.
Ref:     ARCHITECTURE.md §3.3, DATABASE_SCHEMA.md, TECH_STACK.md "Database".

Usage:
    from db.client import get_session

    with get_session() as session:
        session.execute(text("SELECT 1"))
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import OperationalError

from config import settings

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
        # CockroachDB uses the PostgreSQL wire protocol.
        # pool_pre_ping=True validates the connection before each use,
        # handling transient network failures cleanly.
        _engine = create_engine(
            settings.cockroachdb_connection_string,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"application_name": "automata-agent"},
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
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
    """
    Return DB connectivity status.

    Used by the /health API endpoint to surface DB state in the UI.
    """
    if _engine is None:
        return {"db": "disconnected", "reason": "COCKROACHDB_CONNECTION_STRING not set"}

    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "connected"}
    except OperationalError as exc:
        logger.warning("db/client: health check failed — %s", exc)
        return {"db": "error", "reason": str(exc)}
