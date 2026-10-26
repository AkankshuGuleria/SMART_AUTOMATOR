"""
tests/test_cross_app_tools.py - Cross-app control tool tests.

Tests the new cross-app control tools registered in decision_engine/tools.py:
copy_to_clipboard, paste_clipboard, open_url, focus_app, send_keystroke,
submit_prompt_to_app, verify_result.

No live OS calls are made — tool dispatch is tested via execute_tool.
"""

from unittest.mock import patch

from decision_engine.tools import execute_tool, get_tool, get_tool_descriptions


def test_copy_to_clipboard_tool_registered() -> None:
    tool = get_tool("copy_to_clipboard")
    assert tool is not None
    assert tool.policy == "auto_execute"
    assert tool.risk == "low"


def test_paste_clipboard_tool_registered() -> None:
    tool = get_tool("paste_clipboard")
    assert tool is not None
    assert tool.policy == "confirm_once"
    assert tool.risk == "medium"


def test_open_url_tool_registered() -> None:
    tool = get_tool("open_url")
    assert tool is not None
    assert tool.policy == "auto_execute"
    assert tool.risk == "low"


def test_focus_app_tool_registered() -> None:
    tool = get_tool("focus_app")
    assert tool is not None
    assert tool.policy == "confirm_once"
    assert tool.risk == "medium"


def test_send_keystroke_tool_registered() -> None:
    tool = get_tool("send_keystroke")
    assert tool is not None
    assert tool.policy == "confirm_once"
    assert tool.risk == "medium"


def test_submit_prompt_to_app_tool_registered() -> None:
    tool = get_tool("submit_prompt_to_app")
    assert tool is not None
    assert tool.policy == "require_approval"
    assert tool.risk == "high"
    assert tool.requires_approval is True


def test_verify_result_tool_registered() -> None:
    tool = get_tool("verify_result")
    assert tool is not None
    assert tool.policy == "auto_execute"
    assert tool.risk == "low"


def test_copy_to_clipboard_missing_text() -> None:
    result = execute_tool("copy_to_clipboard", {})
    assert result["success"] is False
    assert "text is required" in result.get("error", "")


def test_open_url_missing_url() -> None:
    result = execute_tool("open_url", {})
    assert result["success"] is False
    assert "url is required" in result.get("error", "")


def test_focus_app_missing_app_name() -> None:
    result = execute_tool("focus_app", {})
    assert result["success"] is False
    assert "app_name is required" in result.get("error", "")


def test_send_keystroke_missing_keystrokes() -> None:
    result = execute_tool("send_keystroke", {})
    assert result["success"] is False
    assert "keystrokes is required" in result.get("error", "")


def test_submit_prompt_to_app_missing_prompt() -> None:
    result = execute_tool("submit_prompt_to_app", {})
    assert result["success"] is False
    assert "prompt is required" in result.get("error", "")


def test_verify_result_missing_type() -> None:
    result = execute_tool("verify_result", {})
    assert result["success"] is False
    assert "type is required" in result.get("error", "")


def test_tool_descriptions_include_policy() -> None:
    descs = get_tool_descriptions()
    policy_names = {d["name"]: d.get("policy") for d in descs}
    assert policy_names.get("copy_to_clipboard") == "auto_execute"
    assert policy_names.get("paste_clipboard") == "confirm_once"
    assert policy_names.get("submit_prompt_to_app") == "require_approval"


def test_unsafe_keystroke_rejected_by_tool() -> None:
    # send_keystroke only allows safe keystrokes; unsafe ones are rejected
    # at the OS level, but the tool itself accepts the param and delegates.
    # The tool returns success=False for unsafe keystrokes.
    result = execute_tool("send_keystroke", {"keystrokes": "rm -rf /"})
    assert result["success"] is False


def test_safe_keystroke_accepted_by_tool() -> None:
    # Ctrl+V is in the safe list; the tool will attempt to send it.
    # On a test machine without a GUI, it may fail, but the tool should
    # not reject the keystroke itself.
    result = execute_tool("send_keystroke", {"keystrokes": "ctrl+v"})
    # The tool may succeed or fail depending on the OS environment,
    # but it should not return an error about the keystroke being unsafe.
    assert "unsafe" not in result.get("error", "").lower()


def test_paste_clipboard_is_blocked_without_desktop_input() -> None:
    # The suite disables synthetic input; paste must report that, not pretend.
    result = execute_tool("paste_clipboard", {})
    assert result["success"] is False
    assert "disabled" in result["error"].lower()


@patch("automation.os_windows.read_clipboard", return_value="copied prompt")
def test_verify_result_uses_clipboard_read_not_paste(mock_read) -> None:
    result = execute_tool("verify_result", {"type": "clipboard_has_content"})
    assert result["success"] is True
    assert result["verified"] is True
    assert result["content_preview"] == "copied prompt"
    mock_read.assert_called_once()
