"""
tests/test_orchestrator.py — AUTOMATA orchestrator loop tests.
"""

from unittest.mock import patch

from decision_engine.orchestrator import (
    MAX_ITERATIONS,
    _extract_json,
    _parse_plan,
    _parse_reflection,
    run_orchestrator,
)
from decision_engine.tools import Tool, register


class TestExtractJson:
    def test_pure_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced_json(self):
        text = "Here is JSON:\n```json\n{\"a\": 2}\n```\nDone."
        assert _extract_json(text) == {"a": 2}

    def test_garbage_returns_none(self):
        assert _extract_json("no json here") is None

    def test_empty_returns_none(self):
        assert _extract_json("") is None


class TestParsePlan:
    def test_valid_plan(self):
        text = '{"steps": [{"tool": "retrieve_memory", "params": {"q": "x"}}]}'
        steps = _parse_plan(text)
        assert len(steps) == 1
        assert steps[0]["tool"] == "retrieve_memory"

    def test_unknown_tool_is_skipped(self):
        text = '{"steps": [{"tool": "nonexistent_tool", "params": {}}]}'
        steps = _parse_plan(text)
        assert steps == []

    def test_empty_steps(self):
        assert _parse_plan(None) == []
        assert _parse_plan("") == []

    def test_malformed_step_missing_tool_is_skipped(self):
        text = '{"steps": [{"params": {}}]}'
        steps = _parse_plan(text)
        assert steps == []


class TestParseReflection:
    def test_continue_action(self):
        text = '{"action": "continue", "reason": "ok"}'
        parsed = _parse_reflection(text)
        assert parsed["action"] == "continue"

    def test_stop_action(self):
        text = '{"action": "stop", "success": true, "response": "done"}'
        parsed = _parse_reflection(text)
        assert parsed["action"] == "stop"
        assert parsed["success"] is True

    def test_none_returns_stop(self):
        parsed = _parse_reflection(None)
        assert parsed["action"] == "stop"

    def test_retry_with_params(self):
        text = '{"action": "retry", "params": {"command": "pytest -v"}}'
        parsed = _parse_reflection(text)
        assert parsed["action"] == "retry"
        assert parsed["params"] == {"command": "pytest -v"}


