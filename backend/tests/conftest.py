"""
tests/conftest.py — AUTOMATA test configuration.

Owns:    Session-scoped test fixtures, temp-directory configuration
Never:   Business logic, DB writes, Bedrock calls
Ref:     ARCHITECTURE.md §Component map (API server), CONVENTIONS.md §2
"""

import os
import shutil
from pathlib import Path

# Keep tests off the developer's real database and model providers. load_dotenv()
# never overrides variables that already exist, so blanking them here wins over
# backend/.env (SKILLS.md §1: no live DB or provider calls in automated tests).
for _key in (
    "COCKROACHDB_CONNECTION_STRING",
    "AWS_REGION",
    "AWS_BEDROCK_MODEL_ID",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "GROQ_API_KEY",
    "GROQ_EMBEDDING_API_KEY",
    "GEMINI_API_KEY",
    "NVIDIA_API_KEY",
    "MINIMAX_API_KEY",
    "OPENROUTER_API_KEY",
    "COHERE_API_KEY",
    "EMBEDDING_MODEL_ID",
    "EMBEDDING_DIMENSION",
):
    os.environ[_key] = ""
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"  # closed port: Ollama always "down"
os.environ["AUTOMATA_DISABLE_USAGE_TRACKER"] = "1"


def pytest_configure(config):
    basetemp = Path(config.rootdir) / ".pytest-tmp"
    basetemp.mkdir(exist_ok=True)
    config.option.basetemp = str(basetemp)


def pytest_sessionfinish(session, exitstatus):
    basetemp = Path(session.config.rootdir) / ".pytest-tmp"
    if basetemp.exists():
        shutil.rmtree(basetemp, ignore_errors=True)


# Reset cooldowns before each test so module-level timestamps from a previous
# test (e.g., all backends failed → cooldown active) don't block the next test.
import pytest


@pytest.fixture(autouse=True)
def _reset_cooldowns():
    from ai.bedrock_client import reset_embedding_cooldown, reset_llm_cooldown

    reset_embedding_cooldown()
    reset_llm_cooldown()
    yield
