"""
config.py — AUTOMATA global configuration.

Owns:    Loading and validating environment variables for the entire backend.
Never:   Does not connect to any external service — pure config loading only.
         Does not store secret values — only reads them from the environment.
Ref:     TECH_STACK.md → "Environment variables", SKILLS.md §8.

Usage:
    from backend.config import settings

    print(settings.cockroachdb_connection_string)
    if settings.db_available:
        # safe to attempt a DB connection

All modules must import `settings` from here — never call os.getenv()
directly in feature modules.
"""

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file from the backend directory if present.
# In production / CI, vars should be injected by the environment directly.
_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path, override=False)


@dataclass(frozen=True)
class Settings:
    """
    Immutable settings object populated from environment variables at startup.

    Items that are required for a feature to function are documented per field.
    Missing optional values degrade gracefully (DB/Bedrock start in a
    disconnected state rather than crashing the agent process).
    """

    # ─── Database ─────────────────────────────────────────────────────────────
    # Required for Phase 1+ — Phase 0 runs without it.
    cockroachdb_connection_string: str = field(default="")

    # ─── AWS / Bedrock ────────────────────────────────────────────────────────
    # Required for Phase 2+ reasoning and embedding pipeline.
    aws_region: str = field(default="")
    aws_bedrock_model_id: str = field(default="")
    aws_access_key_id: str = field(default="")
    aws_secret_access_key: str = field(default="")

    # ─── Embedding ────────────────────────────────────────────────────────────
    # Required for Phase 2+ vector pipeline.
    embedding_model_id: str = field(default="")
    embedding_dimension: int = field(default=0)

    # ─── Logging ──────────────────────────────────────────────────────────────
    log_level: str = field(default="INFO")

    # ─── Derived availability flags (read-only convenience properties) ─────────
    @property
    def db_available(self) -> bool:
        """True if a CockroachDB connection string has been supplied."""
        return bool(self.cockroachdb_connection_string)

    @property
    def bedrock_available(self) -> bool:
        """True if minimum Bedrock config is present."""
        return bool(self.aws_region and self.aws_bedrock_model_id)

    @property
    def embedding_available(self) -> bool:
        """True if the embedding model and dimension are configured."""
        return bool(self.embedding_model_id and self.embedding_dimension > 0)


def _load_settings() -> Settings:
    """Build the Settings object from the current environment."""
    raw_dim = os.getenv("EMBEDDING_DIMENSION", "0")
    try:
        dim = int(raw_dim)
    except ValueError:
        logger.warning("EMBEDDING_DIMENSION is not an integer ('%s'); defaulting to 0", raw_dim)
        dim = 0

    s = Settings(
        cockroachdb_connection_string=os.getenv("COCKROACHDB_CONNECTION_STRING", ""),
        aws_region=os.getenv("AWS_REGION", ""),
        aws_bedrock_model_id=os.getenv("AWS_BEDROCK_MODEL_ID", ""),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        embedding_model_id=os.getenv("EMBEDDING_MODEL_ID", ""),
        embedding_dimension=dim,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )

    # Log availability status at startup — never log the actual secret values.
    logger.info(
        "Config loaded | db_available=%s | bedrock_available=%s | embedding_available=%s",
        s.db_available,
        s.bedrock_available,
        s.embedding_available,
    )

    if not s.db_available:
        logger.warning(
            "COCKROACHDB_CONNECTION_STRING not set — "
            "Persistent Memory Engine will run in disconnected mode. "
            "Provide the connection string in backend/.env to enable Phase 1 features."
        )
    if not s.bedrock_available:
        logger.warning(
            "AWS_REGION or AWS_BEDROCK_MODEL_ID not set — "
            "Reasoning Engine will be unavailable. "
            "Required for Phase 2+ features."
        )

    return s


# Single global instance — import this everywhere.
settings: Settings = _load_settings()
