"""
tests/conftest.py — AUTOMATA test configuration.

Owns:    Session-scoped test fixtures, temp-directory configuration
Never:   Business logic, DB writes, Bedrock calls
Ref:     ARCHITECTURE.md §Component map (API server), CONVENTIONS.md §2
"""

import os
import shutil
from pathlib import Path


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
