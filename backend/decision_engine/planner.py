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
    return {
        "trigger": trigger,
        "actions": [],  # empty in Phase 0
    }
