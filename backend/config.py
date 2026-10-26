"""
config.py — AUTOMATA global configuration.

Owns:    Loading and validating environment variables for the entire backend.
Never:   Does not connect to any external service — pure config loading only.
Ref:     TECH_STACK.md → "Environment variables", SKILLS.md §8.
"""

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=_env_path, override=False)


@dataclass(frozen=True)
class Settings:
    cockroachdb_connection_string: str = field(default="")
    aws_region: str = field(default="")
    aws_bedrock_model_id: str = field(default="")
    aws_access_key_id: str = field(default="")
    aws_secret_access_key: str = field(default="")
    ollama_base_url: str = field(default="http://localhost:11434")
    ollama_model: str = field(default="qwen2.5-coder:3b")
    ollama_embedding_model: str = field(default="nomic-embed-text")
    embedding_model_id: str = field(default="")
    embedding_dimension: int = field(default=0)
    log_level: str = field(default="INFO")
    reasoning_mode: str = field(default="auto")
    nvidia_api_key: str = field(default="")
    groq_api_key: str = field(default="")
    groq_embedding_api_key: str = field(default="")
    gemini_api_key: str = field(default="")
    minimax_api_key: str = field(default="")
    openrouter_api_key: str = field(default="")
    openrouter_model: str = field(default="poolside/laguna-s-2.1:free")
    cohere_api_key: str = field(default="")
    api_key: str = field(default="")

    @property
    def db_available(self) -> bool:
        return bool(self.cockroachdb_connection_string)

    @property
    def bedrock_available(self) -> bool:
        if not (self.aws_region and self.aws_bedrock_model_id):
            return False
        if self.aws_access_key_id == "REPLACE_WITH_ACCESS_KEY_ID":
            return False
        if self.aws_secret_access_key == "REPLACE_WITH_SECRET_ACCESS_KEY":  # noqa: S105
            return False
        return True

    @property
    def ollama_available(self) -> bool:
        return bool(self.ollama_base_url)

    @property
    def embedding_available(self) -> bool:
        return bool(self.embedding_model_id and self.embedding_dimension > 0)


def _load_settings() -> Settings:
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
        reasoning_mode=(os.getenv("REASONING_MODE", "auto") or "auto").lower(),
        nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_embedding_api_key=os.getenv("GROQ_EMBEDDING_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "poolside/laguna-s-2.1:free"),
        cohere_api_key=os.getenv("COHERE_API_KEY", ""),
        api_key=os.getenv("API_KEY", ""),
        ollama_embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL") or "qwen2.5-coder:3b",
    )

    logger.info(
        "Config loaded | db_available=%s | bedrock_available=%s | embedding_available=%s",
        s.db_available,
        s.bedrock_available,
        s.embedding_available,
    )

    if not s.db_available:
        logger.warning(
            "COCKROACHDB_CONNECTION_STRING not set — "
            "Persistent Memory Engine will run in disconnected mode."
        )

    return s


settings: Settings = _load_settings()


def data_dir() -> str:
    """Local, per-user data folder (memory, usage, logs). Created on first use.

    %LOCALAPPDATA%/AUTOMATA on Windows, ~/.automata elsewhere; override with
    AUTOMATA_DATA_DIR (tests point this at a temp folder).
    """
    override = os.environ.get("AUTOMATA_DATA_DIR")
    if override:
        path = override
    elif os.name == "nt":
        path = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AUTOMATA")
    else:
        path = os.path.join(os.path.expanduser("~"), ".automata")
    os.makedirs(path, exist_ok=True)
    return path
