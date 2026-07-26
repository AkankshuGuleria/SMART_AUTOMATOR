"""
decision_engine/planner.py — AUTOMATA Decision Engine: action planner.

Owns:    Deciding whether an autonomous action should be executed immediately
           (passive/reversible) or only suggested to the developer
           (environment-changing, irreversible).
Never:   Must not call Bedrock or CockroachDB directly — routing only.
           Must not bypass the Agent Loop. See ARCHITECTURE.md §2.3.
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9 (guardrails).

Phase 0: Stub — plan() returns a no-op action.
Phase 4.5: Implement action classification and routing to execute/suggest.

GUARDRAILS (encoded in ACTION_POLICY below):
- "auto_execute": passive, reversible — run without asking (update summary,
  flag TODO, generate brief).
- "suggest": environment-changing or irreversible — surface as a proposal,
  never silently execute (restore workspace, launch editor).
"""

import logging
from datetime import datetime
from typing import Any

from db.client import insert_decision

logger = logging.getLogger(__name__)

# Maps action types to their policy. Extend here in Phase 4.5.
# Never add an action as "auto_execute" if it modifies the OS environment.
ACTION_POLICY: dict[str, str] = {
    "update_project_summary": "auto_execute",
    "regenerate_daily_brief":  "auto_execute",
    "flag_related_todos":      "auto_execute",
    "store_session_summary":   "auto_execute",
    "suggest_next_task":       "auto_execute",   # surfaced passively in brief
    "restore_workspace":       "suggest",         # never auto-restores
    "launch_editor":           "suggest",
    "start_dev_servers":       "suggest",
    "chat_continue_work":      "suggest",
    "chat_explain_repo":       "suggest",
    "chat_run_tests":          "suggest",
    "chat_generate_commit_message": "suggest",
}


