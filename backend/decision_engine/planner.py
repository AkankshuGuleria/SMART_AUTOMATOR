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
    """
    logger.info("plan: Phase 0 stub | trigger=%s", trigger)

    # Phase 4.5: map triggers to actions based on ACTION_POLICY
    actions = _get_actions_for_trigger(trigger, context)

    # Log the plan for provenance
    _log_plan(trigger, actions)

    return {
        "trigger": trigger,
        "actions": actions,
    }


def _get_actions_for_trigger(trigger: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Map a trigger to a list of planned actions based on ACTION_POLICY."""
    actions: list[dict[str, Any]] = []

    if trigger == "on_commit":
        actions = [
            {
                "type": "update_project_summary",
                "policy": ACTION_POLICY["update_project_summary"],
                "params": {"project_id": context.get("project_id"), "commit_hash": context.get("commit_hash")},
                "provenance": f"Auto-executed: commit {context.get('commit_hash', '')[:8]} detected — updating project summary",
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
                "params": {"project_id": context.get("project_id"), "commit_message": context.get("commit_message", "")},
                "provenance": "Auto-executed: related TODOs flagged based on commit message",
            },
        ]
    elif trigger == "on_session_end":
        actions = [
            {
                "type": "store_session_summary",
                "policy": ACTION_POLICY["store_session_summary"],
                "params": {"project_id": context.get("project_id"), "session_id": context.get("session_id")},
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
