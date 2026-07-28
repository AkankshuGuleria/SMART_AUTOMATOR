"""
tests/test_decision_planner.py — Phase 4.5 Decision Engine planner tests.

Tests the real executor in plan(), action handlers, and the border behavior
wired into triggers. All external services are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from decision_engine.planner import (
    ACTION_POLICY,
    plan,
    _build_brief_payload,
    _execute_flag_related_todos,
    _execute_regenerate_daily_brief,
    _execute_store_session_summary,
    _execute_suggest_next_task,
    _execute_update_project_summary,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

_TRIGGER_CONTEXT: dict[str, dict[str, str]] = {
    "project_id": "proj-123",
    "session_id": "sess-123",
    "commit_hash": "abc123def456",
    "commit_message": "Fix auth bug",
}


# ─── plan() shape and execution ───────────────────────────────────────────────

class TestPlanShape:

    def test_returns_trigger_and_actions(self):
        result = plan("on_commit", {"project_id": "proj-123"})
        assert "trigger" in result
        assert "actions" in result
        assert result["trigger"] == "on_commit"

    def test_on_commit_produces_three_actions(self):
        result = plan("on_commit", {"project_id": "proj-123"})
        assert len(result["actions"]) == 3

    def test_on_session_end_produces_three_actions(self):
        result = plan("on_session_end", {
            "project_id": "proj-123",
            "session_id": "sess-123",
        })
        assert len(result["actions"]) == 3

    def test_each_action_has_required_fields(self):
        result = plan("on_commit", {"project_id": "proj-123"})
        for action in result["actions"]:
            assert "type" in action
            assert "policy" in action
            assert "params" in action
            assert "provenance" in action
            assert "executed" in action
            assert "executed_at" in action


class TestPlanExecution:

    @patch("agent_actions.generate_project_summary", return_value={"summary": "ok"})
    @patch("db.client.upsert_daily_brief", return_value=True)
    @patch("db.client.update_todo_description", return_value=True)
    @patch("db.client.get_todos", return_value=[])
    def test_auto_execute_sets_executed_true(
        self, mock_get_todos, mock_update_desc, mock_upsert, mock_gen
    ):
        with patch("db.client.get_file_edits", return_value=[]), \
             patch("db.client.get_commits", return_value=[]):
            result = plan("on_commit", {"project_id": "proj-123"})
            for action in result["actions"]:
                assert action["executed"] is True
                assert action["executed_at"] is not None

    @patch("agent_actions.generate_project_summary", side_effect=RuntimeError("boom"))
    @patch("db.client.upsert_daily_brief", return_value=True)
    @patch("db.client.update_todo_description", return_value=True)
    @patch("db.client.get_todos", return_value=[])
    def test_failure_does_not_block_others(
        self, mock_get_todos, mock_update_desc, mock_upsert, mock_gen
    ):
        with patch("db.client.get_file_edits", return_value=[]), \
             patch("db.client.get_commits", return_value=[]):
            result = plan("on_commit", {"project_id": "proj-123"})
            types = {a["type"]: a for a in result["actions"]}
            assert types["update_project_summary"]["executed"] is False
            assert types["regenerate_daily_brief"]["executed"] is True
            assert types["flag_related_todos"]["executed"] is True

    def test_suggest_actions_are_not_executed(self):
        actions = [
            {
                "type": "restore_workspace",
                "policy": "suggest",
                "params": {"project_id": "proj-123"},
                "provenance": "test suggest",
            }
        ]
        with patch("decision_engine.planner._get_actions_for_trigger", return_value=actions), \
             patch("decision_engine.planner.insert_decision", return_value="dec-1"):
            result = plan("on_commit", {"project_id": "proj-123"})
            assert result["actions"][0]["executed"] is False
            assert result["actions"][0]["executed_at"] is None
            assert result["actions"][0]["policy"] == "suggest"


# ─── Action handlers ──────────────────────────────────────────────────────────

class TestUpdateProjectSummary:

    @patch("agent_actions.generate_project_summary", return_value={"summary": "ok"})
    def test_success(self, mock_gen):
        result = _execute_update_project_summary({"project_id": "proj-123"})
        assert result == {"summary": "ok"}
        mock_gen.assert_called_once_with("proj-123")

    @patch("agent_actions.generate_project_summary", return_value={"summary": None})
    def test_empty_summary_returns_false(self, mock_gen):
        result = _execute_update_project_summary({"project_id": "proj-123"})
        assert result is None

    @patch("agent_actions.generate_project_summary", side_effect=RuntimeError("bedrock down"))
    def test_bedrock_failure_fails_open(self, mock_gen):
        result = _execute_update_project_summary({"project_id": "proj-123"})
        assert result is None


class TestRegenerateDailyBrief:

    @patch("db.client.get_commits", return_value=[{"message": "feat: x"}])
    @patch("db.client.get_file_edits", return_value=[])
    @patch("db.client.get_todos", return_value=[])
    @patch("db.client.upsert_daily_brief", return_value=True)
    def test_success(self, mock_upsert, mock_todos, mock_edits, mock_commits):
        result = _execute_regenerate_daily_brief({"project_id": "proj-123"})
        assert result is not None
        assert result["commits_count"] == 1
        assert result["highlights"] == ["feat: x"]
        mock_upsert.assert_called_once()
        kwargs = mock_upsert.call_args[1]
        assert kwargs["commits_count"] == 1
        assert kwargs["highlights"] == ["feat: x"]

    @patch("db.client.get_commits", return_value=[])
    @patch("db.client.get_file_edits", return_value=[])
    @patch("db.client.get_todos", return_value=[])
    @patch("db.client.upsert_daily_brief", return_value=True)
    def test_no_data_still_writes(self, mock_upsert, mock_todos, mock_edits, mock_commits):
        result = _execute_regenerate_daily_brief({"project_id": "proj-123"})
        assert result is not None
        assert result["commits_count"] == 0


class TestFlagRelatedTodos:

    @patch("db.client.get_todos", return_value=[
        {"id": "todo-1", "description": "Fix bug"},
    ])
    @patch("db.client.update_todo_description", return_value=True)
    def test_flags_pending_todos(self, mock_update, mock_get):
        result = _execute_flag_related_todos({"project_id": "proj-123"})
        assert result == {"flagged": 1}
        mock_update.assert_called_once_with("todo-1", "[auto-flagged] Fix bug")

    @patch("db.client.get_todos", return_value=[])
    def test_no_pending_todos_skips(self, mock_get):
        result = _execute_flag_related_todos({"project_id": "proj-123"})
        assert result == {"flagged": 0}

    @patch("db.client.get_todos", side_effect=RuntimeError("db down"))
    def test_get_failure_returns_false(self, mock_get):
        result = _execute_flag_related_todos({"project_id": "proj-123"})
        assert result is None


class TestStoreSessionSummary:

    @patch("db.client.end_session", return_value=True)
    def test_success(self, mock_end):
        result = _execute_store_session_summary({
            "project_id": "proj-123",
            "session_id": "sess-123",
            "summary": "did some work",
        })
        assert result == {"stored": True}
        mock_end.assert_called_once_with("proj-123", "sess-123", summary="did some work")

    def test_missing_summary_skips(self):
        result = _execute_store_session_summary({
            "project_id": "proj-123",
            "session_id": "sess-123",
        })
        assert result is None

    def test_missing_ids_skips(self):
        assert _execute_store_session_summary({}) is None
        assert _execute_store_session_summary({"project_id": "proj-123"}) is None
        assert _execute_store_session_summary({"session_id": "sess-123"}) is None


class TestSuggestNextTask:

    @patch("db.client.get_todos", return_value=[
        {"id": "todo-1", "description": "Write tests"},
    ])
    def test_builds_fallback_text(self, mock_get):
        result = _execute_suggest_next_task({"project_id": "proj-123"})
        assert result is not None
        assert result["suggestion"] == "Pending: Write tests"
        assert result["pending_todos_count"] == 1

    @patch("db.client.get_todos", return_value=[])
    def test_no_todos_uses_fallback(self, mock_get):
        result = _execute_suggest_next_task({"project_id": "proj-123"})
        assert result is not None
        assert "No pending" in result["suggestion"]

    def test_missing_project_id_skips(self):
        assert _execute_suggest_next_task({}) is None


# ─── Brief payload builder ────────────────────────────────────────────────────

class TestBuildBriefPayload:

    @patch("db.client.get_commits", return_value=[
        {"message": "feat: add login\nbody"},
    ])
    @patch("db.client.get_file_edits", return_value=[
        {"file_path": "src/auth.py"},
    ])
    @patch("db.client.get_todos", return_value=[
        {"description": "Write docs"},
    ])
    def test_payload_shape(self, mock_todos, mock_edits, mock_commits):
        payload = _build_brief_payload("proj-123")
        assert payload["project_id"] == "proj-123"
        assert payload["commits_count"] == 1
        assert "feat: add login" in payload["highlights"]
        assert "Edited src/auth.py" in payload["highlights"]
        assert "Write docs" in payload["pending_items"]

    @patch("db.client.get_commits", return_value=[])
    @patch("db.client.get_file_edits", return_value=[])
    @patch("db.client.get_todos", return_value=[])
    def test_no_source_returns_empty_payload(self, mock_todos, mock_edits, mock_commits):
        payload = _build_brief_payload("proj-123")
        assert payload["commits_count"] == 0
        assert payload["highlights"] == []
        assert payload["pending_items"] == []
