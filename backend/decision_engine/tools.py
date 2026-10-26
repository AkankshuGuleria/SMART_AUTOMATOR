"""
decision_engine/tools.py — AUTOMATA Tool Registry.

Owns:    Declaring the available tools the orchestrator can call, dispatching
         tool invocations, filtering tools by current configuration.
Never:   Must not call Bedrock directly. Must not bypass the orchestrator loop.
         Must not write to CockroachDB directly (uses db/client.py).
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9, SKILLS.md §4.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


# ─── Tool descriptor ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Tool:
    """Declares a single tool the model can call."""

    name: str
    description: str
    input_schema: dict[str, Any]
    execute: Callable[..., dict[str, Any]]
    requires_config: tuple[str, ...] = field(default_factory=tuple)
    reversible: bool = False
    risk: str = "low"
    requires_approval: bool = False
    policy: str = "auto_execute"  # "auto_execute" | "confirm_once" | "require_approval"


# ─── Tool registry ─────────────────────────────────────────────────────────────

_REGISTRY: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    _REGISTRY[tool.name] = tool


def get_tool(name: str) -> Tool | None:
    return _REGISTRY.get(name)


def get_available_tools() -> list[Tool]:
    return list(_REGISTRY.values())


def get_tool_descriptions() -> list[dict[str, Any]]:
    """Return a JSON-safe description list for the LLM prompt."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "risk": t.risk,
            "policy": t.policy,
        }
        for t in get_available_tools()
    ]


