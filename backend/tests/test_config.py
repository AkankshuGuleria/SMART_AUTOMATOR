"""
tests/test_config.py — Phase 0 smoke tests for backend/config.py.

These tests verify that:
1. The config module loads without a .env file present.
2. settings exposes the expected attributes with safe defaults.
3. Availability flags return correct boolean values based on what's configured.
4. No crash occurs when all env vars are missing (graceful degradation).

These tests must NOT require a real DB or Bedrock connection — they test
config loading only. See SKILLS.md §1 (unit tests must not make live network calls).
"""

import os
import sys

import pytest


def _reload_config(monkeypatch, env_overrides: dict) -> object:
    """
    Helper: clear environment, apply overrides, and freshly import config.
    Needed because config.py runs _load_settings() at module import time.
    """
    # Remove all AUTOMATA env vars from the environment
    automata_keys = [
        "COCKROACHDB_CONNECTION_STRING",
        "AWS_REGION",
        "AWS_BEDROCK_MODEL_ID",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "EMBEDDING_MODEL_ID",
        "EMBEDDING_DIMENSION",
        "LOG_LEVEL",
    ]
    for key in automata_keys:
        monkeypatch.delenv(key, raising=False)

    # Apply the overrides for this test
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    # Force a fresh import of config so _load_settings() runs with the new env
    # Remove all cached modules that import config
    modules_to_clear = [
        k
        for k in sys.modules
        if k.startswith("config") or k.startswith("backend.config") or k.startswith("ai") or k.startswith("backend.ai")
    ]
    for mod in modules_to_clear:
        del sys.modules[mod]

    # Also clear the backend package cache so submodules re-import
    backend_modules = [k for k in sys.modules if k.startswith("backend.")]
    for mod in backend_modules:
        del sys.modules[mod]

    # Ensure backend/ is on the path (for running tests from the backend dir)
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Remove .env from the path so config.py doesn't load real credentials
    env_path = os.path.join(backend_dir, ".env")
    if os.path.exists(env_path):
        # Temporarily rename .env so config.py doesn't load it
        env_backup = env_path + ".test_backup"
        os.rename(env_path, env_backup)
        try:
            import config  # noqa: PLC0415 — intentional dynamic import
            result = config.settings
        finally:
            os.rename(env_backup, env_path)
        return result

    import config  # noqa: PLC0415 — intentional dynamic import
    return config.settings


class TestSettingsDefaults:
    """Settings loads with safe defaults when no .env is present."""

    def test_loads_without_env_file(self, monkeypatch):
        """Config must not raise when all env vars are missing."""
        s = _reload_config(monkeypatch, {})
        assert s is not None

    def test_db_unavailable_when_no_connection_string(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        assert s.db_available is False

    def test_bedrock_unavailable_when_no_region(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        assert s.bedrock_available is False

    def test_embedding_unavailable_when_no_model(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        assert s.embedding_available is False

    def test_log_level_default_is_info(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        assert s.log_level == "INFO"

    def test_embedding_dimension_default_is_zero(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        assert s.embedding_dimension == 0


class TestSettingsWithValues:
    """Settings correctly reflects values when env vars are provided."""

    def test_db_available_when_connection_string_set(self, monkeypatch):
        s = _reload_config(monkeypatch, {
            "COCKROACHDB_CONNECTION_STRING": "postgresql+psycopg2://user:pass@host/db"
        })
        assert s.db_available is True

    def test_bedrock_available_when_region_and_model_set(self, monkeypatch):
        s = _reload_config(monkeypatch, {
            "AWS_REGION": "us-east-1",
            "AWS_BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        })
        assert s.bedrock_available is True

    def test_embedding_available_when_model_and_dimension_set(self, monkeypatch):
        s = _reload_config(monkeypatch, {
            "EMBEDDING_MODEL_ID": "amazon.titan-embed-text-v2:0",
            "EMBEDDING_DIMENSION": "1024",
        })
        assert s.embedding_available is True

    def test_log_level_from_env(self, monkeypatch):
        s = _reload_config(monkeypatch, {"LOG_LEVEL": "debug"})
        assert s.log_level == "DEBUG"  # config normalizes to upper

    def test_invalid_embedding_dimension_defaults_to_zero(self, monkeypatch):
        s = _reload_config(monkeypatch, {"EMBEDDING_DIMENSION": "not_a_number"})
        assert s.embedding_dimension == 0


class TestSettingsImmutability:
    """Settings object must be immutable (frozen dataclass)."""

    def test_settings_is_frozen(self, monkeypatch):
        s = _reload_config(monkeypatch, {})
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            s.log_level = "DEBUG"  # type: ignore

