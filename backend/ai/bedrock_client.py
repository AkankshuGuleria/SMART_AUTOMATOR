"""
ai/bedrock_client.py — AUTOMATA Reasoning Engine: Amazon Bedrock client.

Owns:    All calls to Amazon Bedrock — text generation (reasoning, summaries,
         commit messages, next-task suggestions) and embedding generation.
         Centralized retry logic, timeout limits, and graceful fallback.
Never:   Must not execute OS actions (→ automation/).
         Must not write to CockroachDB (→ db/client.py).
         Must not accept raw credential values — uses boto3 with env-var or
         IAM-role authentication only (see SKILLS.md §8).
Ref:     ARCHITECTURE.md §3.4, §3.2b, TECH_STACK.md "AI".

Phase 0: Stub — all methods return None with a warning log.
Phase 2: Wire to boto3 Bedrock runtime client with retry + timeout.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Timeout for a single Bedrock invocation (seconds).
# Tune in Phase 2 based on observed p95 latency for the chosen model.
BEDROCK_TIMEOUT_SECONDS = 30

# Maximum retry attempts on transient errors (throttling, 5xx).
BEDROCK_MAX_RETRIES = 3


def _get_client() -> Optional[Any]:
    """
    Return a boto3 bedrock-runtime client, or None if Bedrock is not configured.

    Uses boto3's standard credential chain:
    1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. IAM role (preferred for production/EC2)
    3. AWS credentials file
    Never passes credentials explicitly — see SKILLS.md §8.
    """
    from config import settings

    if not settings.bedrock_available:
        logger.warning(
            "bedrock_client: Bedrock not configured — "
            "AWS_REGION or AWS_BEDROCK_MODEL_ID missing. "
            "Reasoning Engine will be unavailable until configured."
        )
        return None

    try:
        import boto3  # type: ignore

        return boto3.client("bedrock-runtime", region_name=settings.aws_region)
    except Exception as exc:  # pragma: no cover
        logger.error("bedrock_client: Failed to create boto3 client — %s", exc)
        return None


def invoke_reasoning(
    system_prompt: str,
    user_message: str,
    retrieved_memories: list[dict] | None = None,
) -> Optional[str]:
    """
    Call Amazon Bedrock to generate a grounded response.

    Args:
        system_prompt:       The system-level instruction (from ai/prompts/).
        user_message:        The developer's question or command.
        retrieved_memories:  Structured memory rows from retrieval.py to ground
                             the answer. The model is instructed not to fabricate
                             facts not present in these memories (see SKILLS.md §5).

    Returns:
        The model's text response, or None if Bedrock is unavailable.
        Callers must handle None — return raw memories with a
        "reasoning unavailable" note instead of failing entirely
        (see ARCHITECTURE.md §10).

    Phase 2 implementation:
        - Build prompt from system_prompt + retrieved_memories + user_message.
        - Call bedrock_runtime.invoke_model() with retry + timeout.
        - Parse response body per the model's output format.
        - Apply SKILLS.md §6 output naturalness checks to strip AI filler.
    """
    from config import settings

    if not settings.bedrock_available:
        logger.debug("invoke_reasoning: Bedrock unavailable — returning None")
        return None

    # TODO (Phase 2): implement Bedrock invocation
    logger.warning("invoke_reasoning: Phase 0 stub — not yet implemented")
    return None


def invoke_embedding(text: str) -> Optional[list[float]]:
    """
    Call Amazon Bedrock to generate a vector embedding for the given text.

    Returns:
        List of floats (the embedding vector) or None on failure.
        Dimension must equal settings.embedding_dimension and match
        the VECTOR(n) column size in schema.sql.

    Phase 2 implementation:
        - Use the Bedrock Titan Embeddings (or decided model) invoke_model() call.
        - Validate output dimension matches settings.embedding_dimension.
        - Return None on error — memory/embeddings.py handles the None case by
          storing the row without a vector and flagging it for back-fill.
    """
    from config import settings

    if not settings.embedding_available:
        logger.debug("invoke_embedding: embedding model not configured — returning None")
        return None

    # TODO (Phase 2): implement embedding invocation
    logger.warning("invoke_embedding: Phase 0 stub — not yet implemented")
    return None