class TestRunOrchestrator:
    def test_happy_path_single_step(self):
        with patch("decision_engine.orchestrator._retrieve_memories", return_value=[]), \
             patch("decision_engine.orchestrator._retrieve_mistakes", return_value=[]), \
             patch("decision_engine.orchestrator._get_filtered_tool_descriptions", return_value=[
                 {"name": "retrieve_memory", "description": "Search memory", "risk": "low", "requires_approval": False, "input_schema": {}}
             ]), \
             patch("decision_engine.orchestrator._call_planner", side_effect=[
                 '{"steps": [{"tool": "retrieve_memory", "params": {"query": "x", "project_id": "p1"}, "reasoning": "test"}]}',
                 None,
             ]), \
             patch("decision_engine.orchestrator._call_reflector", return_value='{"action": "stop", "success": true, "response": "done"}'), \
             patch("decision_engine.orchestrator.execute_tool", return_value={"success": True, "result": "ok"}), \
             patch("decision_engine.orchestrator._record_decision", return_value="dec-1"), \
             patch("decision_engine.orchestrator._record_mistake"):
            result = run_orchestrator("test goal", project_id="p1")
            assert result.goal == "test goal"
            assert len(result.steps) == 1
            assert result.steps[0].tool == "retrieve_memory"
            assert result.success is True

    def test_user_approval_needed_stops_loop(self):
        register(Tool(
            name="fake_approval_tool",
            description="needs approval",
            input_schema={"x": "string"},
            execute=lambda p: {},
            reversible=False,
            risk="high",
            requires_approval=True,
        ))
        try:
            with patch("decision_engine.orchestrator._retrieve_memories", return_value=[]), \
                 patch("decision_engine.orchestrator._retrieve_mistakes", return_value=[]), \
                 patch("decision_engine.orchestrator._get_filtered_tool_descriptions", return_value=[
                     {"name": "fake_approval_tool", "description": "needs approval", "risk": "high", "requires_approval": True, "input_schema": {}}
                 ]), \
                 patch("decision_engine.orchestrator._call_planner", return_value='{"steps": [{"tool": "fake_approval_tool", "params": {}, "reasoning": "test"}]}'), \
                 patch("decision_engine.orchestrator._record_decision", return_value="dec-1"), \
                 patch("decision_engine.orchestrator._record_mistake"):
                result = run_orchestrator("test goal", project_id="p1")
                assert result.needs_approval is True
                assert len(result.steps) == 0
                assert result.success is False
        finally:
            from decision_engine.tools import _REGISTRY
            _REGISTRY.pop("fake_approval_tool", None)

    def test_max_iterations_stops_loop(self):
        with patch("decision_engine.orchestrator._retrieve_memories", return_value=[]), \
             patch("decision_engine.orchestrator._retrieve_mistakes", return_value=[]), \
             patch("decision_engine.orchestrator._get_filtered_tool_descriptions", return_value=[
                 {"name": "retrieve_memory", "description": "Search memory", "risk": "low", "requires_approval": False, "input_schema": {}}
             ]), \
             patch("decision_engine.orchestrator._call_planner", side_effect=[
                 '{"steps": [{"tool": "retrieve_memory", "params": {"query": "x", "project_id": "p1"}, "reasoning": "test"}]}'
             ] * (MAX_ITERATIONS + 5)), \
             patch("decision_engine.orchestrator._call_reflector", return_value='{"action": "retry"}'), \
             patch("decision_engine.orchestrator.execute_tool", return_value={"success": True}), \
             patch("decision_engine.orchestrator._record_decision", return_value="dec-1"), \
             patch("decision_engine.orchestrator._record_mistake"):
            result = run_orchestrator("test goal", project_id="p1")
            assert "max_iterations" in result.stopped_reason or "max_tool_calls" in result.stopped_reason

    def test_failure_records_mistake(self):
        with patch("decision_engine.orchestrator._retrieve_memories", return_value=[]), \
             patch("decision_engine.orchestrator._retrieve_mistakes", return_value=[]), \
             patch("decision_engine.orchestrator._get_filtered_tool_descriptions", return_value=[
                 {"name": "retrieve_memory", "description": "Search memory", "risk": "low", "requires_approval": False, "input_schema": {}}
             ]), \
             patch("decision_engine.orchestrator._call_planner", side_effect=[
                 '{"steps": [{"tool": "retrieve_memory", "params": {"query": "x", "project_id": "p1"}, "reasoning": "test"}]}',
                 None,
             ]), \
             patch("decision_engine.orchestrator._call_reflector", return_value='{"action": "stop", "success": false}'), \
             patch("decision_engine.orchestrator.execute_tool", return_value={"success": False, "error": "boom"}), \
             patch("decision_engine.orchestrator._record_decision", return_value="dec-1"), \
             patch("decision_engine.orchestrator._record_mistake", return_value="mist-1") as mock_mist:
            result = run_orchestrator("test goal", project_id="p1")
            assert result.success is False
            mock_mist.assert_called()

    def test_reflector_retry_does_not_advance_step(self):
        with patch("decision_engine.orchestrator._retrieve_memories", return_value=[]), \
             patch("decision_engine.orchestrator._retrieve_mistakes", return_value=[]), \
             patch("decision_engine.orchestrator._get_filtered_tool_descriptions", return_value=[
                 {"name": "retrieve_memory", "description": "Search memory", "risk": "low", "requires_approval": False, "input_schema": {}}
             ]), \
             patch("decision_engine.orchestrator._call_planner", side_effect=[
                 '{"steps": [{"tool": "retrieve_memory", "params": {"query": "x", "project_id": "p1"}, "reasoning": "test"}]}',
                 None,
             ]), \
             patch("decision_engine.orchestrator._call_reflector", side_effect=[
                 '{"action": "retry", "params": {"query": "retried", "project_id": "p1"}}',
                 '{"action": "stop", "success": true, "response": "ok"}',
             ]), \
             patch("decision_engine.orchestrator.execute_tool", return_value={"success": False, "error": "fail first"}), \
             patch("decision_engine.orchestrator._record_decision", return_value="dec-1"), \
             patch("decision_engine.orchestrator._record_mistake"):
            result = run_orchestrator("test goal", project_id="p1")
            # Should have 2 steps because of retry (same tool, retried then succeeded on second call)
            assert len(result.steps) == 2
            assert result.steps[0].tool == "retrieve_memory"
            assert result.steps[1].tool == "retrieve_memory"
            assert result.steps[0].params["query"] == "x"
            assert result.steps[1].params["query"] == "retried"
