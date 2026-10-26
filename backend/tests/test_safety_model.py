"""
tests/test_safety_model.py - Safety model / policy routing tests.

Tests the three execution policies (auto_execute, confirm_once,
require_approval) in the decision engine planner.
"""

from decision_engine.planner import ACTION_POLICY, plan


def test_auto_execute_policies() -> None:
    """auto_execute actions run without user confirmation."""
    auto_actions = [
        action_type
        for action_type, policy in ACTION_POLICY.items()
        if policy == "auto_execute"
    ]
    assert "copy_to_clipboard" in auto_actions
    assert "open_url" in auto_actions
    assert "verify_result" in auto_actions
    assert "generate_prompt_from_screen" in auto_actions
    assert "ocr_image" in auto_actions
    assert "verify_visible_result" in auto_actions


def test_confirm_once_policies() -> None:
    """confirm_once actions require user acknowledgment."""
    confirm_actions = [
        action_type
        for action_type, policy in ACTION_POLICY.items()
        if policy == "confirm_once"
    ]
    assert "paste_clipboard" in confirm_actions
    assert "focus_app" in confirm_actions
    assert "send_keystroke" in confirm_actions
    assert "capture_screen" in confirm_actions
    assert "read_visible_context" in confirm_actions
    assert "diagnose_visible_error" in confirm_actions
    assert "review_visible_design" in confirm_actions


def test_require_approval_policies() -> None:
    """require_approval actions need explicit user approval."""
    approval_actions = [
        action_type
        for action_type, policy in ACTION_POLICY.items()
        if policy == "require_approval"
    ]
    assert "submit_prompt_to_app" in approval_actions


def test_plan_returns_actions_with_policy() -> None:
    """plan() returns actions with the correct policy field."""
    result = plan("chat:copy_to_clipboard", {
        "project_id": "test-project",
        "message": "copy this text",
        "parsed": {"target": "hello world"},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "confirm_once"  # clipboard = controlling the PC: ask first
    assert actions[0]["type"] == "copy_to_clipboard"


def test_plan_paste_clipboard_is_confirm_once() -> None:
    """paste_clipboard should have confirm_once policy."""
    result = plan("chat:paste_clipboard", {
        "project_id": "test-project",
        "message": "paste it",
        "parsed": {},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "confirm_once"
    assert actions[0]["type"] == "paste_clipboard"


def test_plan_submit_prompt_is_require_approval() -> None:
    """submit_prompt_to_app should have require_approval policy."""
    result = plan("chat:submit_prompt", {
        "project_id": "test-project",
        "message": "submit this prompt to chatgpt",
        "parsed": {"app_name": "chatgpt", "url": "", "target": "submit the prompt"},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "require_approval"
    assert actions[0]["type"] == "submit_prompt_to_app"


def test_plan_focus_app_is_confirm_once() -> None:
    """focus_app should have confirm_once policy."""
    result = plan("chat:focus_app", {
        "project_id": "test-project",
        "message": "focus vscode",
        "parsed": {"target": "vscode"},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "confirm_once"
    assert actions[0]["type"] == "focus_app"


def test_plan_capture_screen_is_confirm_once() -> None:
    """capture_screen should have confirm_once policy."""
    result = plan("chat:capture_screen", {
        "project_id": "test-project",
        "message": "capture screen",
        "parsed": {},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "confirm_once"
    assert actions[0]["type"] == "capture_screen"


def test_plan_verify_result_is_auto_execute() -> None:
    """verify_result should have auto_execute policy."""
    result = plan("chat:verify_result", {
        "project_id": "test-project",
        "message": "verify the result",
        "parsed": {},
    })
    actions = result.get("actions", [])
    assert len(actions) > 0
    assert actions[0]["policy"] == "auto_execute"
    assert actions[0]["type"] == "verify_result"


def test_plan_unknown_trigger_returns_empty() -> None:
    """Unknown triggers return an empty actions list."""
    result = plan("chat:unknown_action", {
        "project_id": "test-project",
        "message": "do something unknown",
        "parsed": {},
    })
    assert result["actions"] == []
