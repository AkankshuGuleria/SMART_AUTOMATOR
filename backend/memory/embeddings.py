"""
memory/embeddings.py — AUTOMATA Persistent Memory Engine: embedding generation.

Owns:    Generating vector embeddings for semantically rich content
         (commit messages, TODOs, architecture notes, session summaries,
         README text) before writing them to CockroachDB vector columns.
Never:   Must not write to CockroachDB directly (→ db/client.py).
         Must not call Bedrock for reasoning (→ ai/bedrock_client.py).
         Embedding is a data-preparation step, not a reasoning step.
Ref:     ARCHITECTURE.md §3.2a (Memory Lifecycle), DATABASE_SCHEMA.md §3.

Phase 0: Stub — generate_embedding() returns None (no model configured yet).
Phase 2: Wire to the Bedrock embedding model configured in config.settings.
         The embedding model ID and dimension must match the VECTOR(n) column
         size in schema.sql — see DATABASE_SCHEMA.md §5 open question.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate a vector embedding for the given text via Amazon Bedrock.

    Returns:
        A list of floats (the embedding vector) on success.
        None if the embedding model is not configured or the call fails.

    Phase 0: Always returns None — model not yet configured.
    Phase 2 implementation:
        - Use ai/bedrock_client.invoke_embedding(text).
        - Validate that len(result) == settings.embedding_dimension.
        - Return None (with a warning log) on failure — callers must handle None
          gracefully (store the row without the embedding vector; mark for
          back-fill once the model is available).
    """
    from config import settings  # local import to avoid circular dependency

    if not settings.embedding_available:
        logger.debug(
            "generate_embedding: embedding model not configured — returning None. "
            "Set EMBEDDING_MODEL_ID and EMBEDDING_DIMENSION in .env to enable."
        )
        return None

    # TODO (Phase 2): call bedrock_client.invoke_embedding(text)
    logger.warning("generate_embedding: Phase 0 stub — embedding pipeline not yet implemented")
    return None


def batch_generate_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Generate embeddings for a batch of texts.

    Returns a list of the same length as `texts`, where each element is either
    a vector (list[float]) or None if generation failed for that item.

    Phase 2: Implement efficient batch calls if the Bedrock model supports them,
    otherwise call generate_embedding() per item with controlled concurrency.
    """
    return [generate_embedding(t) for t in texts]
