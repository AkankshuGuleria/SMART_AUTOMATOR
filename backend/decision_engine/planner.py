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
from datetime import datetime
from typing import Any

from db.client import insert_decision

logger = logging.getLogger(__name__)

# Maps action types to their policy.
ACTION_POLICY: dict[str, str] = {
    "update_project_summary":         "auto_execute",
    "regenerate_daily_brief":         "auto_execute",
    "flag_related_todos":             "auto_execute",
    "store_session_summary":          "auto_execute",
    "suggest_next_task":              "auto_execute",
    "chat_explain_repo":              "auto_execute",
    "chat_open_browser":              "auto_execute",   # opening browser is safe
    "chat_open_app":                  "auto_execute",   # opening an app is safe
    "chat_system_command":            "suggest",        # system-level changes need confirmation
    "chat_query_memory":              "auto_execute",   # read-only
    "chat_morning_brief":             "auto_execute",   # read-only
    "chat_continue_work":             "auto_execute",   # read-only suggestion
    "chat_generate_commit_message":   "suggest",        # requires staged changes
    "chat_run_tests":                 "suggest",        # environment-changing
    "restore_workspace":              "suggest",        # never auto-restores
    "launch_editor":                  "suggest",
    "start_dev_servers":              "suggest",
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

        if policy == "suggest":
            try:
                insert_decision(
                    project_id=action["params"].get("project_id"),
                    decision=f"Suggested action: {action['type']} (requires approval)",
                    rationale=action["provenance"],
                )
            except Exception as exc:
                logger.warning(
                    "plan: failed to log suggested action | type=%s error=%s",
                    action["type"], exc,
                )
            continue

        try:
            result = _execute_action(action)
            if result is not None:
                action["executed"] = True
                action["executed_at"] = datetime.now().isoformat()
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
        "update_project_summary":       _execute_update_project_summary,
        "regenerate_daily_brief":       _execute_regenerate_daily_brief,
        "flag_related_todos":           _execute_flag_related_todos,
        "store_session_summary":        _execute_store_session_summary,
        "suggest_next_task":            _execute_suggest_next_task,
        "chat_explain_repo":            _execute_chat_explain_repo,
        "chat_continue_work":           _execute_chat_continue_work,
        "chat_generate_commit_message": _execute_chat_generate_commit_message,
        "chat_open_browser":            _execute_chat_open_browser,
        "chat_open_app":                _execute_chat_open_app,
        "chat_system_command":          _execute_chat_system_command,
        "chat_query_memory":            _execute_chat_query_memory,
        "chat_morning_brief":           _execute_chat_morning_brief,
        "chat_run_tests":               _execute_chat_run_tests,
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
        result = _aa.explain_repository(project_id, params.get("repo_path", ""))
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
    if not question:
        return None
    try:
        from ai.bedrock_client import invoke_reasoning
        from memory.retrieval import retrieve_by_vector, retrieve_recent
        memories = []
        if project_id:
            memories.extend(
                retrieve_by_vector(question, ["commits", "todos", "architecture_notes"], project_id=project_id, top_k=6)
            )
            if not memories:
                for table in ("commits", "todos", "file_edits"):
                    memories.extend(retrieve_recent(project_id, table, limit=3))
        answer = invoke_reasoning(
            system_prompt=(
                "You are AUTOMATA's Reasoning Engine. Answer concisely using only "
                "retrieved project memory. If memory is incomplete, say so without inventing details."
            ),
            user_message=question,
            retrieved_memories=memories,
        ) if memories else None
        if not answer and memories:
            bullets = "\n".join(
                f"- [{m.get('table','memory')}] {m.get('content','')}"
                for m in memories[:5] if m.get("content")
            )
            answer = f"Reasoning unavailable, but I found relevant memory:\n{bullets}"
        elif not answer:
            answer = "No stored memory found for that question."
        return {"answer": answer, "memories_used": len(memories)}
    except Exception as exc:
        logger.warning("plan: chat_query_memory failed | %s", exc)
        return None


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


# ─── Trigger → action mapping ─────────────────────────────────────────────────

def _get_actions_for_trigger(trigger: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a trigger to a list of planned actions."""
    project_id = context.get("project_id")
    message = context.get("message", "")
    parsed = context.get("parsed", {})
    target = parsed.get("target", "") or parsed.get("project_hint", "") or message

    if trigger == "on_commit":
        return [
            {
                "type": "update_project_summary",
                "policy": ACTION_POLICY["update_project_summary"],
                "params": {"project_id": project_id, "commit_hash": context.get("commit_hash")},
                "provenance": f"Auto-executed: commit {str(context.get('commit_hash',''))[:8]} detected",
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
                "params": {"project_id": project_id, "commit_message": context.get("commit_message", "")},
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
        return [{"type": "restore_workspace", "policy": ACTION_POLICY["restore_workspace"],
                 "params": {"project_id": project_id, "message": message},
                 "provenance": f"Suggested: restore workspace — {message}"}]

    if trigger == "chat:continue_work":
        return [{"type": "chat_continue_work", "policy": ACTION_POLICY["chat_continue_work"],
                 "params": {"project_id": project_id, "message": message},
                 "provenance": f"Executed: continue previous work — {message}"}]

    if trigger == "chat:run_tests":
        return [{"type": "chat_run_tests", "policy": ACTION_POLICY["chat_run_tests"],
                 "params": {"project_id": project_id, "message": message},
                 "provenance": f"Suggested: run tests — {message}"}]

    if trigger == "chat:explain_repo":
        return [{"type": "chat_explain_repo", "policy": ACTION_POLICY["chat_explain_repo"],
                 "params": {"project_id": project_id, "message": message, "repo_path": parsed.get("repo_path", "")},
                 "provenance": f"Executed: explain repository — {message}"}]

    if trigger == "chat:generate_commit_message":
        return [{"type": "chat_generate_commit_message", "policy": ACTION_POLICY["chat_generate_commit_message"],
                 "params": {"project_id": project_id, "message": message},
                 "provenance": f"Suggested: generate commit message — {message}"}]

    if trigger == "chat:open_browser":
        from agent_actions import _resolve_app_target
        _, resolved = _resolve_app_target(target)
        return [{"type": "chat_open_browser", "policy": ACTION_POLICY["chat_open_browser"],
                 "params": {"project_id": project_id, "target": target, "message": message},
                 "provenance": f"Executed: opened {resolved}"}]

    if trigger == "chat:open_app":
        from agent_actions import _resolve_app_target
        _, resolved = _resolve_app_target(target)
        return [{"type": "chat_open_app", "policy": ACTION_POLICY["chat_open_app"],
                 "params": {"project_id": project_id, "target": target, "message": message},
                 "provenance": f"Executed: launched {resolved}"}]

    if trigger == "chat:system_command":
        return [{"type": "chat_system_command", "policy": ACTION_POLICY["chat_system_command"],
                 "params": {"project_id": project_id, "message": message, "raw": target},
                 "provenance": f"Suggested system command — {target}"}]

    if trigger == "chat:query_memory":
        return [{"type": "chat_query_memory", "policy": ACTION_POLICY["chat_query_memory"],
                 "params": {"project_id": project_id, "question": message, "raw": message},
                 "provenance": f"Executed: queried project memory — {message}"}]

    if trigger == "chat:morning_brief":
        return [{"type": "chat_morning_brief", "policy": ACTION_POLICY["chat_morning_brief"],
                 "params": {"project_id": project_id},
                 "provenance": "Executed: generated morning brief from stored memory"}]

    return []


def _build_reply(trigger: str, actions: list[dict[str, Any]], context: dict[str, Any]) -> str:
    """Build a meaningful human-readable reply from action results."""
    executed = [a for a in actions if a.get("executed") and a.get("result")]
    suggested = [a for a in actions if not a.get("executed") and a.get("policy") == "suggest"]

    if not actions:
        return (
            "I'm not sure how to help with that yet. Try: "
            "\"explain repo\", \"resume project\", \"run tests\", "
            "\"open browser to chatgpt.com\", \"install Java\", "
            "\"open spotify\", or \"what was I working on yesterday?\"."
        )

    lines: list[str] = []

    for action in executed:
        result = action.get("result") or {}
        atype = action.get("type", "")

        if atype == "chat_explain_repo":
            explanation = result.get("explanation") or result.get("readme_summary") or ""
            if explanation:
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
            lines.append(f"[browser] {msg}")

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

        elif atype == "chat_morning_brief":
            highlights = result.get("highlights", [])
            pending = result.get("pending_items", [])
            commits_count = result.get("commits_count", 0)
            lines.append(f"**Morning Brief** — {commits_count} recent commit(s)")
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

    for action in suggested:
        atype = action.get("type", "")
        result = action.get("result") or {}

        if atype == "chat_run_tests":
            cmd = result.get("suggested_command", "pytest")
            repo = result.get("repo_path", "")
            lines.append(f"**Run tests:** `{cmd}`{f' in `{repo}`' if repo else ''}\n*(Confirm to execute)*")

        elif atype == "chat_generate_commit_message":
            msg = result.get("commit_message") if result else None
            if msg:
                lines.append(f"**Suggested commit message:**\n```\n{msg}\n```")
            else:
                lines.append("Ready to generate a commit message — stage your changes first, then confirm.")

        elif atype == "restore_workspace":
            lines.append("**Restore workspace?** This will check out the active branch and start your dev servers. Confirm to proceed.")

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
