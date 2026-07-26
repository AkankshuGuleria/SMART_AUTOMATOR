"""
tests/test_check_env_script.py - scripts/check_env.py unit tests.

These tests validate environment readiness logic without requiring real
credentials, CockroachDB, or AWS access.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_env import collect_status  # noqa: E402


def test_phase1_reports_missing_db_when_env_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("COCKROACHDB_CONNECTION_STRING", raising=False)
    # Use a temp .env file that doesn't exist
    env_file = tmp_path / ".env"
    ok, missing = collect_status("phase1", env_file)
    assert "COCKROACHDB_CONNECTION_STRING" in missing
    assert "COCKROACHDB_CONNECTION_STRING" not in ok
    assert "LOG_LEVEL" not in missing


def test_phase1_accepts_real_db_value(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOG_LEVEL=INFO\n"
        "COCKROACHDB_CONNECTION_STRING=postgresql+psycopg2://user:pass@host/db\n",
        encoding="utf-8",
    )

    ok, missing = collect_status("phase1", env_file)
    assert "COCKROACHDB_CONNECTION_STRING" in ok
    assert "COCKROACHDB_CONNECTION_STRING" not in missing


def test_placeholder_values_are_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("COCKROACHDB_CONNECTION_STRING", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "COCKROACHDB_CONNECTION_STRING=REPLACE_WITH_COCKROACHDB_CONNECTION_STRING\n",
        encoding="utf-8",
    )

    ok, missing = collect_status("phase1", env_file)
    assert "COCKROACHDB_CONNECTION_STRING" in missing
    assert "COCKROACHDB_CONNECTION_STRING" not in ok