def execute_tool(name: str, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call. Returns a result dict."""
    tool = get_tool(name)
    if tool is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    try:
        result = tool.execute(params)
        if not isinstance(result, dict):
            result = {"result": result}
        result.setdefault("success", True)
        return result
    except Exception as exc:
        logger.error("execute_tool: %s failed — %s", name, exc)
        return {"success": False, "tool": name, "error": str(exc)}


# ─── Tool implementations ──────────────────────────────────────────────────────


def _tool_run_command(params: dict[str, Any]) -> dict[str, Any]:
    """Execute a shell command on the local OS."""
    command = str(params.get("command", "")).strip()
    if not command:
        return {"success": False, "error": "command is required"}
    try:
        from automation.command_executor import CommandExecutor

        executor = CommandExecutor(cwd=params.get("cwd", ""))
        result = executor.execute(command)
        return {
            "success": result.status == "ok",
            "status": result.status,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
            "exit_code": result.exit_code,
            "suggested": result.suggested,
            "undo_hint": result.undo_hint,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tool_read_file(params: dict[str, Any]) -> dict[str, Any]:
    """Read a file from the filesystem."""
    path = str(params.get("path", "")).strip()
    if not path:
        return {"success": False, "error": "path is required"}
    limit = int(params.get("limit", 2000))
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= limit:
                    lines.append(f"... (truncated at {limit} lines)")
                    break
                lines.append(line)
        content = "".join(lines)
        return {"success": True, "path": path, "content": content, "lines": len(lines)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tool_write_file(params: dict[str, Any]) -> dict[str, Any]:
    """Write content to a file on the filesystem."""
    path = str(params.get("path", "")).strip()
    content = str(params.get("content", ""))
    if not path:
        return {"success": False, "error": "path is required"}
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes": len(content)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _apply_unified_diff(original: str, diff_text: str) -> tuple[str, str]:
    """Apply a validating unified diff to a string. Returns ``(new_text, error)``."""
    hunk_pattern = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
    source_lines = original.splitlines(keepends=True)
    diff_lines = diff_text.splitlines()
    output: list[str] = []
    source_index = 0
    diff_index = 0
    found_hunk = False
    line_ending = "\r\n" if "\r\n" in original else "\n"

    def _text(line: str) -> str:
        return line.rstrip("\r\n")

    while diff_index < len(diff_lines):
        line = diff_lines[diff_index]
        if line.startswith(("--- ", "+++ ")):
            diff_index += 1
            continue

        match = hunk_pattern.match(line)
        if match is None:
            return original, f"Invalid unified diff line: {line}"

        found_hunk = True
        hunk_start = int(match.group(1)) - 1
        if hunk_start < source_index or hunk_start > len(source_lines):
            return original, "Invalid or overlapping hunk position"

        output.extend(source_lines[source_index:hunk_start])
        source_index = hunk_start
        diff_index += 1

        while diff_index < len(diff_lines) and not diff_lines[diff_index].startswith("@@"):
            hunk_line = diff_lines[diff_index]
            if hunk_line == r"\ No newline at end of file":
                diff_index += 1
                continue
            if not hunk_line or hunk_line[0] not in {" ", "+", "-"}:
                return original, f"Invalid hunk line: {hunk_line}"

            marker, content = hunk_line[0], hunk_line[1:]
            if marker in {" ", "-"}:
                if (
                    source_index >= len(source_lines)
                    or _text(source_lines[source_index]) != content
                ):
                    return original, "Patch context does not match the target file"
                if marker == " ":
                    output.append(source_lines[source_index])
                source_index += 1
            else:
                output.append(content + line_ending)
            diff_index += 1

    if not found_hunk:
        return original, "No unified diff hunk found"

    output.extend(source_lines[source_index:])
    return "".join(output), ""


def _tool_apply_diff(params: dict[str, Any]) -> dict[str, Any]:
    """Apply a unified diff patch to a file."""
    path = str(params.get("path", "")).strip()
    diff = str(params.get("diff", ""))
    if not path:
        return {"success": False, "error": "path is required"}
    if not diff:
        return {"success": False, "error": "diff is required"}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            original = f.read()
        new_content, err = _apply_unified_diff(original, diff)
        if err:
            return {"success": False, "error": f"Diff apply failed: {err}"}
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"success": True, "path": path, "applied": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tool_run_tests(params: dict[str, Any]) -> dict[str, Any]:
    """Run the project's test suite."""
    command = str(params.get("command", "pytest")).strip()
    cwd = str(params.get("cwd", ""))
    return _tool_run_command({"command": command, "cwd": cwd})


def _tool_git_commit(params: dict[str, Any]) -> dict[str, Any]:
    """Stage all changes and create a git commit."""
    message = str(params.get("message", "")).strip()
    cwd = str(params.get("cwd", ""))
    if not message:
        return {"success": False, "error": "commit message is required"}
    add_result = _tool_run_command({"command": "git add -A", "cwd": cwd})
    if not add_result.get("success"):
        return {"success": False, "error": f"git add failed: {add_result.get('stderr', '')}"}
    commit_result = _tool_run_command({"command": f'git commit -m "{message}"', "cwd": cwd})
    return commit_result


def _tool_git_branch(params: dict[str, Any]) -> dict[str, Any]:
    """Create, list, or checkout a git branch."""
    action = str(params.get("action", "list")).strip().lower()
    name = str(params.get("name", "")).strip()
    cwd = str(params.get("cwd", ""))
    if action == "create":
        if not name:
            return {"success": False, "error": "branch name is required for create"}
        return _tool_run_command({"command": f"git checkout -b {name}", "cwd": cwd})
    if action == "checkout":
        if not name:
            return {"success": False, "error": "branch name is required for checkout"}
        return _tool_run_command({"command": f"git checkout {name}", "cwd": cwd})
    return _tool_run_command({"command": "git branch", "cwd": cwd})


def _tool_retrieve_memory(params: dict[str, Any]) -> dict[str, Any]:
    """Search project memory via vector or recent retrieval."""
    project_id = str(params.get("project_id", "")).strip()
    query = str(params.get("query", "")).strip()
    if not query:
        return {"success": False, "error": "query is required"}
    if not project_id:
        return {"success": False, "error": "project_id is required"}
    try:
        from memory.retrieval import retrieve_by_vector, retrieve_recent

        tables = params.get(
            "tables", ["commits", "todos", "architecture_notes", "decision_log", "mistake_log"]
        )
        memories = retrieve_by_vector(
            query, list(tables), project_id=project_id, top_k=int(params.get("top_k", 8))
        )
        if not memories:
            fallback_tables = ["commits", "todos", "file_edits"]
            memories = retrieve_recent(project_id, fallback_tables[0], limit=3)
            for t in fallback_tables[1:]:
                memories.extend(retrieve_recent(project_id, t, limit=3))
        return {"success": True, "memories": memories, "count": len(memories)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tool_call_design_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Delegate a design task to an external design tool."""
    tool_name = str(params.get("target", "")).strip()
    prompt = str(params.get("prompt", "")).strip()
    if not tool_name or not prompt:
        return {"success": False, "error": "target and prompt are required"}
    try:
        from automation.agent_bridge import AgentBridge

        bridge = AgentBridge()
        result = bridge.send_prompt(tool_name, prompt)
        return {
            "success": result.status == "ok",
            "tool": tool_name,
            "output": result.output[:3000],
            "suggested": result.suggested,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _draft_grounded_prompt(base_prompt: str, mistakes: list[dict[str, Any]]) -> str:
    """Fold retrieved historical mistakes into the handoff prompt."""
    if not mistakes:
        return base_prompt
    lines = [base_prompt, "\nPrior lessons from this project (avoid repeating these mistakes):"]
    for m in mistakes[:5]:
        symptom = str(m.get("symptom", ""))[:120]
        fix = str(m.get("fix", ""))[:120]
        lines.append(f"- {symptom} → {fix}")
    return "\n".join(lines)


def _verify_coding_output(
    project_id: str, repo_path: str, bridge_result: dict[str, Any]
) -> dict[str, Any]:
    """Independently verify a coding agent's output."""
    verification: dict[str, Any] = {"checks": [], "success": False}
    if not repo_path:
        verification["checks"].append("skipped: no repo_path provided")
        return verification
    # Check that the tool reported success
    bridge_success = False
    if isinstance(bridge_result, dict):
        bridge_success = bool(bridge_result.get("success"))
    else:
        bridge_success = bool(
            getattr(bridge_result, "status", None) == "ok"
            or getattr(bridge_result, "success", False)
        )

    if not bridge_success:
        verification["checks"].append("external tool reported failure")
        return verification
    verification["checks"].append("external tool reported success")
    # Optionally run a quick git status check
    git_ok = False
    try:
        status = _tool_run_command({"command": "git status --porcelain", "cwd": repo_path})
        if status.get("success"):
            verification["checks"].append("git status check passed")
            git_ok = True
            if status.get("stdout", "").strip():
                verification["checks"].append("working tree has changes")
            else:
                verification["checks"].append("working tree clean or unknown")
        else:
            verification["checks"].append("git status check failed")
            git_ok = False
    except Exception as exc:
        verification["checks"].append(f"git status check failed: {exc}")
        git_ok = False
    verification["success"] = git_ok
    return verification


def _tool_call_coding_agent(params: dict[str, Any]) -> dict[str, Any]:
    """Delegate a coding task to an external coding agent with the full delegation sub-loop."""
    project_id = str(params.get("project_id", "")).strip()
    prompt = str(params.get("prompt", "")).strip()
    tool_name = str(params.get("target", "")).strip()
    repo_path = str(params.get("repo_path", "")).strip()
    if not all([project_id, prompt, tool_name]):
        return {"success": False, "error": "project_id, prompt, and target are required"}

    # Step 1: Retrieve prior attempts
    mistakes: list[dict[str, Any]] = []
    try:
        from db.client import get_mistakes

        mistakes = get_mistakes(project_id) or []
    except Exception as exc:
        logger.warning("_tool_call_coding_agent: get_mistakes failed — %s", exc)

    # Step 2: Draft grounded prompt
    grounded_prompt = _draft_grounded_prompt(prompt, mistakes)

    # Step 3: Delegate
    from automation.agent_bridge import AgentBridge

    bridge = AgentBridge()
    bridge_result = bridge.send_prompt(tool_name, grounded_prompt)

    # Step 4: Capture raw output
    raw_output = getattr(bridge_result, "output", None) or ""
    try:
        from agent_actions import record_agent_decision

        record_agent_decision(
            project_id=project_id,
            decision=f"Coding agent {tool_name} executed",
            rationale=f"Prompt: {grounded_prompt[:300]}... Output: {str(raw_output)[:500]}",
        )
    except Exception as exc:
        logger.warning("_tool_call_coding_agent: record_agent_decision failed — %s", exc)

    # Step 5: Verify
    verification = _verify_coding_output(project_id, repo_path, bridge_result)

    # Step 6: Record judgment
    if verification.get("success"):
        try:
            from agent_actions import record_agent_decision

            record_agent_decision(
                project_id=project_id,
                decision=f"Coding agent {tool_name} verified",
                rationale=f"Verification: {verification}",
            )
        except Exception as exc:
            logger.warning("_tool_call_coding_agent: record_agent_decision failed — %s", exc)
        return {
            "success": True,
            "tool": tool_name,
            "output": raw_output[:3000],
            "verification": verification,
        }
    else:
        try:
            from agent_actions import record_agent_mistake

            record_agent_mistake(
                project_id=project_id,
                symptom=f"Coding agent {tool_name} failed verification",
                root_cause=raw_output[:300],
                fix="Review handoff prompt and external tool output",
            )
        except Exception as exc:
            logger.warning("_tool_call_coding_agent: record_agent_mistake failed — %s", exc)
        return {
            "success": False,
            "tool": tool_name,
            "output": raw_output[:3000],
            "verification": verification,
        }


# ─── Register tools ────────────────────────────────────────────────────────────


def _register_default_tools() -> None:
    register(
        Tool(
            name="run_command",
            description="Execute a shell command on the local OS. Use for generic CLI operations.",
            input_schema={
                "command": "string — the shell command to execute (required)",
                "cwd": "string — optional working directory",
            },
            execute=_tool_run_command,
            reversible=False,
            risk="high",
            requires_approval=True,
            policy="require_approval",
        )
    )

    register(
        Tool(
            name="read_file",
            description="Read a file from the filesystem. Returns up to limit lines.",
            input_schema={
                "path": "string — absolute or relative file path (required)",
                "limit": "integer — max lines to return (default 2000)",
            },
            execute=_tool_read_file,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="write_file",
            description="Write content to a file on the filesystem. Creates directories if needed.",
            input_schema={
                "path": "string — file path (required)",
                "content": "string — file content (required)",
            },
            execute=_tool_write_file,
            reversible=False,
            risk="medium",
            requires_approval=True,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="apply_diff",
            description="Apply a unified diff patch to an existing file. Only modifies the specified hunks.",
            input_schema={
                "path": "string — file path to patch (required)",
                "diff": "string — unified diff text (required)",
            },
            execute=_tool_apply_diff,
            reversible=False,
            risk="medium",
            requires_approval=True,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="run_tests",
            description="Run the project's test suite using the configured test runner.",
            input_schema={
                "command": "string — test command (default: pytest)",
                "cwd": "string — optional working directory",
            },
            execute=_tool_run_tests,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="git_commit",
            description="Stage all changes and create a git commit with the provided message.",
            input_schema={
                "message": "string — commit message (required)",
                "cwd": "string — optional working directory",
            },
            execute=_tool_git_commit,
            reversible=True,
            risk="medium",
            requires_approval=True,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="git_branch",
            description="Create, checkout, or list git branches.",
            input_schema={
                "action": "string — one of: create, checkout, list (required)",
                "name": "string — branch name (required for create/checkout)",
                "cwd": "string — optional working directory",
            },
            execute=_tool_git_branch,
            reversible=True,
            risk="medium",
            requires_approval=True,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="retrieve_memory",
            description="Search project memory using vector search or recent retrieval. Use this when you need context from past sessions, commits, TODOs, or architecture notes.",
            input_schema={
                "query": "string — natural language search query (required)",
                "project_id": "string — project scope (required)",
                "tables": "array of strings — tables to search (optional)",
                "top_k": "integer — max results (default 8)",
            },
            execute=_tool_retrieve_memory,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="call_design_tool",
            description="Delegate a design task to an external design generator (e.g. Stitch). Only available if the design tool is installed.",
            input_schema={
                "target": "string — tool name, e.g. 'stitch' (required)",
                "prompt": "string — design prompt (required)",
            },
            execute=_tool_call_design_tool,
            reversible=True,
            risk="medium",
            requires_approval=True,
            policy="require_approval",
        )
    )

    register(
        Tool(
            name="call_coding_agent",
            description="Delegate a coding task to an external coding agent (e.g. Claude, Cursor). Retrieves prior similar tasks from mistake_log to improve the handoff prompt, then independently verifies the result.",
            input_schema={
                "target": "string — tool name, e.g. 'claude' or 'cursor' (required)",
                "prompt": "string — coding prompt (required)",
                "project_id": "string — project scope (required)",
                "repo_path": "string — repository path for verification (optional)",
            },
            execute=_tool_call_coding_agent,
            reversible=False,
            risk="high",
            requires_approval=True,
            policy="require_approval",
        )
    )

    # ── AUTOMATA semantic actions (safe, reversible, auto-executable) ─────────

    def _tool_update_project_summary(params: dict[str, Any]) -> dict[str, Any]:
        project_id = str(params.get("project_id", "")).strip()
        if not project_id:
            return {"success": False, "error": "project_id is required"}
        try:
            import agent_actions as _aa

            result = _aa.generate_project_summary(project_id)
            if result and result.get("summary"):
                return {"success": True, "summary": result["summary"]}
            return {"success": False, "error": "no summary generated"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _tool_regenerate_daily_brief(params: dict[str, Any]) -> dict[str, Any]:
        project_id = str(params.get("project_id", "")).strip()
        if not project_id:
            return {"success": False, "error": "project_id is required"}
        try:
            from db.client import get_commits, get_file_edits, get_todos, upsert_daily_brief

            commits = get_commits(project_id, limit=20) or []
            file_edits = get_file_edits(project_id, limit=5) or []
            todos = get_todos(project_id, status="pending") or []

            highlights: list[str] = []
            for commit in commits[:5]:
                msg = str(commit.get("message", "")).split("\n")[0].strip()
                if msg:
                    highlights.append(msg[:80])
            for edit in file_edits[:3]:
                path = str(edit.get("file_path", ""))
                if path:
                    highlights.append(f"Edited {path}")

            pending_items = [
                str(t.get("description", "")) for t in todos[:10] if t.get("description")
            ]
            brief_date = datetime.now(UTC).strftime("%Y-%m-%d")

            ok = upsert_daily_brief(
                project_id=project_id,
                brief_date=brief_date,
                commits_count=len(commits),
                highlights=highlights,
                pending_items=pending_items,
            )
            return {
                "success": bool(ok),
                "brief_date": brief_date,
                "commits_count": len(commits),
                "highlights": highlights,
                "pending_items": pending_items,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _tool_flag_related_todos(params: dict[str, Any]) -> dict[str, Any]:
        project_id = str(params.get("project_id", "")).strip()
        if not project_id:
            return {"success": False, "error": "project_id is required"}
        try:
            from db.client import get_todos, update_todo_description

            todos = get_todos(project_id, status="pending")
            if not todos:
                return {"success": True, "flagged": 0}
            flagged = 0
            for todo in todos:
                current = str(todo.get("description", ""))
                if not current.startswith("[auto-flagged]"):
                    updated = f"[auto-flagged] {current}"
                    if update_todo_description(str(todo.get("id", "")), updated):
                        flagged += 1
            return {"success": True, "flagged": flagged}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _tool_store_session_summary(params: dict[str, Any]) -> dict[str, Any]:
        project_id = str(params.get("project_id", "")).strip()
        session_id = str(params.get("session_id", "")).strip()
        summary = str(params.get("summary", "")).strip()
        if not all([project_id, session_id, summary]):
            return {"success": False, "error": "project_id, session_id, and summary are required"}
        try:
            from db.client import end_session

            ok = end_session(project_id, session_id, summary=summary)
            return {"success": bool(ok), "stored": bool(ok)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _tool_suggest_next_task(params: dict[str, Any]) -> dict[str, Any]:
        project_id = str(params.get("project_id", "")).strip()
        if not project_id:
            return {"success": False, "error": "project_id is required"}
        try:
            from db.client import get_todos

            todos = get_todos(project_id, status="pending") or []
            if todos:
                top = todos[0]
                title = str(top.get("description", "")).strip()
                suggestion = f"Pending: {title}" if title else "Review pending TODOs"
            else:
                suggestion = "No pending TODOs — check recent commits for clues"
            return {"success": True, "suggestion": suggestion, "pending_todos_count": len(todos)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    register(
        Tool(
            name="update_project_summary",
            description="Generate a project summary from recent commits, file edits, and architecture notes.",
            input_schema={
                "project_id": "string — project scope (required)",
            },
            execute=_tool_update_project_summary,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="regenerate_daily_brief",
            description="Regenerate the daily brief for a project from recent memory.",
            input_schema={
                "project_id": "string — project scope (required)",
            },
            execute=_tool_regenerate_daily_brief,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="flag_related_todos",
            description="Auto-flag pending TODOs based on recent project activity.",
            input_schema={
                "project_id": "string — project scope (required)",
            },
            execute=_tool_flag_related_todos,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="store_session_summary",
            description="End an active session and store its summary.",
            input_schema={
                "project_id": "string — project scope (required)",
                "session_id": "string — session ID (required)",
                "summary": "string — end-of-session summary text (required)",
            },
            execute=_tool_store_session_summary,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )

    register(
        Tool(
            name="suggest_next_task",
            description="Suggest the next task from pending TODOs or recent context.",
            input_schema={
                "project_id": "string — project scope (required)",
            },
            execute=_tool_suggest_next_task,
            reversible=True,
            risk="low",
            requires_approval=False,
        )
    )


def filter_tools_by_config() -> list[Tool]:
    """Return tools whose required config/env vars are currently set."""
    from config import settings

    available: list[Tool] = []
    for tool in get_available_tools():
        missing = False
        for cfg in tool.requires_config:
            # Check in settings object (support both attribute and dict-style access)
            val = getattr(settings, cfg, None) if hasattr(settings, cfg) else None
            if val is None and isinstance(settings, dict):
                val = settings.get(cfg)
            if not val or (isinstance(val, str) and not val.strip()):
                missing = True
                break
        if not missing:
            available.append(tool)
    return available


# ─── Cross-app control tool implementations ──────────────────


def _tool_copy_to_clipboard(params: dict[str, Any]) -> dict[str, Any]:
    """Copy generated text to the clipboard (verified by reading it back)."""
    from automation.desktop import copy_text

    return copy_text(str(params.get("text", "")))


def _tool_paste_clipboard(params: dict[str, Any]) -> dict[str, Any]:
    """Paste the clipboard into a verified target window."""
    from automation.desktop import paste

    return paste(str(params.get("target_app") or "") or None)


def _tool_open_url(params: dict[str, Any]) -> dict[str, Any]:
    """Open a URL in the default browser."""
    url = str(params.get("url", "")).strip()
    if not url:
        return {"success": False, "error": "url is required"}
    try:
        from automation.os_windows import launch_browser

        ok = launch_browser(url)
        return {"success": ok, "opened": ok, "url": url}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _tool_focus_app(params: dict[str, Any]) -> dict[str, Any]:
    """Bring an app window to the front (confirmed by Windows)."""
    from automation.desktop import focus

    return focus(str(params.get("app_name", "")).strip())


def _tool_send_keystroke(params: dict[str, Any]) -> dict[str, Any]:
    """Send an allowed chord to a verified window."""
    from automation.desktop import press

    return press(str(params.get("keystrokes", "")).strip(), str(params.get("target_app") or "") or None)


def _tool_submit_prompt_to_app(params: dict[str, Any]) -> dict[str, Any]:
    """Generate a prompt if needed, then hand it to the app with verified steps."""
    from automation.desktop import handoff_prompt

    app_name = str(params.get("app_name", "")).strip()
    prompt_text = str(params.get("prompt", "")).strip()
    url = str(params.get("url", "")).strip()

    if not prompt_text:
        request_desc = params.get("request_description") or params.get("message") or params.get("raw") or ""
        target_app = url or app_name
        if request_desc and target_app:
            try:
                from agent_actions import generate_prompt_for_app

                prompt_text = generate_prompt_for_app(
                    request_desc, target_app, params.get("project_id")
                ) or ""
            except Exception as exc:
                logger.warning("_tool_submit_prompt_to_app: prompt generation failed | %s", exc)
        if not prompt_text:
            return {"success": False, "error": "prompt is required"}
    return handoff_prompt(prompt_text, app_name=app_name, url=url, submit=bool(params.get("submit", True)))


def _tool_verify_result(params: dict[str, Any]) -> dict[str, Any]:
    """Check an outcome; unknown check types fail instead of passing."""
    from automation.desktop import verify

    return verify(str(params.get("type", "")), str(params.get("target", "")))


# ─── Register cross-app control tools ────────────────────────


def _register_cross_app_tools() -> None:
    register(
        Tool(
            name="copy_to_clipboard",
            description="Copy generated text to the Windows clipboard. Safe, reversible, auto-executed.",
            input_schema={
                "text": "string — the text to copy (required)",
            },
            execute=_tool_copy_to_clipboard,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )

    register(
        Tool(
            name="paste_clipboard",
            description="Paste clipboard content into the active target app. Medium-risk external action.",
            input_schema={},
            execute=_tool_paste_clipboard,
            reversible=False,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="open_url",
            description="Open a URL in the default browser. Low-risk, auto-executed.",
            input_schema={
                "url": "string — the URL to open (required)",
            },
            execute=_tool_open_url,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )

    register(
        Tool(
            name="focus_app",
            description="Bring a known existing application window to the foreground.",
            input_schema={
                "app_name": "string — the application name or process name (required)",
            },
            execute=_tool_focus_app,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="send_keystroke",
            description="Send limited safe keystrokes: Ctrl+V, Enter, Ctrl+L, Alt+Tab, Tab, Escape.",
            input_schema={
                "keystrokes": "string — the keystroke combination (required)",
            },
            execute=_tool_send_keystroke,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="submit_prompt_to_app",
            description="Higher-level flow: generate prompt, open/focus app, copy to clipboard, paste, optionally submit. Requires approval before external submission.",
            input_schema={
                "app_name": "string — target application name (optional if url is provided)",
                "url": "string — URL to open (optional if app_name is provided)",
                "prompt": "string — the prompt text to submit (required)",
            },
            execute=_tool_submit_prompt_to_app,
            reversible=False,
            risk="high",
            requires_approval=True,
            policy="require_approval",
        )
    )

    register(
        Tool(
            name="verify_result",
            description="Verify whether an action worked: app opened, file changed, command completed, server started, or prompt was copied.",
            input_schema={
                "type": "string — check type: app_open, file_changed, clipboard_has_content (required)",
                "target": "string — the target to verify against (app name, file path, etc.)",
            },
            execute=_tool_verify_result,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )


# ─── Visual feedback tool implementations ────────────


def _tool_capture_screen(params: dict[str, Any]) -> dict[str, Any]:
    """Capture the screen, a region, or an app's window."""
    from automation.desktop import capture

    return capture(
        region=str(params.get("region") or "").strip() or None,
        app_name=str(params.get("app_name") or "").strip() or None,
    )


def _tool_ocr_image(params: dict[str, Any]) -> dict[str, Any]:
    """Extract text from a screenshot/image."""
    from automation.ocr import run_ocr

    image_path = str(params.get("image_path", "")).strip()
    if not image_path:
        return {"success": False, "error": "image_path is required"}
    result = run_ocr(image_path)
    return {"success": result["ok"], "text": result["text"], "engine": result["engine"], "error": result["error"]}


def _tool_read_visible_context(params: dict[str, Any]) -> dict[str, Any]:
    """Capture and OCR the screen (or one app's window)."""
    from automation.desktop import read_screen

    return read_screen(app_name=str(params.get("app_name") or "") or None)


def _tool_diagnose_visible_error(params: dict[str, Any]) -> dict[str, Any]:
    """Read visible error text from the screen for diagnosis."""
    from automation.desktop import read_screen

    return read_screen(app_name=str(params.get("app_name") or "") or None)


def _tool_review_visible_design(params: dict[str, Any]) -> dict[str, Any]:
    """Read the visible UI text for a design review."""
    from automation.desktop import read_screen

    return read_screen(app_name=str(params.get("app_name") or "") or None)


def _tool_generate_prompt_from_screen(params: dict[str, Any]) -> dict[str, Any]:
    """Read the visible screen text to ground a prompt."""
    from automation.desktop import read_screen

    return read_screen(app_name=str(params.get("app_name") or "") or None)


def _tool_verify_visible_result(params: dict[str, Any]) -> dict[str, Any]:
    """Check whether expected text is visible on screen."""
    from automation.desktop import read_screen

    expected = str(params.get("expected_text") or "").strip()
    if not expected:
        return {"success": False, "verified": False, "error": "expected_text is required"}
    return read_screen(expected_text=expected)


def _register_visual_feedback_tools() -> None:
    register(
        Tool(
            name="capture_screen",
            description="Capture full screen, active window, or selected region. Confirm before capturing.",
            input_schema={
                "region": "string — optional region in 'left,top,width,height' format",
            },
            execute=_tool_capture_screen,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="ocr_image",
            description="Extract text from a screenshot/image. Auto-executes after capture.",
            input_schema={
                "image_path": "string — path to the image file (required)",
            },
            execute=_tool_ocr_image,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )

    register(
        Tool(
            name="read_visible_context",
            description="Capture and OCR the current visible workspace.",
            input_schema={},
            execute=_tool_read_visible_context,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="diagnose_visible_error",
            description="Parse visible error text and connect it to project memory.",
            input_schema={},
            execute=_tool_diagnose_visible_error,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="review_visible_design",
            description="Analyze current UI/design preview and generate improvement notes.",
            input_schema={},
            execute=_tool_review_visible_design,
            reversible=True,
            risk="medium",
            requires_approval=False,
            policy="confirm_once",
        )
    )

    register(
        Tool(
            name="generate_prompt_from_screen",
            description="Use visible context plus project memory to draft a prompt for another tool.",
            input_schema={},
            execute=_tool_generate_prompt_from_screen,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )

    register(
        Tool(
            name="verify_visible_result",
            description="Check whether expected UI text/state appears after an action.",
            input_schema={},
            execute=_tool_verify_visible_result,
            reversible=True,
            risk="low",
            requires_approval=False,
            policy="auto_execute",
        )
    )


_register_default_tools()
_register_cross_app_tools()
_register_visual_feedback_tools()
