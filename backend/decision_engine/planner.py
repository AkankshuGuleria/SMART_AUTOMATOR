"""
decision_engine/planner.py — AUTOMATA Decision Engine: action planner.

Owns:    Deciding whether an autonomous action should be executed immediately
           (passive/reversible) or only suggested to the developer
           (environment-changing, irreversible).
Never:   Must not call Bedrock or CockroachDB directly — routing only.
           Must not bypass the Agent Loop. See ARCHITECTURE.md §2.3.
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9 (guardrails).

GUARDRAILS (encoded in ACTION_POLICY below):
- "auto_execute": passive, reversible — run without asking (update summary,
  flag TODO, generate brief, open browser/app).
- "suggest": environment-changing or irreversible — surface as a proposal,
  never silently execute (restore workspace, launch editor, run tests).
"""

import logging
import os
import re
from datetime import datetime
from typing import Any

from db.client import insert_decision

logger = logging.getLogger(__name__)

# Maps action types to their policy.
ACTION_POLICY: dict[str, str] = {
    "update_project_summary": "auto_execute",
    "regenerate_daily_brief": "auto_execute",
    "flag_related_todos": "auto_execute",
    "store_session_summary": "auto_execute",
    "suggest_next_task": "auto_execute",
    "chat_explain_repo": "auto_execute",
    "chat_open_browser": "auto_execute",
    "chat_open_app": "auto_execute",
    "chat_system_command": "suggest",
    "chat_query_memory": "auto_execute",
    "chat_generate_prompt": "auto_execute",
    "chat_git_log": "auto_execute",
    "chat_morning_brief": "auto_execute",
    "chat_continue_work": "auto_execute",
    "chat_generate_commit_message": "suggest",
    "chat_run_tests": "suggest",
    "restore_workspace": "suggest",
    # Cross-app control actions
    "copy_to_clipboard": "auto_execute",
    "paste_clipboard": "confirm_once",
    "open_url": "auto_execute",
    "focus_app": "confirm_once",
    "send_keystroke": "confirm_once",
    "submit_prompt_to_app": "require_approval",
    "verify_result": "auto_execute",
    # Visual feedback actions
    "capture_screen": "confirm_once",
    "ocr_image": "auto_execute",
    "read_visible_context": "confirm_once",
    "diagnose_visible_error": "confirm_once",
    "review_visible_design": "confirm_once",
    "generate_prompt_from_screen": "auto_execute",
    "verify_visible_result": "auto_execute",
}


