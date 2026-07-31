"""
tests/test_visual_feedback.py - Visual feedback layer tests.

Tests the visual feedback tools: capture_screen, ocr_image,
read_visible_context, diagnose_visible_error, review_visible_design,
generate_prompt_from_screen, verify_visible_result.
"""

from decision_engine.tools import execute_tool, get_tool


def test_capture_screen_tool_registered() -> None:
    tool = get_tool("capture_screen")
    assert tool is not None
    assert tool.policy == "confirm_once"


def test_ocr_image_tool_registered() -> None:
    tool = get_tool("ocr_image")
    assert tool is not None
    assert tool.policy == "auto_execute"


def test_read_visible_context_tool_registered() -> None:
    tool = get_tool("read_visible_context")
    assert tool is not None
    assert tool.policy == "confirm_once"


def test_diagnose_visible_error_tool_registered() -> None:
    tool = get_tool("diagnose_visible_error")
    assert tool is not None
    assert tool.policy == "confirm_once"


def test_review_visible_design_tool_registered() -> None:
    tool = get_tool("review_visible_design")
    assert tool is not None
    assert tool.policy == "confirm_once"


def test_generate_prompt_from_screen_tool_registered() -> None:
    tool = get_tool("generate_prompt_from_screen")
    assert tool is not None
    assert tool.policy == "auto_execute"


def test_verify_visible_result_tool_registered() -> None:
    tool = get_tool("verify_visible_result")
    assert tool is not None
    assert tool.policy == "auto_execute"


def test_capture_screen_missing_params() -> None:
    result = execute_tool("capture_screen", {})
    # The tool delegates to os_windows.capture_screen which may fail
    # without a display, but should not crash.
    assert isinstance(result, dict)
    assert "success" in result


def test_ocr_image_missing_path() -> None:
    result = execute_tool("ocr_image", {})
    assert result["success"] is False
    assert "image_path is required" in result.get("error", "")


def test_ocr_image_nonexistent_file() -> None:
    result = execute_tool("ocr_image", {"image_path": "/nonexistent/path.png"})
    assert result["success"] is False


def test_read_visible_context_returns_dict() -> None:
    result = execute_tool("read_visible_context", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_diagnose_visible_error_returns_dict() -> None:
    result = execute_tool("diagnose_visible_error", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_review_visible_design_returns_dict() -> None:
    result = execute_tool("review_visible_design", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_generate_prompt_from_screen_returns_dict() -> None:
    result = execute_tool("generate_prompt_from_screen", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_verify_visible_result_returns_dict() -> None:
    result = execute_tool("verify_visible_result", {})
    assert isinstance(result, dict)
    assert "success" in result


def test_redact_secrets_in_ocr() -> None:
    """OCR module redacts secrets from extracted text."""
    from automation.ocr import redact_secrets

    text = "Here is my token: ghp_abcdefghijklmnopqrstuvwxyz123456789012"
    redacted = redact_secrets(text)
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456789012" not in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted


def test_redact_secrets_preserves_normal_text() -> None:
    from automation.ocr import redact_secrets

    text = "This is normal text with no secrets."
    assert redact_secrets(text) == text


def test_redact_secrets_aws_key() -> None:
    from automation.ocr import redact_secrets

    text = "AWS key: AKIAIOSFODNN7EXAMPLE"
    redacted = redact_secrets(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_redact_secrets_openai_key() -> None:
    from automation.ocr import redact_secrets

    text = "OpenAI key: sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234"
    redacted = redact_secrets(text)
    assert "sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234" not in redacted
    assert "[REDACTED_OPENAI_KEY]" in redacted


def test_redact_secrets_password() -> None:
    from automation.ocr import redact_secrets

    text = "password=hunter2"
    redacted = redact_secrets(text)
    assert "hunter2" not in redacted
    assert "password=[REDACTED]" in redacted


def test_redact_secrets_bearer() -> None:
    from automation.ocr import redact_secrets

    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9"
    redacted = redact_secrets(text)
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted
    assert "[REDACTED]" in redacted