def plan(trigger: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Given a trigger and its context, decide what actions to take and in what mode.

    Returns a plan dict:
    {
        "trigger": str,
        "actions": [
            {
                "type": str,          # key in ACTION_POLICY
                "policy": str,        # "auto_execute" | "suggest"
                "params": dict,       # action-specific parameters
                "provenance": str,    # human-readable explanation for the UI
                "executed": bool,     # True if the action was run successfully
                "executed_at": str | None,   # ISO timestamp when executed, or None
            },
            ...
        ]
    }

    Phase 4.5 implementation:
    - Map trigger → list of action types.
    - Look up each action type in ACTION_POLICY.
    - For "auto_execute": route to the relevant module directly.
    - For "suggest": build a SuggestedAction and surface it in the next
      morning brief or via a passive UI notification.
    - Log every planned action to decision_log with provenance.
    - Log every suggest action with executed=False for provenance transparency.
    """
    logger.info("plan: trigger=%s", trigger)

    actions = _get_actions_for_trigger(trigger, context)

    # Log the plan for provenance
    _log_plan(trigger, actions)

    for action in actions:
        policy = action.get("policy", "suggest")
        action.setdefault("executed", False)
        action.setdefault("executed_at", None)

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
                    action["type"],
                    exc,
                )
            continue

        try:
            executed = _execute_action(action)
            action["executed"] = bool(executed)
            if executed:
                action["executed_at"] = datetime.now().isoformat()
        except Exception as exc:
            logger.warning(
                "plan: action failed | type=%s error=%s", action["type"], exc
            )

    return {
        "trigger": trigger,
        "actions": actions,
    }


def _execute_action(action: dict[str, Any]) -> bool:
    """Dispatch an action to its concrete implementation. Returns True on success."""
    action_type = action.get("type", "")
    params = action.get("params", {})

    if action_type == "update_project_summary":
        return _execute_update_project_summary(params)
    if action_type == "regenerate_daily_brief":
        return _execute_regenerate_daily_brief(params)
    if action_type == "flag_related_todos":
        return _execute_flag_related_todos(params)
    if action_type == "store_session_summary":
        return _execute_store_session_summary(params)
    if action_type == "suggest_next_task":
        return _execute_suggest_next_task(params)

    logger.warning("plan: unknown action type | %s", action_type)
    return False


def _execute_update_project_summary(params: dict[str, Any]) -> bool:
    """Reuse agent_actions.generate_project_summary. Fail open if Bedrock is unavailable."""
    project_id = params.get("project_id")
    if not project_id:
        return False

    try:
        import agent_actions as _agent_actions
        result = _agent_actions.generate_project_summary(project_id)
        if result and result.get("summary"):
            logger.debug(
                "plan: project summary updated | project=%s summary=%s...",
                project_id,
                result["summary"][:60],
            )
            return True
    except Exception as exc:
        logger.warning(
            "plan: generate_project_summary failed | project=%s error=%s — failing open",
            project_id,
            exc,
        )
    return False


def _build_brief_payload(project_id: str) -> dict[str, Any] | None:
    """Build a daily brief payload from recent DB memory.

    Used when AI-generated content is unavailable; provides a fallback brief
    populated with concrete recent activity so the brief panel never renders empty.
    """
    from db import client as _db_client

    commits = _db_client.get_commits(project_id, limit=20) or []
    file_edits = _db_client.get_file_edits(project_id, limit=5) or []
    todos = _db_client.get_todos(project_id, status="pending") or []

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


def _execute_regenerate_daily_brief(params: dict[str, Any]) -> bool:
    """Regenerate the daily brief using recent DB memory as a fallback payload."""
    project_id = params.get("project_id")
    if not project_id:
        return False

    payload = _build_brief_payload(project_id)
    if payload is None:
        logger.warning("plan: regenerate_daily_brief | no payload built | project=%s", project_id)
        return False

    import db.client as _db_client
    success = _db_client.upsert_daily_brief(
        project_id=project_id,
        brief_date=str(payload.get("brief_date", datetime.now().strftime("%Y-%m-%d"))),
        commits_count=int(payload.get("commits_count", 0)),
        highlights=list(payload.get("highlights", [])),
        pending_items=list(payload.get("pending_items", [])),
    )
    if success:
        logger.debug("plan: daily brief upserted | project=%s", project_id)
    return bool(success)


def _execute_flag_related_todos(params: dict[str, Any]) -> bool:
    """Flag pending TODOs by prepending [auto-flagged] to their description."""
    project_id = params.get("project_id")
    if not project_id:
        return False

    try:
        import db.client as _db_client
        todos = _db_client.get_todos(project_id, status="pending")
        if not todos:
            logger.debug("plan: flag_related_todos | no pending todos | project=%s", project_id)
            return True

        flagged = 0
        for todo in todos:
            current = str(todo.get("description", ""))
            if not current.startswith("[auto-flagged]"):
                updated = f"[auto-flagged] {current}"
                if _db_client.update_todo_description(str(todo.get("id", "")), updated):
                    flagged += 1

        logger.debug("plan: flag_related_todos | flagged=%d | project=%s", flagged, project_id)
        return flagged > 0
    except Exception as exc:
        logger.warning(
            "plan: flag_related_todos failed | project=%s error=%s",
            project_id,
            exc,
        )
        return False


def _execute_store_session_summary(params: dict[str, Any]) -> bool:
    """Store a session summary by ending the session with any provided summary text."""
    project_id = params.get("project_id")
    session_id = params.get("session_id")
    summary = params.get("summary")

    if not project_id or not session_id:
        return False

    if not summary:
        logger.debug(
            "plan: store_session_summary | no summary available | session=%s", session_id
        )
        return False

    import db.client as _db_client
    success = _db_client.end_session(project_id, session_id, summary=summary)
    if success:
        logger.debug("plan: session summary stored | session=%s", session_id)
    return bool(success)


def _execute_suggest_next_task(params: dict[str, Any]) -> bool:
    """Build a fallback next-task suggestion text from pending TODOs.

    Does NOT call Bedrock. In Phase 2, this can be replaced with an AI-generated
    suggestion grounded in pending TODOs and recent memory.
    """
    project_id = params.get("project_id")
    if not project_id:
        return False

    try:
        import db.client as _db_client
        todos = _db_client.get_todos(project_id, status="pending") or []

        if todos:
            top = todos[0]
            title = str(top.get("description", "")).strip()
            suggestion = f"Pending: {title}" if title else "Next task: review pending TODOs"
        else:
            suggestion = "Next task: no pending TODOs — check recent commits for clues"

        params["suggestion_text"] = suggestion
        params["pending_todos_count"] = len(todos)
        logger.debug(
            "plan: suggest_next_task | suggestion='%s' | project=%s",
            suggestion[:60],
            project_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "plan: suggest_next_task failed | project=%s error=%s",
            project_id,
            exc,
        )
        return False


def _get_actions_for_trigger(trigger: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a trigger to a list of planned actions based on ACTION_POLICY."""
    actions: list[dict[str, Any]] = []

    if trigger == "on_commit":
        actions = [
            {
                "type": "update_project_summary",
                "policy": ACTION_POLICY["update_project_summary"],
                "params": {
                    "project_id": context.get("project_id"),
                    "commit_hash": context.get("commit_hash"),
                },
                "provenance": (
                    f"Auto-executed: commit {context.get('commit_hash', '')[:8]} "
                    "detected — updating project summary"
                ),
            },
            {
                "type": "regenerate_daily_brief",
                "policy": ACTION_POLICY["regenerate_daily_brief"],
                "params": {"project_id": context.get("project_id")},
                "provenance": "Auto-executed: daily brief regenerated after new commit",
            },
            {
                "type": "flag_related_todos",
                "policy": ACTION_POLICY["flag_related_todos"],
                "params": {
                    "project_id": context.get("project_id"),
                    "commit_message": context.get("commit_message", ""),
                },
                "provenance": "Auto-executed: related TODOs flagged based on commit message",
            },
        ]
    elif trigger == "on_session_end":
        actions = [
            {
                "type": "store_session_summary",
                "policy": ACTION_POLICY["store_session_summary"],
                "params": {
                    "project_id": context.get("project_id"),
                    "session_id": context.get("session_id"),
                },
                "provenance": "Auto-executed: session summary stored at session end",
            },
            {
                "type": "regenerate_daily_brief",
                "policy": ACTION_POLICY["regenerate_daily_brief"],
                "params": {"project_id": context.get("project_id")},
                "provenance": "Auto-executed: daily brief regenerated at session end",
            },
            {
                "type": "suggest_next_task",
                "policy": ACTION_POLICY["suggest_next_task"],
                "params": {"project_id": context.get("project_id")},
                "provenance": "Auto-executed: next task suggestion generated from pending TODOs",
            },
        ]
    elif trigger == "chat:resume_project":
        actions = [
            {
                "type": "restore_workspace",
                "policy": ACTION_POLICY["restore_workspace"],
                "params": {
                    "project_id": context.get("project_id"),
                    "message": context.get("message", ""),
                },
                "provenance": f"Suggested: restore workspace from chat intent — {context.get('message', '')}",
            }
        ]
    elif trigger == "chat:continue_work":
        actions = [
            {
                "type": "chat_continue_work",
                "policy": ACTION_POLICY["chat_continue_work"],
                "params": {
                    "project_id": context.get("project_id"),
                    "message": context.get("message", ""),
                },
                "provenance": f"Suggested: continue previous work — {context.get('message', '')}",
            }
        ]
    elif trigger == "chat:run_tests":
        actions = [
            {
                "type": "chat_run_tests",
                "policy": ACTION_POLICY["chat_run_tests"],
                "params": {
                    "project_id": context.get("project_id"),
                    "message": context.get("message", ""),
                },
                "provenance": f"Suggested: run tests — {context.get('message', '')}",
            }
        ]
    elif trigger == "chat:explain_repo":
        actions = [
            {
                "type": "chat_explain_repo",
                "policy": ACTION_POLICY["chat_explain_repo"],
                "params": {
                    "project_id": context.get("project_id"),
                    "message": context.get("message", ""),
                },
                "provenance": f"Suggested: explain repository — {context.get('message', '')}",
            }
        ]
    elif trigger == "chat:generate_commit_message":
        actions = [
            {
                "type": "chat_generate_commit_message",
                "policy": ACTION_POLICY["chat_generate_commit_message"],
                "params": {
                    "project_id": context.get("project_id"),
                    "message": context.get("message", ""),
                },
                "provenance": f"Suggested: generate commit message — {context.get('message', '')}",
            }
        ]

    return actions


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
