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
from typing import Optional

logger = logging.getLogger(__name__)


def generate_embedding(text: str) -> Optional[list[float]]:
    """
    Generate a vector embedding for the given text.

    Currently uses Ollama (free, local). When Bedrock API keys are
    available, uncomment the Bedrock section in ai/bedrock_client.py
    and set EMBEDDING_MODEL_ID + EMBEDDING_DIMENSION in .env to switch.

    Returns:
        A list of floats (the embedding vector) on success.
        None if the embedding backend is not available or the call fails.
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

    return result


def batch_generate_embeddings(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Generate embeddings for a batch of texts.

    Returns a list of the same length as `texts`, where each element is either
    a vector (list[float]) or None if generation failed for that item.

    Phase 2: Implement efficient batch calls if the backend supports them,
    otherwise call generate_embedding() per item with controlled concurrency.
    """
    return [generate_embedding(t) for t in texts]
