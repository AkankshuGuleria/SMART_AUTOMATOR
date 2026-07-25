"""
decision_engine/triggers.py — AUTOMATA Decision Engine: trigger detection.

Owns:    Detecting the small, explicit set of triggers that initiate autonomous
          (unsolicited) agent actions. For the MVP: "on_commit" and "on_session_end".
Never:   Must not call Bedrock or CockroachDB directly — it fires the Agent Loop
          (Observe → Reason → Plan → Execute → Update Memory) the same way a
          user query does, just without a user prompt. See ARCHITECTURE.md §2.3.
          Must not bypass the module boundaries in CONVENTIONS.md §3.
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9, ROADMAP.md Phase 4.5.

Phase 0: Stub — trigger handlers are defined but do nothing.
Phase 4.5: Wire on_commit to GitPollerThread events; on_session_end to session
            tracking in memory/capture.py.

GUARDRAILS (from PROJECT.md §9):
- Only on_commit and on_session_end triggers for MVP.
- Every autonomous action is logged with provenance (SKILLS.md §10).
- Passive/reversible actions (update summary, flag TODOs) auto-execute.
- Environment-changing actions (restore workspace) only suggest, never execute.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# MVP trigger set — expand only after Phase 1–4 are solid per ROADMAP.md.
SUPPORTED_TRIGGERS = {"on_commit", "on_session_end"}


def on_commit(project_id: str, commit_hash: str, commit_message: str) -> None:
    """
    Fired when a new commit is detected by GitPollerThread.

    Autonomous actions (Phase 4.5):
    1. Update the project/architecture summary if the commit touched structure.
    2. Regenerate the daily brief.
    3. Detect unfinished TODOs related to the commit (vector search).
    4. Store the resulting memory (Update Memory step).
    5. Surface a suggested next task in the next brief (passive, not interruptive).

    All actions logged to decision_log with provenance (trigger=on_commit, commit_hash).
    """
    logger.info(
        "on_commit trigger fired | project=%s commit=%s msg='%s...'",
        project_id, commit_hash[:8] if len(commit_hash) > 8 else commit_hash,
        commit_message[:60],
    )

    # Phase 4.5: implement via planner.py
    # For now, log the trigger event so it's auditable
    _log_trigger_event("on_commit", project_id, {
        "commit_hash": commit_hash,
        "commit_message": commit_message[:200],
    })


def on_session_end(project_id: str, session_id: str) -> None:
    """
    Fired when a developer session ends (detected by session tracking in memory/capture.py).

    Autonomous actions (Phase 4.5):
    1. Generate an end-of-session summary (Bedrock reasoning over session events).
    2. Store the summary + embedding to the sessions table.
    3. Update or create the daily_briefs row for today.
    4. Flag any unresolved TODOs touched during the session.

    All actions logged with provenance (trigger=on_session_end, session_id).
    """
    logger.info(
        "on_session_end trigger fired | project=%s session=%s",
        project_id, session_id,
    )

    # Phase 4.5: implement via planner.py
    _log_trigger_event("on_session_end", project_id, {
        "session_id": session_id,
    })


def _log_trigger_event(trigger: str, project_id: str, context: dict[str, Any]) -> None:
    """Log a trigger event to the decision_log for provenance tracking."""
    from db.client import insert_decision

    decision_text = f"Trigger '{trigger}' fired for project {project_id}"
    rationale = (
        f"Trigger '{trigger}' was detected automatically. "
        f"Context: {context}. "
        f"This is a passive trigger — no environment-changing actions will be taken without developer confirmation."
    )

    try:
        insert_decision(project_id, decision_text, rationale)
    except Exception as exc:
        logger.warning("Failed to log trigger event to decision_log — %s", exc)
