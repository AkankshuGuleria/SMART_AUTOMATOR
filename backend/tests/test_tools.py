"""
tests/test_tools.py — AUTOMATA Decision Engine tool registry tests.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from decision_engine.tools import (
    Tool,
    execute_tool,
    filter_tools_by_config,
    get_available_tools,
    get_tool,
    get_tool_descriptions,
    register,
)


class TestRegistry:
    def test_get_tool_returns_registered_tool(self):
        tool = get_tool("run_command")
        assert tool is not None
        assert tool.name == "run_command"

    def test_get_tool_unknown_returns_none(self):
        assert get_tool("nonexistent_tool_xyz") is None

    def test_get_available_tools_not_empty(self):
        assert len(get_available_tools()) > 0

    def test_get_tool_descriptions_shape(self):
        descs = get_tool_descriptions()
        assert isinstance(descs, list)
        for d in descs:
            assert "name" in d
            assert "description" in d
            assert "input_schema" in d


class TestExecuteTool:
    def test_unknown_tool_returns_failure(self):
        result = execute_tool("nonexistent_tool_xyz", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_run_command_executes_shell(self):
        if os.name != "nt":
            pytest.skip("Windows-only shell test")
        with patch("automation.command_executor.CommandExecutor") as MockExec:
            instance = MockExec.return_value
            from automation.command_executor import CommandResult
            instance.execute.return_value = CommandResult(
                command="dir", status="ok", stdout="files", exit_code=0, executed=True
            )
            result = execute_tool("run_command", {"command": "dir"})
            assert result["success"] is True

    def test_read_file_reads_content(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
            f.write("hello world")
            f.flush()
            path = f.name
        try:
            result = execute_tool("read_file", {"path": path})
            assert result["success"] is True
            assert "hello world" in result["content"]
        finally:
            os.unlink(path)

    def test_write_file_writes_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "newdir", "file.txt")
            result = execute_tool("write_file", {"path": target, "content": "data"})
            assert result["success"] is True
            with open(target) as f:
                assert f.read() == "data"

    def test_apply_diff_patches_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            f.flush()
            path = f.name
        try:
            diff = "@@ -1,2 +1,2 @@\n line1\n-line2\n+line2 modified\n"
            result = execute_tool("apply_diff", {"path": path, "diff": diff})
            assert result["success"] is True
            with open(path) as f:
                content = f.read()
            assert "line2 modified" in content
        finally:
            os.unlink(path)

    def test_apply_diff_empty_diff_fails(self):
        result = execute_tool("apply_diff", {"path": "/tmp/nonexistent_xyz_12345.txt", "diff": ""})
        assert result["success"] is False

    def test_retrieve_memory_requires_fields(self):
        result = execute_tool("retrieve_memory", {"query": "x"})
        assert result["success"] is False

    def test_retrieve_memory_calls_retrieval(self):
        mock_ret = MagicMock(return_value={"success": True, "memories": [], "count": 0})
        temp_tool = Tool(
            name="retrieve_memory_temp",
            description="Search memory",
            input_schema={"query": "string"},
            execute=mock_ret,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
        register(temp_tool)
        try:
            result = execute_tool("retrieve_memory_temp", {"project_id": "p1", "query": "test"})
            assert result["success"] is True
            mock_ret.assert_called_once()
        finally:
            from decision_engine.tools import _REGISTRY
            _REGISTRY.pop("retrieve_memory_temp", None)

    def test_filter_tools_by_config(self):
        with patch.dict(os.environ, {}, clear=True):
            tools = filter_tools_by_config()
            assert isinstance(tools, list)
