"""
tests/test_capture_redaction.py - Phase 1 redaction tests.

These tests verify that captured terminal commands and diffs are sanitized
before storage or Bedrock use. They do not touch CockroachDB or Bedrock.
"""

from memory.capture import redact_secrets


def test_redacts_github_pat() -> None:
    text = "git clone https://ghp_abcdefghijklmnopqrstuvwxyz123456@github.com/org/repo"
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in redact_secrets(text)


def test_redacts_aws_access_key_id() -> None:
    text = "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF"
    assert "AKIA1234567890ABCDEF" not in redact_secrets(text)


def test_redacts_openai_style_key() -> None:
    text = "client --api-key sk-abcdefghijklmnopqrstuvwxyz"
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in redact_secrets(text)


def test_redacts_key_token_password_assignments() -> None:
    text = "key=abc123 token=def456 password=hunter2"
    redacted = redact_secrets(text)
    assert "abc123" not in redacted
    assert "def456" not in redacted
    assert "hunter2" not in redacted


def test_redacts_bearer_token() -> None:
    text = "curl -H 'Authorization: Bearer abc.def.ghi' https://example.test"
    assert "abc.def.ghi" not in redact_secrets(text)


def test_preserves_non_secret_text() -> None:
    text = "npm run build && pytest tests/"
    assert redact_secrets(text) == text