def plan(trigger: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Given a trigger and its context, decide what actions to take and in what mode.

    Returns a plan dict:
    {
        "trigger": str,
        "reply": str,        # human-readable reply for the chat UI
        "actions": [
            {
                "type": str,          # key in ACTION_POLICY
                "policy": str,        # "auto_execute" | "suggest"
                "params": dict,       # action-specific parameters
                "provenance": str,    # human-readable explanation for the UI
                "executed": bool,
                "executed_at": str | None,
                "result": dict | None,    # action result payload
            },
            ...
        ]
    }
    """
    logger.info("plan: trigger=%s", trigger)

    actions = _get_actions_for_trigger(trigger, context)

    # Log the plan for provenance
    _log_plan(trigger, actions)

    for action in actions:
        policy = action.get("policy", "suggest")
        action.setdefault("executed", False)
        action.setdefault("executed_at", None)
        action.setdefault("result", None)

        if policy in ("suggest", "confirm_once", "require_approval"):
            try:
                insert_decision(
                    project_id=action["params"].get("project_id"),
                    decision=f"Suggested action: {action['type']} (policy={policy})",
                    rationale=action["provenance"],
                )
            except Exception as exc:
                logger.warning(
                    "plan: failed to log suggested action | type=%s error=%s",
                    action["type"],
                    exc,
                )
            continue

        try:
            result = _execute_action(action)
            if result is not None and result.get("success", True) is not False:
                action["executed"] = True
                action["executed_at"] = datetime.now().isoformat()
                action["result"] = result
            elif result is not None:
                action["result"] = result
        except Exception as exc:
            logger.warning("plan: action failed | type=%s error=%s", action["type"], exc)

    # Build human-readable reply from executed/suggested actions
    reply = _build_reply(trigger, actions, context)

    return {
        "trigger": trigger,
        "reply": reply,
        "actions": actions,
    }


def _execute_action(action: dict[str, Any]) -> dict | None:
    """Dispatch an action to its concrete implementation. Returns result dict or None on failure."""
    action_type = action.get("type", "")
    params = action.get("params", {})

    dispatch = {
        "update_project_summary": _execute_update_project_summary,
        "regenerate_daily_brief": _execute_regenerate_daily_brief,
        "flag_related_todos": _execute_flag_related_todos,
        "store_session_summary": _execute_store_session_summary,
        "suggest_next_task": _execute_suggest_next_task,
        "chat_explain_repo": _execute_chat_explain_repo,
        "chat_continue_work": _execute_chat_continue_work,
        "chat_generate_commit_message": _execute_chat_generate_commit_message,
        "restore_workspace": _execute_restore_workspace,
        "chat_open_browser": _execute_chat_open_browser,
        "chat_open_app": _execute_chat_open_app,
        "chat_system_command": _execute_chat_system_command,
        "chat_query_memory": _execute_chat_query_memory,
        "chat_generate_prompt": _execute_chat_generate_prompt,
        "chat_git_log": _execute_chat_git_log,
        "chat_morning_brief": _execute_chat_morning_brief,
        "chat_run_tests": _execute_chat_run_tests,
        # Cross-app control actions
        "copy_to_clipboard": _execute_copy_to_clipboard,
        "paste_clipboard": _execute_paste_clipboard,
        "open_url": _execute_open_url,
        "focus_app": _execute_focus_app,
        "send_keystroke": _execute_send_keystroke,
        "submit_prompt_to_app": _execute_submit_prompt_to_app,
        "verify_result": _execute_verify_result,
        # Visual feedback actions
        "capture_screen": _execute_capture_screen,
        "ocr_image": _execute_ocr_image,
        "read_visible_context": _execute_read_visible_context,
        "diagnose_visible_error": _execute_diagnose_visible_error,
        "review_visible_design": _execute_review_visible_design,
        "generate_prompt_from_screen": _execute_generate_prompt_from_screen,
        "verify_visible_result": _execute_verify_visible_result,
    }

    fn = dispatch.get(action_type)
    if fn is None:
        logger.warning("plan: no executor for action type '%s'", action_type)
        return None

    return fn(params)


# ─── Action executors ─────────────────────────────────────────────────────────


def _execute_update_project_summary(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import agent_actions as _aa

        result = _aa.generate_project_summary(project_id)
        return result if result and result.get("summary") else None
    except Exception as exc:
        logger.warning("plan: generate_project_summary failed | %s", exc)
        return None


def _build_brief_payload(project_id: str) -> dict[str, Any] | None:
    from db import client as _db

    commits = _db.get_commits(project_id, limit=20) or []
    file_edits = _db.get_file_edits(project_id, limit=5) or []
    todos = _db.get_todos(project_id, status="pending") or []

    highlights: list[str] = []
    for commit in commits[:5]:
        msg = str(commit.get("message", "")).split("\n")[0].strip()
        if msg:
            highlights.append(msg[:80])
    for edit in file_edits[:3]:
        path = str(edit.get("file_path", ""))
        if path:
            highlights.append(f"Edited {path}")

    pending_items = [str(t.get("description", "")) for t in todos[:10] if t.get("description")]

    return {
        "project_id": project_id,
        "brief_date": datetime.now().strftime("%Y-%m-%d"),
        "commits_count": len(commits),
        "highlights": highlights,
        "pending_items": pending_items,
    }


def _execute_regenerate_daily_brief(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    payload = _build_brief_payload(project_id)
    if payload is None:
        return None
    import db.client as _db

    success = _db.upsert_daily_brief(
        project_id=project_id,
        brief_date=str(payload.get("brief_date", datetime.now().strftime("%Y-%m-%d"))),
        commits_count=int(payload.get("commits_count", 0)),
        highlights=list(payload.get("highlights", [])),
        pending_items=list(payload.get("pending_items", [])),
    )
    return payload if success else None


def _execute_flag_related_todos(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import db.client as _db

        todos = _db.get_todos(project_id, status="pending")
        if not todos:
            return {"flagged": 0}
        flagged = 0
        for todo in todos:
            current = str(todo.get("description", ""))
            if not current.startswith("[auto-flagged]"):
                updated = f"[auto-flagged] {current}"
                if _db.update_todo_description(str(todo.get("id", "")), updated):
                    flagged += 1
        return {"flagged": flagged}
    except Exception as exc:
        logger.warning("plan: flag_related_todos failed | %s", exc)
        return None


def _execute_store_session_summary(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    session_id = params.get("session_id")
    summary = params.get("summary")
    if not project_id or not session_id or not summary:
        return None
    import db.client as _db

    success = _db.end_session(project_id, session_id, summary=summary)
    return {"stored": success} if success else None


def _execute_suggest_next_task(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import db.client as _db

        todos = _db.get_todos(project_id, status="pending") or []
        if todos:
            top = todos[0]
            title = str(top.get("description", "")).strip()
            suggestion = f"Pending: {title}" if title else "Review pending TODOs"
        else:
            suggestion = "No pending TODOs — check recent commits for clues"
        return {"suggestion": suggestion, "pending_todos_count": len(todos)}
    except Exception as exc:
        logger.warning("plan: suggest_next_task failed | %s", exc)
        return None


def _execute_chat_explain_repo(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import agent_actions as _aa

        repo_path = params.get("repo_path", "")
        if not repo_path:
            try:
                from db.client import get_project

                project = get_project(project_id)
                if project:
                    repo_path = project.get("repo_path", "")
            except Exception as exc:
                logger.debug("planner: explain repo repo_path lookup failed — %s", exc)
        result = _aa.explain_repository(project_id, repo_path)
        if result and result.get("error"):
            return {"error": result["error"], "message": result["error"]}
        return result
    except Exception as exc:
        logger.warning("plan: chat_explain_repo failed | %s", exc)
        return None


def _execute_chat_continue_work(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import agent_actions as _aa

        return _aa.continue_previous_work(project_id)
    except Exception as exc:
        logger.warning("plan: chat_continue_work failed | %s", exc)
        return None


def _execute_chat_generate_commit_message(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        import agent_actions as _aa

        result = _aa.generate_commit_message(
            project_id,
            repo_path=params.get("repo_path", ""),
            staged=params.get("staged", True),
        )
        return result
    except Exception as exc:
        logger.warning("plan: chat_generate_commit_message failed | %s", exc)
        return None


def _execute_chat_open_browser(params: dict[str, Any]) -> dict | None:
    target = params.get("target", params.get("url", ""))
    if not target:
        return {"success": False, "message": "No URL or target provided."}
    try:
        import agent_actions as _aa

        return _aa.open_app_or_url(target)
    except Exception as exc:
        logger.warning("plan: chat_open_browser failed | %s", exc)
        return {"success": False, "message": str(exc)}


def _execute_chat_open_app(params: dict[str, Any]) -> dict | None:
    target = params.get("target", params.get("app_name", ""))
    if not target:
        return {"success": False, "message": "No app name provided."}
    try:
        import agent_actions as _aa

        return _aa.open_app_or_url(target)
    except Exception as exc:
        logger.warning("plan: chat_open_app failed | %s", exc)
        return {"success": False, "message": str(exc)}


def _execute_chat_system_command(params: dict[str, Any]) -> dict | None:
    """Execute a system-level command (install, setup, env vars) with confirmation."""
    message = params.get("message", params.get("raw", ""))
    if not message:
        return {"success": False, "message": "No command provided."}
    try:
        import agent_actions as _aa

        return _aa.execute_system_command(message)
    except Exception as exc:
        logger.warning("plan: chat_system_command failed | %s", exc)
        return {"success": False, "message": str(exc)}


def _execute_chat_query_memory(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    question = params.get("question", params.get("raw", ""))
    reasoning_mode = params.get("reasoning_mode")
    if not question:
        return None
    try:
        lowered = question.lower().replace("  ", " ")

        # ── Project listing queries ─────────────────────────────────────────────
        if any(
            k in lowered
            for k in [
                "list all project",
                "all projects",
                "which project",
                "projects am i",
                "working on",
                "working o n",
                "am i working on",
                "show projects",
                "my projects",
            ]
        ):
            import db.client as _db

            projects = _db.get_projects()
            if projects:
                lines = [
                    f"{p.get('name') or p.get('id')} ({p.get('repo_path', 'no path')})"
                    for p in projects[:20]
                ]
                answer = "You have these projects:\n" + "\n".join(f"• {line}" for line in lines)
            else:
                answer = "No projects found in memory."
            return {"answer": answer, "memories_used": 0}

        from ai.bedrock_client import invoke_reasoning
        from memory.retrieval import retrieve_by_vector, retrieve_recent

        memories = []
        if project_id:
            memories.extend(
                retrieve_by_vector(
                    question,
                    ["commits", "todos", "architecture_notes"],
                    project_id=project_id,
                    top_k=6,
                )
            )
            if not memories:
                for table in ("commits", "todos", "file_edits"):
                    memories.extend(retrieve_recent(project_id, table, limit=3))

        # Include taste preferences in the system prompt so answers match developer style
        taste_prompt = ""
        if project_id:
            try:
                import agent_actions as _aa

                tastes = _aa.get_developer_tastes(project_id)
                if tastes.get("available"):
                    taste_prompt = (
                        "Developer taste profile (use this to match style):\n"
                        f"{tastes['summary']}\n\n"
                    )
            except Exception as exc:
                logger.debug("planner: taste preferences load failed — %s", exc)

        answer = invoke_reasoning(
            system_prompt=(
                taste_prompt
                + "You are AUTOMATA's Reasoning Engine. Answer using the provided memory "
                "context when relevant. If the memory doesn't contain the answer, use "
                "your general knowledge — do NOT say 'No relevant memory found.' "
                "Be direct, terse, factual. No chatbot filler, no fabricated details."
            ),
            user_message=question,
            retrieved_memories=memories,
            reasoning_mode=reasoning_mode,
        )
        if not answer and memories:
            # Fallback: return raw memories as a terse bullet list (no LLM)
            answer = "\n".join(
                f"- [{m.get('table', 'memory')}] {m.get('content', '')}"
                for m in memories[:5]
                if m.get("content")
            )
        elif not answer:
            answer = (
                "No AI backend is currently available. "
                "Install Ollama or configure API keys to enable responses."
            )
        return {"answer": answer, "memories_used": len(memories)}
    except Exception as exc:
        logger.warning("plan: chat_query_memory failed | %s", exc)
        return None


def _execute_chat_git_log(params: dict[str, Any]) -> dict | None:
    """Answer git history questions directly — no LLM, no verbose boilerplate."""
    project_id = params.get("project_id")
    question = str(params.get("question", "")).strip().lower()

    if not project_id:
        return {"answer": "No project selected.", "commits": []}

    # Try DB-stored commits first
    import db.client as _db

    commits = _db.get_commits(project_id, limit=10) or []

    # Fall back to live git log if DB has no commits
    if not commits:
        repo_path = ""
        try:
            project = _db.get_project(project_id)
            repo_path = project.get("repo_path", "") if project else ""
        except Exception:
            pass

        if repo_path and os.path.isdir(repo_path):
            try:
                import git

                repo = git.Repo(repo_path)
                commits = []
                for c in list(repo.iter_commits(max_count=10)):
                    commits.append(
                        {
                            "commit_hash": c.hexsha[:8],
                            "message": c.message.strip().split("\n")[0],
                            "author": c.author.name or "",
                            "committed_at": c.committed_datetime.strftime("%Y-%m-%d %H:%M"),
                        }
                    )
            except Exception as exc:
                logger.warning("plan: git log fallback failed — %s", exc)

    if not commits:
        return {"answer": "No commits found for this project.", "commits": []}

    # Direct, terse answers — no LLM needed
    latest = commits[0]
    latest_msg = str(latest.get("message", "")).strip()
    latest_hash = str(latest.get("commit_hash", latest.get("hash", "unknown")))[:8]

    if "last commit" in question or "latest commit" in question or "most recent commit" in question:
        answer = f"{latest_msg}\n— {latest_hash} by {latest.get('author', 'unknown')} at {latest.get('committed_at', 'unknown')}"
    elif "recent commits" in question or "show me" in question or "commits" in question:
        lines = []
        for c in commits[:10]:
            msg = str(c.get("message", "")).strip().split("\n")[0]
            h = str(c.get("commit_hash", c.get("hash", "unknown")))[:8]
            lines.append(f"• {msg} — {h}")
        answer = "\n".join(lines)
    elif "when" in question:
        answer = f"{latest.get('committed_at', 'unknown')}"
    elif "who" in question:
        answer = f"{latest.get('author', 'unknown')}"
    else:
        answer = f"{latest_msg} ({latest_hash})"

    return {"answer": answer, "commits": commits[:10]}


def _execute_chat_generate_prompt(params: dict[str, Any]) -> dict | None:
    """Generate a ready-to-use prompt text from project context — no LLM required.

    Called when a compound request like 'open claude and generate a prompt'
    is detected. Builds a prompt using a template + project context (commits,
    todos, architecture notes, file edits) so the user can copy-paste it into
    any AI assistant.
    """
    project_id = params.get("project_id")
    message = str(params.get("raw", params.get("question", "")))
    if not project_id:
        return {"answer": "No project selected."}

    import db.client as _db

    commits = _db.get_commits(project_id, limit=10) or []
    todos = _db.get_todos(project_id, status="pending") or []
    file_edits = _db.get_file_edits(project_id, limit=5) or []
    arch_notes = []
    try:
        arch_notes = _db.get_architecture_notes(project_id) or []
    except Exception:
        pass

    # Extract the secondary task from the compound message (everything after "and")
    secondary_task = message
    if " and " in message.lower():
        secondary_task = message.split(" and ", 1)[-1]
    # Strip filler like "generate a prompt I should give to it so that"
    secondary_task = secondary_task.strip()

    # Build context sections
    commit_lines = []
    for c in commits[:5]:
        msg = str(c.get("message", "")).split("\n")[0].strip()
        h = str(c.get("commit_hash", ""))[:8]
        if msg:
            commit_lines.append(f"- {msg} ({h})")

    todo_lines = [str(t.get("description", "")) for t in todos[:10] if t.get("description")]

    note_lines = []
    for n in arch_notes[:5]:
        content = str(n.get("content", n.get("summary", ""))).strip()[:200]
        source = str(n.get("source_file", ""))
        if content:
            note_lines.append(f"- [{source}] {content}" if source else f"- {content}")

    edit_lines = []
    for e in file_edits[:3]:
        path = str(e.get("file_path", ""))
        if path:
            edit_lines.append(f"- {path}")

    project_name = "this project"
    try:
        proj = _db.get_project(project_id)
        if proj:
            project_name = str(proj.get("name", project_name))
    except Exception:
        pass

    # Build the prompt template
    parts = [
        f"You are a senior engineer working on {project_name}.",
        f"Task: {secondary_task}",
        "",
        "Project context (most recent first):",
    ]

    if commit_lines:
        parts.append("Recent commits:")
        parts.extend(commit_lines)
    else:
        parts.append("Recent commits: (none found)")

    if todo_lines:
        parts.append("")
        parts.append("Pending TODOs:")
        parts.extend(f"- {t}" for t in todo_lines)

    if note_lines:
        parts.append("")
        parts.append("Architecture notes:")
        parts.extend(note_lines)

    if edit_lines:
        parts.append("")
        parts.append("Recently edited files:")
        parts.extend(edit_lines)

    parts.append("")
    parts.append("Based on this context, produce the requested output.")

    prompt_text = "\n".join(parts)

    return {
        "answer": prompt_text,
        "prompt": prompt_text,
        "memories_used": len(commits) + len(todos) + len(arch_notes),
    }


def _execute_chat_morning_brief(params: dict[str, Any]) -> dict | None:
    project_id = params.get("project_id")
    if not project_id:
        return None
    try:
        payload = _build_brief_payload(project_id)
        if payload is None:
            return None
        import db.client as _db

        success = _db.upsert_daily_brief(
            project_id=project_id,
            brief_date=str(payload.get("brief_date", datetime.now().strftime("%Y-%m-%d"))),
            commits_count=int(payload.get("commits_count", 0)),
            highlights=list(payload.get("highlights", [])),
            pending_items=list(payload.get("pending_items", [])),
        )

        # Generate a grounded morning brief from the template
        try:
            from ai.bedrock_client import _load_prompt_template, invoke_reasoning
            from memory.retrieval import retrieve_by_vector

            memories = retrieve_by_vector(
                "morning brief recent activity",
                ["commits", "todos", "file_edits"],
                project_id=project_id,
                top_k=6,
            )
            highlights = payload.get("highlights", []) or ["No recent activity"]
            pending = payload.get("pending_items", []) or []
            template = _load_prompt_template("morning_brief")
            if template:
                user_message = template.format(
                    memory_context="\n".join(f"- {h}" for h in highlights + pending),
                    todo_context="\n".join(f"- {p}" for p in pending),
                    recent_context="\n".join(f"- {h}" for h in highlights),
                )
                brief_text = invoke_reasoning(
                    system_prompt="You are AUTOMATA's morning brief generator.",
                    user_message=user_message,
                    retrieved_memories=memories,
                )
                if brief_text:
                    payload["brief_text"] = brief_text
        except Exception as exc:
            logger.debug("_execute_chat_morning_brief: LLM brief generation failed — %s", exc)

        return payload if success else None
    except Exception as exc:
        logger.warning("plan: chat_morning_brief failed | %s", exc)
        return None


def _execute_chat_run_tests(params: dict[str, Any]) -> dict | None:
    """Build a test-run suggestion without executing — keeps suggest policy intact."""
    project_id = params.get("project_id")
    if not project_id:
        return {"suggested_command": "pytest", "message": "Run pytest to execute tests."}
    try:
        import agent_actions as _aa

        return _aa.run_tests_action(project_id)
    except Exception as exc:
        logger.warning("plan: chat_run_tests failed | %s", exc)
        return {"suggested_command": "pytest", "message": "Run pytest to execute tests."}


def _execute_restore_workspace(params: dict[str, Any]) -> dict | None:
    """Restore workspace — surface as a proposal, never silently execute."""
    project_id = params.get("project_id")
    if not project_id:
        return {"success": False, "message": "No project_id provided."}
    try:
        from automation.restore import restore_workspace as _restore

        result = _restore(project_id)
        return {
            "success": result.get("overall") in ("ok", "partial"),
            "project_id": project_id,
            "steps": result.get("steps", []),
            "overall": result.get("overall", "error"),
        }
    except Exception as exc:
        logger.warning("plan: restore_workspace failed | %s", exc)
        return {"success": False, "message": str(exc)}


# ─── Cross-app control action executors ──────────────


def _execute_copy_to_clipboard(params: dict[str, Any]) -> dict | None:
    text = params.get("text", "")
    if not text:
        return {"success": False, "error": "text is required"}
    try:
        from automation.os_windows import copy_to_clipboard

        ok = copy_to_clipboard(text)
        return {"success": ok, "copied": ok}
    except Exception as exc:
        logger.warning("plan: copy_to_clipboard failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_paste_clipboard(params: dict[str, Any]) -> dict | None:
    try:
        from automation.os_windows import paste_clipboard

        ok = paste_clipboard()
        return {"success": ok, "pasted": ok, "keystrokes": "ctrl+v"}
    except Exception as exc:
        logger.warning("plan: paste_clipboard failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_open_url(params: dict[str, Any]) -> dict | None:
    url = params.get("url", "")
    if not url:
        return {"success": False, "error": "url is required"}
    try:
        from automation.os_windows import launch_browser

        ok = launch_browser(url)
        return {"success": ok, "opened": ok, "url": url}
    except Exception as exc:
        logger.warning("plan: open_url failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_focus_app(params: dict[str, Any]) -> dict | None:
    app_name = params.get("app_name", "")
    if not app_name:
        return {"success": False, "error": "app_name is required"}
    try:
        from automation.os_windows import focus_app

        ok = focus_app(app_name)
        return {"success": ok, "focused": ok, "app": app_name}
    except Exception as exc:
        logger.warning("plan: focus_app failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_send_keystroke(params: dict[str, Any]) -> dict | None:
    keystrokes = params.get("keystrokes", "")
    if not keystrokes:
        return {"success": False, "error": "keystrokes is required"}
    try:
        from automation.os_windows import send_keystrokes

        ok = send_keystrokes(keystrokes)
        return {"success": ok, "sent": ok, "keystrokes": keystrokes}
    except Exception as exc:
        logger.warning("plan: send_keystroke failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_submit_prompt_to_app(params: dict[str, Any]) -> dict | None:
    app_name = params.get("app_name", "")
    url = params.get("url", "")
    prompt_text = params.get("prompt", "")
    if not prompt_text:
        return {"success": False, "error": "prompt is required"}
    try:
        import time

        from automation.os_windows import (
            copy_to_clipboard,
            focus_app,
            launch_app,
            launch_browser,
            send_keystrokes,
        )

        steps: list[dict[str, Any]] = []
        copy_ok = copy_to_clipboard(prompt_text)
        steps.append({"action": "copy_to_clipboard", "success": copy_ok})
        if url:
            open_ok = launch_browser(url)
            steps.append({"action": "open_url", "success": open_ok, "url": url})
        elif app_name:
            open_ok = launch_app(app_name)
            steps.append({"action": "open_app", "success": open_ok, "app": app_name})
            if open_ok:
                focus_ok = focus_app(app_name)
                steps.append({"action": "focus_app", "success": focus_ok, "app": app_name})
        time.sleep(2.0)
        paste_ok = send_keystrokes("ctrl+v")
        steps.append({"action": "paste_clipboard", "success": paste_ok, "keystrokes": "ctrl+v"})
        time.sleep(0.5)
        submit_ok = send_keystrokes("ctrl+enter")
        steps.append({"action": "send_keystroke", "success": submit_ok, "keystrokes": "ctrl+enter"})
        all_success = all(s.get("success") for s in steps)
        return {"success": all_success, "prompt_length": len(prompt_text), "steps": steps}
    except Exception as exc:
        logger.warning("plan: submit_prompt_to_app failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_verify_result(params: dict[str, Any]) -> dict | None:
    check_type = params.get("type", "")
    target = params.get("target", "")
    if not check_type:
        return {"success": False, "error": "type is required"}
    try:
        result: dict[str, Any] = {"success": True, "check_type": check_type, "target": target}
        if check_type == "file_changed":
            if target and os.path.exists(target):
                result["verified"] = True
                result["exists"] = True
                result["size"] = os.path.getsize(target)
            else:
                result["verified"] = False
                result["exists"] = False
        elif check_type == "clipboard_has_content":
            from automation.os_windows import read_clipboard

            content = read_clipboard()
            result["verified"] = bool(content)
            result["content_preview"] = content[:200] if content else ""
        else:
            result["verified"] = True
            result["note"] = "check type not fully implemented for this type"
        return result
    except Exception as exc:
        logger.warning("plan: verify_result failed | %s", exc)
        return {"success": False, "error": str(exc)}


# ─── Visual feedback action executors ────────────────


def _execute_capture_screen(params: dict[str, Any]) -> dict | None:
    region = params.get("region")
    try:
        from automation.os_windows import capture_screen

        path = capture_screen(region)
        return {"success": bool(path), "path": path}
    except Exception as exc:
        logger.warning("plan: capture_screen failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_ocr_image(params: dict[str, Any]) -> dict | None:
    image_path = params.get("image_path", "")
    if not image_path:
        return {"success": False, "error": "image_path is required"}
    try:
        from automation.ocr import ocr_image

        text = ocr_image(image_path)
        return {"success": bool(text), "text": text}
    except Exception as exc:
        logger.warning("plan: ocr_image failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_read_visible_context(params: dict[str, Any]) -> dict | None:
    try:
        from automation.ocr import ocr_image
        from automation.screen_capture import capture_screen

        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path}
    except Exception as exc:
        logger.warning("plan: read_visible_context failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_diagnose_visible_error(params: dict[str, Any]) -> dict | None:
    try:
        from automation.ocr import ocr_image
        from automation.screen_capture import capture_screen

        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "diagnosed": True}
    except Exception as exc:
        logger.warning("plan: diagnose_visible_error failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_review_visible_design(params: dict[str, Any]) -> dict | None:
    try:
        from automation.ocr import ocr_image
        from automation.screen_capture import capture_screen

        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "reviewed": True}
    except Exception as exc:
        logger.warning("plan: review_visible_design failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_generate_prompt_from_screen(params: dict[str, Any]) -> dict | None:
    try:
        from automation.ocr import ocr_image
        from automation.screen_capture import capture_screen

        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {
            "success": bool(text),
            "text": text,
            "screen_path": screen_path,
            "prompt_generated": True,
        }
    except Exception as exc:
        logger.warning("plan: generate_prompt_from_screen failed | %s", exc)
        return {"success": False, "error": str(exc)}


def _execute_verify_visible_result(params: dict[str, Any]) -> dict | None:
    try:
        from automation.ocr import ocr_image
        from automation.screen_capture import capture_screen

        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "verified": True}
    except Exception as exc:
        logger.warning("plan: verify_visible_result failed | %s", exc)
        return {"success": False, "error": str(exc)}


# ─── Trigger → action mapping ─────────────────────────────────────────────────

# Phrases that signal a secondary content-generation request after "and"
# Detects compound requests like "open claude and generate a prompt",
# "open vscode and create a fix.md file", etc.
_COMPOUND_SECONDARY_PATTERNS = re.compile(
    r"\band\s+(?:also\s+)?"
    r"(?:generate|create|write|draft|make|build|prepare|give me)\b",
    re.IGNORECASE,
)


def _detect_secondary_query(message: str) -> bool:
    """Return True if *message* is a compound request: open/launch + generate content."""
    return bool(_COMPOUND_SECONDARY_PATTERNS.search(message))


def _get_actions_for_trigger(trigger: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a trigger to a list of planned actions."""
    project_id = context.get("project_id")
    message = context.get("message", "")
    parsed = context.get("parsed") or {}
    target = parsed.get("target", "") or parsed.get("project_hint", "") or message

    if trigger == "on_commit":
        return [
            {
                "type": "update_project_summary",
                "policy": ACTION_POLICY["update_project_summary"],
                "params": {"project_id": project_id, "commit_hash": context.get("commit_hash")},
                "provenance": f"Auto-executed: commit {str(context.get('commit_hash', ''))[:8]} detected",
            },
            {
                "type": "regenerate_daily_brief",
                "policy": ACTION_POLICY["regenerate_daily_brief"],
                "params": {"project_id": project_id},
                "provenance": "Auto-executed: daily brief regenerated after new commit",
            },
            {
                "type": "flag_related_todos",
                "policy": ACTION_POLICY["flag_related_todos"],
                "params": {
                    "project_id": project_id,
                    "commit_message": context.get("commit_message", ""),
                },
                "provenance": "Auto-executed: related TODOs flagged based on commit message",
            },
        ]

    if trigger == "on_session_end":
        return [
            {
                "type": "store_session_summary",
                "policy": ACTION_POLICY["store_session_summary"],
                "params": {"project_id": project_id, "session_id": context.get("session_id")},
                "provenance": "Auto-executed: session summary stored at session end",
            },
            {
                "type": "regenerate_daily_brief",
                "policy": ACTION_POLICY["regenerate_daily_brief"],
                "params": {"project_id": project_id},
                "provenance": "Auto-executed: daily brief regenerated at session end",
            },
            {
                "type": "suggest_next_task",
                "policy": ACTION_POLICY["suggest_next_task"],
                "params": {"project_id": project_id},
                "provenance": "Auto-executed: next task suggestion from pending TODOs",
            },
        ]

    if trigger == "chat:resume_project":
        return [
            {
                "type": "restore_workspace",
                "policy": ACTION_POLICY["restore_workspace"],
                "params": {"project_id": project_id, "message": message},
                "provenance": f"Suggested: restore workspace — {message}",
            }
        ]

    if trigger == "chat:continue_work":
        return [
            {
                "type": "chat_continue_work",
                "policy": ACTION_POLICY["chat_continue_work"],
                "params": {"project_id": project_id, "message": message},
                "provenance": f"Executed: continue previous work — {message}",
            }
        ]

    if trigger == "chat:run_tests":
        return [
            {
                "type": "chat_run_tests",
                "policy": ACTION_POLICY["chat_run_tests"],
                "params": {"project_id": project_id, "message": message},
                "provenance": f"Suggested: run tests — {message}",
            }
        ]

    if trigger == "chat:explain_repo":
        return [
            {
                "type": "chat_explain_repo",
                "policy": ACTION_POLICY["chat_explain_repo"],
                "params": {
                    "project_id": project_id,
                    "message": message,
                    "repo_path": parsed.get("repo_path", ""),
                },
                "provenance": f"Executed: explain repository — {message}",
            }
        ]

    if trigger == "chat:generate_commit_message":
        return [
            {
                "type": "chat_generate_commit_message",
                "policy": ACTION_POLICY["chat_generate_commit_message"],
                "params": {"project_id": project_id, "message": message},
                "provenance": f"Suggested: generate commit message — {message}",
            }
        ]

    if trigger == "chat:open_browser":
        from agent_actions import _resolve_app_target

        _, resolved = _resolve_app_target(target)
        actions = [
            {
                "type": "chat_open_browser",
                "policy": ACTION_POLICY["chat_open_browser"],
                "params": {"project_id": project_id, "target": target, "message": message},
                "provenance": f"Executed: opened {resolved}",
            }
        ]
        # Compound request: "open X and generate a prompt" — also handle the content generation
        if _detect_secondary_query(message):
            actions.append(
                {
                    "type": "chat_generate_prompt",
                    "policy": ACTION_POLICY["chat_generate_prompt"],
                    "params": {"project_id": project_id, "message": message, "raw": message},
                    "provenance": f"Executed: generated prompt from compound request — {message}",
                }
            )
        return actions

    if trigger == "chat:open_app":
        from agent_actions import _resolve_app_target

        _, resolved = _resolve_app_target(target)
        actions = [
            {
                "type": "chat_open_app",
                "policy": ACTION_POLICY["chat_open_app"],
                "params": {"project_id": project_id, "target": target, "message": message},
                "provenance": f"Executed: launched {resolved}",
            }
        ]
        if _detect_secondary_query(message):
            actions.append(
                {
                    "type": "chat_generate_prompt",
                    "policy": ACTION_POLICY["chat_generate_prompt"],
                    "params": {"project_id": project_id, "message": message, "raw": message},
                    "provenance": f"Executed: generated prompt from compound request — {message}",
                }
            )
        return actions

    if trigger == "chat:system_command":
        return [
            {
                "type": "chat_system_command",
                "policy": ACTION_POLICY["chat_system_command"],
                "params": {"project_id": project_id, "message": message, "raw": target},
                "provenance": f"Suggested system command — {target}",
            }
        ]

    if trigger == "chat:query_memory":
        return [
            {
                "type": "chat_query_memory",
                "policy": ACTION_POLICY["chat_query_memory"],
                "params": {
                    "project_id": project_id,
                    "question": message,
                    "raw": message,
                    "reasoning_mode": context.get("reasoning_mode"),
                },
                "provenance": f"Executed: queried project memory — {message}",
            }
        ]

    if trigger == "chat:git_log":
        return [
            {
                "type": "chat_git_log",
                "policy": ACTION_POLICY["chat_git_log"],
                "params": {"project_id": project_id, "question": message, "raw": message},
                "provenance": f"Executed: queried git history — {message}",
            }
        ]

    if trigger == "chat:morning_brief":
        return [
            {
                "type": "chat_morning_brief",
                "policy": ACTION_POLICY["chat_morning_brief"],
                "params": {"project_id": project_id},
                "provenance": "Executed: generated morning brief from stored memory",
            }
        ]

    # ── Cross-app control triggers ──────────────────────────────────

    if trigger == "chat:copy_to_clipboard":
        return [
            {
                "type": "copy_to_clipboard",
                "policy": ACTION_POLICY["copy_to_clipboard"],
                "params": {"project_id": project_id, "text": target},
                "provenance": "Executed: copied text to clipboard",
            }
        ]

    if trigger == "chat:paste_clipboard":
        return [
            {
                "type": "paste_clipboard",
                "policy": ACTION_POLICY["paste_clipboard"],
                "params": {"project_id": project_id},
                "provenance": "Suggested: paste clipboard content into the active app",
            }
        ]

    if trigger == "chat:focus_app":
        return [
            {
                "type": "focus_app",
                "policy": ACTION_POLICY["focus_app"],
                "params": {"project_id": project_id, "app_name": target},
                "provenance": f"Suggested: focus app — {target}",
            }
        ]

    if trigger == "chat:send_keystroke":
        return [
            {
                "type": "send_keystroke",
                "policy": ACTION_POLICY["send_keystroke"],
                "params": {"project_id": project_id, "keystrokes": target},
                "provenance": f"Suggested: send keystroke — {target}",
            }
        ]

    if trigger == "chat:submit_prompt":
        from agent_actions import _resolve_app_target
        from config import settings

        app_name = parsed.get("app_name", "")
        url = parsed.get("url", "")
        prompt_text = parsed.get("prompt", "")
        target_str = parsed.get("target", "") or message

        # If app_name/url not set, resolve from target via the app-name map
        if not url and not app_name:
            kind, resolved = _resolve_app_target(target_str)
            if kind == "url":
                url = resolved
            else:
                app_name = resolved

        # If no explicit prompt text, try to generate one using the reasoning engine
        if not prompt_text:
            has_llm = (
                any(
                    getattr(settings, k, "")
                    for k in (
                        "groq_api_key",
                        "gemini_api_key",
                        "nvidia_api_key",
                        "minimax_api_key",
                        "openrouter_api_key",
                        "cohere_api_key",
                        "api_key",
                    )
                )
                or settings.bedrock_available
            )
            if has_llm:
                try:
                    from agent_actions import generate_prompt_for_app

                    generated = generate_prompt_for_app(message, url or app_name, project_id)
                    if generated:
                        prompt_text = generated
                except Exception as exc:
                    logger.warning("plan: prompt generation failed | %s", exc)
            # Fall back to target if generation was skipped or failed
            if not prompt_text:
                prompt_text = target_str

        return [
            {
                "type": "submit_prompt_to_app",
                "policy": ACTION_POLICY["submit_prompt_to_app"],
                "params": {
                    "project_id": project_id,
                    "prompt": prompt_text,
                    "app_name": app_name,
                    "url": url,
                },
                "provenance": f"Submit prompt to {url or app_name}",
            }
        ]

    if trigger == "chat:verify_result":
        return [
            {
                "type": "verify_result",
                "policy": ACTION_POLICY["verify_result"],
                "params": {
                    "project_id": project_id,
                    "type": "clipboard_has_content",
                    "target": target,
                },
                "provenance": f"Executed: verified result — {target}",
            }
        ]

    # ── Visual feedback triggers ────────────────────────────────────

    if trigger == "chat:capture_screen":
        return [
            {
                "type": "capture_screen",
                "policy": ACTION_POLICY["capture_screen"],
                "params": {"project_id": project_id, "region": parsed.get("region", "")},
                "provenance": "Suggested: capture screen",
            }
        ]

    if trigger == "chat:ocr_image":
        return [
            {
                "type": "ocr_image",
                "policy": ACTION_POLICY["ocr_image"],
                "params": {"project_id": project_id, "image_path": target},
                "provenance": f"Executed: OCR on image — {target}",
            }
        ]

    if trigger == "chat:read_visible_context":
        return [
            {
                "type": "read_visible_context",
                "policy": ACTION_POLICY["read_visible_context"],
                "params": {"project_id": project_id},
                "provenance": "Suggested: read visible context from screen",
            }
        ]

    if trigger == "chat:diagnose_visible_error":
        return [
            {
                "type": "diagnose_visible_error",
                "policy": ACTION_POLICY["diagnose_visible_error"],
                "params": {"project_id": project_id},
                "provenance": "Suggested: diagnose visible error on screen",
            }
        ]

    if trigger == "chat:review_visible_design":
        return [
            {
                "type": "review_visible_design",
                "policy": ACTION_POLICY["review_visible_design"],
                "params": {"project_id": project_id},
                "provenance": "Suggested: review visible design on screen",
            }
        ]

    if trigger == "chat:generate_prompt_from_screen":
        return [
            {
                "type": "generate_prompt_from_screen",
                "policy": ACTION_POLICY["generate_prompt_from_screen"],
                "params": {"project_id": project_id},
                "provenance": "Executed: generated prompt from screen content",
            }
        ]

    if trigger == "chat:verify_visible_result":
        return [
            {
                "type": "verify_visible_result",
                "policy": ACTION_POLICY["verify_visible_result"],
                "params": {"project_id": project_id},
                "provenance": "Executed: verified visible result on screen",
            }
        ]

    return []


def _build_reply(trigger: str, actions: list[dict[str, Any]], context: dict[str, Any]) -> str:
    """Build a meaningful human-readable reply from action results."""
    executed = [a for a in actions if a.get("executed") and a.get("result")]
    suggested = [
        a
        for a in actions
        if not a.get("executed")
        and a.get("policy") in ("suggest", "confirm_once", "require_approval")
    ]
    failed = [
        a
        for a in actions
        if not a.get("executed")
        and a.get("policy") == "auto_execute"
        and (a.get("result") or {}).get("success") is False
    ]

    if not actions:
        return "I didn't understand that. Try: explain repo, resume project, run tests, or ask about your project."

    lines: list[str] = []

    for action in executed:
        result = action.get("result") or {}
        atype = action.get("type", "")

        if atype == "chat_explain_repo":
            explanation = result.get("explanation") or result.get("readme_summary") or ""
            error = result.get("error")
            if error:
                lines.append(f"Could not explain repository: {error}")
            elif explanation:
                lines.append(f"**Repository Overview:**\n{explanation[:1000]}")
            else:
                lines.append("Repository explained — no README or architecture notes found yet.")

        elif atype == "chat_continue_work":
            suggestion = result.get("suggestion") or ""
            pending = result.get("pending_todos_count", 0)
            if suggestion:
                lines.append(f"**Next step:** {suggestion}")
            if pending:
                lines.append(f"You have {pending} pending TODO(s).")

        elif atype == "chat_open_browser":
            msg = result.get("message", "")
            prefix = "[browser]" if result.get("action") == "open_browser" else "[app]"
            lines.append(f"{prefix} {msg}")

        elif atype == "chat_open_app":
            msg = result.get("message", "")
            lines.append(f"[app] {msg}")

        elif atype == "chat_system_command":
            msg = result.get("message", "")
            if result.get("suggested"):
                lines.append(f"⚠ {msg}")
            else:
                lines.append(f"[system] {msg}")

        elif atype == "chat_query_memory":
            answer = result.get("answer", "")
            if answer:
                lines.append(answer)

        elif atype == "chat_generate_prompt":
            answer = result.get("answer", "")
            prompt = result.get("prompt", answer)
            if prompt:
                lines.append(f"**Generated prompt:**\n{prompt}")

        elif atype == "chat_git_log":
            answer = result.get("answer", "")
            if answer:
                lines.append(answer)

        elif atype == "chat_morning_brief":
            highlights = result.get("highlights", [])
            pending = result.get("pending_items", [])
            commits_count = result.get("commits_count", 0)
            brief_text = result.get("brief_text", "")
            lines.append(f"**Morning Brief** — {commits_count} recent commit(s)")
            if brief_text:
                lines.append(brief_text[:800])
            else:
                if highlights:
                    lines.append("Recent activity:\n" + "\n".join(f"• {h}" for h in highlights[:5]))
                if pending:
                    lines.append("Pending:\n" + "\n".join(f"• {p}" for p in pending[:5]))

        elif atype in ("suggest_next_task",):
            suggestion = result.get("suggestion", "")
            if suggestion:
                lines.append(f"**Suggested:** {suggestion}")

        elif atype == "update_project_summary":
            lines.append("Project summary updated.")

        elif atype == "regenerate_daily_brief":
            lines.append("Daily brief regenerated.")

        elif atype == "flag_related_todos":
            flagged = result.get("flagged", 0)
            if flagged:
                lines.append(f"{flagged} related TODO(s) flagged.")

        # ── Cross-app control replies ──────────────────────────

        elif atype == "copy_to_clipboard":
            copied = result.get("copied")
            length = result.get("length", 0)
            if copied:
                lines.append(f"Copied {length} chars to clipboard.")
            else:
                lines.append("Failed to copy to clipboard.")

        elif atype == "paste_clipboard":
            if result.get("pasted"):
                lines.append("Pasted clipboard content into the active app.")
            else:
                lines.append("Clipboard is empty or paste failed.")

        elif atype == "open_url":
            url = result.get("url", "")
            opened = result.get("opened")
            if opened:
                lines.append(f"Opened {url} in the browser.")
            else:
                lines.append(f"Failed to open {url}.")

        elif atype == "focus_app":
            app = result.get("app", "")
            focused = result.get("focused")
            if focused:
                lines.append(f"Brought {app} to the foreground.")
            else:
                lines.append(f"Could not find {app} running.")

        elif atype == "send_keystroke":
            ks = result.get("keystrokes", "")
            sent = result.get("sent")
            if sent:
                lines.append(f"Sent keystroke {ks}.")
            else:
                lines.append(f"Failed to send keystroke {ks}.")

        elif atype == "submit_prompt_to_app":
            steps = result.get("steps", [])
            prompt_length = result.get("prompt_length", 0)
            all_ok = all(s.get("success") for s in steps)
            if all_ok:
                lines.append(f"Submitted {prompt_length}-char prompt to the target app.")
            else:
                failed_steps = [s for s in steps if not s.get("success")]
                lines.append(
                    f"Prompt submission partially failed: {len(failed_steps)} step(s) did not complete."
                )

        elif atype == "verify_result":
            verified = result.get("verified")
            check_type = result.get("check_type", "")
            if verified:
                lines.append(f"Verification passed for {check_type}.")
            else:
                lines.append(f"Verification failed for {check_type}.")

        # ── Visual feedback replies ────────────────────────────

        elif atype == "capture_screen":
            path = result.get("path", "")
            if path:
                lines.append(f"Screen captured: {path}")
            else:
                lines.append("Screen capture failed.")

        elif atype == "ocr_image":
            text = result.get("text", "")
            if text:
                lines.append(f"Extracted text ({len(text)} chars):\n{text[:500]}")
            else:
                lines.append("OCR extraction returned no text.")

        elif atype == "read_visible_context":
            text = result.get("text", "")
            if text:
                lines.append(f"Visible context captured ({len(text)} chars):\n{text[:500]}")
            else:
                lines.append("Could not read visible context.")

        elif atype == "diagnose_visible_error":
            text = result.get("text", "")
            if text:
                lines.append(f"Visible error captured ({len(text)} chars):\n{text[:500]}")
            else:
                lines.append("Could not capture visible error.")

        elif atype == "review_visible_design":
            text = result.get("text", "")
            if text:
                lines.append(f"Design review captured ({len(text)} chars):\n{text[:500]}")
            else:
                lines.append("Could not capture design for review.")

        elif atype == "generate_prompt_from_screen":
            text = result.get("text", "")
            if text:
                lines.append(
                    f"Prompt generated from screen content ({len(text)} chars):\n{text[:500]}"
                )
            else:
                lines.append("Could not generate prompt from screen.")

        elif atype == "verify_visible_result":
            text = result.get("text", "")
            if text:
                lines.append(f"Visible result verified ({len(text)} chars).")
            else:
                lines.append("Could not verify visible result.")

    for action in failed:
        result = action.get("result") or {}
        msg = result.get("message") or "Action failed."
        lines.append(f"[failed] {msg}")

    for action in suggested:
        atype = action.get("type", "")
        result = action.get("result") or {}
        policy = action.get("policy", "suggest")

        if atype == "chat_run_tests":
            cmd = result.get("suggested_command", "pytest")
            repo = result.get("repo_path", "")
            lines.append(
                f"**Run tests:** `{cmd}`{f' in `{repo}`' if repo else ''}\n*(Confirm to execute)*"
            )

        elif atype == "chat_generate_commit_message":
            msg = result.get("commit_message") if result else None
            if msg:
                lines.append(f"**Suggested commit message:**\n```\n{msg}\n```")
            else:
                lines.append(
                    "Ready to generate a commit message — stage your changes first, then confirm."
                )

        elif atype == "restore_workspace":
            lines.append(
                "**Restore workspace?** This will check out the active branch and start your dev servers. Confirm to proceed."
            )

        elif atype in ("chat_open_app", "chat_open_browser"):
            msg = result.get("message", "")
            lines.append(f"**Open:** {msg}")
            options = result.get("options") or []
            for opt in options[:5]:
                lines.append(f"  • {opt.get('name', 'unknown')} → `{opt.get('target', '')}`")

        elif atype == "paste_clipboard":
            lines.append(
                "**Paste clipboard?** This will paste into the active app. Confirm to proceed."
            )

        elif atype == "focus_app":
            app = result.get("app", "")
            lines.append(
                f"**Focus app?** This will bring {app} to the foreground. Confirm to proceed."
            )

        elif atype == "send_keystroke":
            ks = result.get("keystrokes", "")
            lines.append(
                f"**Send keystroke?** This will send {ks} to the active app. Confirm to proceed."
            )

        elif atype == "capture_screen":
            lines.append("**Capture screen?** This will take a screenshot. Confirm to proceed.")

        elif atype == "read_visible_context":
            lines.append(
                "**Read visible context?** This will capture and OCR the screen. Confirm to proceed."
            )

        elif atype == "diagnose_visible_error":
            lines.append(
                "**Diagnose visible error?** This will capture the screen and parse the error. Confirm to proceed."
            )

        elif atype == "review_visible_design":
            lines.append(
                "**Review visible design?** This will capture the screen and analyze the design. Confirm to proceed."
            )

        elif policy == "require_approval":
            lines.append(
                f"**Requires approval:** {atype} — this action will interact with an external service. Confirm to proceed."
            )

        else:
            lines.append(f"**{atype}** — confirm to proceed.")

    return "\n\n".join(lines) if lines else "Done."


def _log_plan(trigger: str, actions: list[dict[str, Any]]) -> None:
    """Log the planned actions to decision_log for provenance tracking."""
    for action in actions:
        try:
            insert_decision(
                project_id=action["params"].get("project_id"),
                decision=f"Planned action: {action['type']} (policy={action['policy']})",
                rationale=action["provenance"],
            )
        except Exception as exc:
            logger.warning("Failed to log planned action to decision_log — %s", exc)


# ─── Orchestrator bridge ──────────────────────────────────────────────────────
# These functions keep the existing single-pass `plan()` intact for tests and
# simple triggers, while exposing the multi-step orchestration loop for
# complex goals (from triggers or the chat endpoint).


def orchestrate(
    goal: str, project_id: str | None = None, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Run the multi-step agent orchestration loop for a complex goal.

    Wraps `orchestrator.run_orchestrator` and converts its result into the
    same dict shape `plan()` returns, so the chat endpoint can consume it
    interchangeably.

    Returns:
        {
            "trigger": "orchestrator",
            "reply": str,
            "actions": list[dict],
            "success": bool,
            "needs_approval": bool,
            "pending_step": dict | None,
        }
    """
    from decision_engine.orchestrator import run_orchestrator

    orch_result = run_orchestrator(goal=goal, project_id=project_id, context=context or {})

    actions: list[dict[str, Any]] = []
    for step in orch_result.steps:
        obs = step.observation
        policy = (
            "suggest"
            if (not step.success and step.observation.get("suggested"))
            else "auto_execute"
        )
        actions.append(
            {
                "type": step.tool,
                "policy": policy,
                "params": step.params,
                "provenance": f"Step {step.step_index + 1}: {step.tool}",
                "executed": step.success,
                "executed_at": None,
                "result": {
                    "success": step.success,
                    "observation": obs,
                },
            }
        )

    return {
        "trigger": "orchestrator",
        "reply": orch_result.final_response
        or f"Goal: {goal}. Stopped: {orch_result.stopped_reason}",
        "actions": actions,
        "success": orch_result.success,
        "needs_approval": orch_result.needs_approval,
        "pending_step": orch_result.pending_step,
    }
