"""
memory/retrieval.py — AUTOMATA Persistent Memory Engine: vector search retrieval.
Owns: Querying CockroachDB for relevant memories given a natural-language
           question or a structured filter. Returns raw memory rows — does not
           compose an answer (→ ai/bedrock_client.py does that).
Never:   Must not call Bedrock. Must not execute OS actions.
Ref:     ARCHITECTURE.md §5 (retrieval data flow), DATABASE_SCHEMA.md §3.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

_RECENT_TABLES = {
    "commits": {
        "columns": "id, project_id, session_id, commit_hash, message, author, committed_at",
        "timestamp": "committed_at",
        "content": "message",
    },
    "todos": {
        "columns": "id, project_id, description, status, source, created_at, resolved_at",
        "timestamp": "created_at",
        "content": "description",
    },
    "file_edits": {
        "columns": "id, project_id, session_id, file_path, edited_at, change_summary",
        "timestamp": "edited_at",
        "content": "change_summary",
    },
    "terminal_commands": {
        "columns": "id, project_id, session_id, command, cwd, exit_code, run_at",
        "timestamp": "run_at",
        "content": "command",
    },
    "architecture_notes": {
        "columns": "id, project_id, title, content, updated_at",
        "timestamp": "updated_at",
        "content": "content",
    },
    "decision_log": {
        "columns": "id, project_id, decision, rationale, decided_at",
        "timestamp": "decided_at",
        "content": "rationale",
    },
    "mistake_log": {
        "columns": "id, project_id, symptom, root_cause, fix, module, occurred_at",
        "timestamp": "occurred_at",
        "content": "root_cause",
    },
}

_VECTOR_TABLES = {
    "sessions": {
        "embedding": "summary_embedding",
        "timestamp": "started_at",
        "content": "summary",
    },
    "commits": {
        "embedding": "message_embedding",
        "timestamp": "committed_at",
        "content": "message",
    },
    "todos": {
        "embedding": "description_embedding",
        "timestamp": "created_at",
        "content": "description",
    },
    "architecture_notes": {
        "embedding": "content_embedding",
        "timestamp": "updated_at",
        "content": "content",
    },
    "decision_log": {
        "embedding": "rationale_embedding",
        "timestamp": "decided_at",
        "content": "rationale",
    },
    "mistake_log": {
        "embedding": "root_cause_embedding",
        "timestamp": "occurred_at",
        "content": "root_cause",
    },
}


def _format_vector(values: list[float]) -> str:
    """Return a CockroachDB-compatible vector literal."""
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _normalize_row(row: dict[str, Any], table: str, score: float | None = None) -> dict[str, Any]:
    """Shape table-specific rows into the memory structure used by the Reasoning Engine."""
    meta = _RECENT_TABLES.get(table) or _VECTOR_TABLES.get(table)
    content_key = meta["content"] if meta else ""
    timestamp_key = meta["timestamp"] if meta else ""

    content = row.get(content_key)
    if not content and table == "file_edits":
        content = f"Edited {row.get('file_path', 'unknown file')}"
    if not content and table == "decision_log":
        content = row.get("decision")
    if not content and table == "mistake_log":
        content = row.get("symptom")

    memory = {
        "table": table,
        "id": str(row.get("id", "")),
        "content": content or "",
        "timestamp": row.get(timestamp_key),
        "raw": row,
    }
    if score is not None:
        memory["score"] = score
    return memory


def retrieve_recent(project_id: str, table: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Return recent memories from one allow-listed table.

    This is the reliable fallback path when vector search or the embedding
    backend is unavailable. It keeps the API useful in disconnected/local setup
    mode without bypassing project scoping.
    """
    from sqlalchemy import text

    from db.client import get_session

    if not project_id:
        logger.warning("retrieve_recent: project_id is required")
        return []

    if table not in _RECENT_TABLES:
        logger.warning("retrieve_recent: unsupported table '%s'", table)
        return []

    meta = _RECENT_TABLES[table]
    query = (
        f"SELECT {meta['columns']} FROM {table} "  # noqa: S608 — table validated against _RECENT_TABLES allowlist
        f"WHERE project_id = :project_id "
        f"ORDER BY {meta['timestamp']} DESC LIMIT :limit"
    )

    try:
        with get_session() as session:
            if session is None:
                return []
            result = session.execute(
                text(query),
                {"project_id": project_id, "limit": max(1, min(limit, 100))},
            )
            return [
                _normalize_row(dict(row._mapping), table)
                for row in result.fetchall()
            ]
    except Exception as exc:
        logger.error("retrieve_recent: failed for table %s - %s", table, exc)
        return []


def retrieve_by_vector(
    query_text: str,
    tables: list[str],
    project_id: str | None = None,
    top_k: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run a vector similarity search across the specified table(s) and return
    the top-k most relevant memory rows.

    Args:
        query_text:  Natural-language query to embed and search against.
        tables:      List of table names to search (e.g. ['commits', 'todos']).
        project_id:  Scope search to this project. Required unless comparing
                      across projects (explicitly allowed by the caller).
        top_k:       Maximum number of results to return.
        date_from:   Optional ISO-8601 date string for filtering by recency.
        date_to:     Optional ISO-8601 date string for filtering by recency.

    Returns:
        List of dicts — each dict represents one memory row with at minimum:
        {'table': str, 'id': str, 'content': str, 'timestamp': str, 'score': float}
        Returns [] if DB is unavailable or no results found.
    """
    from sqlalchemy import text

    from ai.bedrock_client import invoke_embedding
    from config import settings
    from db.client import get_session

    if not settings.embedding_available:
        logger.debug("retrieve_by_vector: embedding model not configured — returning empty")
        return []

    if not project_id:
        logger.warning("retrieve_by_vector: project_id is required for vector search")
        return []

    # Embed the query text
    query_embedding = invoke_embedding(query_text)
    if query_embedding is None:
        logger.error("retrieve_by_vector: Failed to generate embedding for query")
        return []

    results = []

    # For each table, execute CockroachDB vector search
    for table in tables:
        try:
            with get_session() as session:
                if session is None:
                    continue
                
                if table not in _VECTOR_TABLES:
                    logger.warning(f"retrieve_by_vector: Table {table} has no vector column")
                    continue

                table_meta = _VECTOR_TABLES[table]
                embedding_col = table_meta["embedding"]
                timestamp_col = table_meta["timestamp"]
                
                # Build and execute the vector search query
                # noqa: S608 — table/cols validated against _VECTOR_TABLES allowlist
                query = f"""
                    SELECT *, {embedding_col} <-> :query_vec AS score
                    FROM {table}
                    WHERE project_id = :project_id
                    AND {embedding_col} IS NOT NULL
                    {f" AND {timestamp_col} >= :date_from" if date_from else ""}
                    {f" AND {timestamp_col} <= :date_to" if date_to else ""}
                    ORDER BY score ASC
                    LIMIT :top_k
                """
                
                result = session.execute(
                    text(query),
                    {
                        "project_id": project_id,
                        "query_vec": _format_vector(query_embedding),
                        "date_from": date_from,
                        "date_to": date_to,
                        "top_k": top_k
                    }
                )
                
                # Convert results to list of dicts
                for row in result.fetchall():
                    row_dict = dict(row._mapping)
                    score = float(row_dict.pop("score", 1.0))
                    results.append(_normalize_row(row_dict, table, score))
                    
        except Exception as exc:
            logger.error("retrieve_by_vector: failed for table %s — %s", table, exc)
    
    # Re-rank results by score (lower score = more similar)
    results.sort(key=lambda x: x.get('score', 1.0))
    
    # Return top_k results
    return results[:top_k]
