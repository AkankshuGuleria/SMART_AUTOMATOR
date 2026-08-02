"""
memory/embeddings.py — AUTOMATA Persistent Memory Engine: embedding generation.

Owns:    Generating vector embeddings for semantically rich content
         (commit messages, TODOs, architecture notes, session summaries,
         README text) before writing them to CockroachDB vector columns.
Never:   Must not write to CockroachDB directly (→ db/client.py).
         Must not call Bedrock for reasoning (→ ai/bedrock_client.py).
         Embedding is a data-preparation step, not a reasoning step.
Ref:     ARCHITECTURE.md §3.2a (Memory Lifecycle), DATABASE_SCHEMA.md §3.

Phase 0: Uses Ollama (free, local) for embedding generation.
         Falls back to None if Ollama is not running.
Phase 2: Wire to Bedrock embedding model when API keys are available.
         The embedding model ID and dimension must match the VECTOR(n)
         column size in schema.sql — see DATABASE_SCHEMA.md §5 open question.
"""

import logging

logger = logging.getLogger(__name__)


def _pad_to_db_dimension(vector: list[float] | None) -> list[float] | None:
    """Pad or truncate an embedding vector to match the DB column dimension.

    Ollama's nomic-embed-text produces 768-dim vectors, but the DB columns
    were provisioned with VECTOR(1024) (via EMBEDDING_DIMENSION=1024 in .env
    for Bedrock's amazon.titan-embed-text-v2:0).  This function bridges the
    gap by zero-padding the vector so it matches the configured dimension.

    If EMBEDDING_DIMENSION is 0 or unset, the vector is returned unmodified.
    """
    if vector is None:
        return None

    from config import settings
    target_dim = settings.embedding_dimension
    if target_dim <= 0 or len(vector) == target_dim:
        return vector

    if len(vector) > target_dim:
        # Truncate (Bedrock model with higher dim than DB)
        return vector[:target_dim]

    # Pad with zeros (Ollama nomic-embed-text: 768 → Bedrock: 1024)
    padded = vector + [0.0] * (target_dim - len(vector))
    logger.debug(
        "Padded embedding from %d to %d dimensions (model dim mismatch)",
        len(vector),
        target_dim,
    )
    return padded


def generate_embedding(text: str) -> list[float] | None:
    """
    Generate a vector embedding for the given text.

    Uses Ollama (free, local) when available, falling back to None if
    Ollama is not running.  When Bedrock API keys are configured, the
    Bedrock embedding model is used instead — set EMBEDDING_MODEL_ID +
    EMBEDDING_DIMENSION in .env to switch.

    Returns:
        A list of floats (padded to match the DB VECTOR(n) column dimension)
        on success.  None if the embedding backend is not available or
        the call fails.
    """
    from ai.bedrock_client import invoke_embedding

    result = invoke_embedding(text)
    if result is None:
        logger.debug(
            "generate_embedding: embedding backend returned None. "
            "Ensure Ollama is running (ollama pull qwen2.5:7b) or "
            "configure Bedrock API keys in .env."
        )
        return None

    return _pad_to_db_dimension(result)


def batch_generate_embeddings(texts: list[str]) -> list[list[float] | None]:
    """
    Generate embeddings for a batch of texts.

    Returns a list of the same length as `texts`, where each element is either
    a vector (list[float]) or None if generation failed for that item.

    Phase 2: Implement efficient batch calls if the backend supports them,
    otherwise call generate_embedding() per item with controlled concurrency.
    """
    return [generate_embedding(t) for t in texts]


def format_vector(values: list[float] | None) -> str | None:
    """Return a CockroachDB-compatible vector literal, or None if input is None/empty."""
    if not values:
        return None
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def generate_embedding_for_capture(text: str, max_length: int = 500) -> str | None:
    """Convenience wrapper for capture paths: generate embedding from truncated text."""
    if not text:
        return None
    truncated = text[:max_length]
    vector = generate_embedding(truncated)
    return format_vector(vector)

