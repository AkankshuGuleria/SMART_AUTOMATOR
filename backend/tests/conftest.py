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
