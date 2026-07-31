"""
decision_engine/triggers.py — AUTOMATA Decision Engine: autonomous triggers.

Owns:    The small, explicit set of triggers that initiate autonomous
         (unsolicited) agent actions. For the MVP: "on_commit" and
         "on_session_end". Triggers construct a real goal and route it
         through the orchestrator loop (plan → act → observe → reflect).
Never:   Must not call Bedrock or CockroachDB directly — it fires the Agent
         Loop the same way a user query does. See ARCHITECTURE.md §2.3.
         Must not bypass the module boundaries in CONVENTIONS.md §3.
Ref:     ARCHITECTURE.md §2.3, PROJECT.md §9, ROADMAP.md Phase 4.5.

GUARDRAILS (from PROJECT.md §9):
- Only on_commit and on_session_end triggers for MVP.
- Every autonomous action is logged with provenance (SKILLS.md §10).
- Passive/reversible actions auto-execute; environment-changing actions
  only suggest.
"""

from __future__ import annotations

import logging
import time
import threading
from typing import Any

logger = logging.getLogger(__name__)

# MVP trigger set — expand only after Phase 1–4 are solid per ROADMAP.md.
SUPPORTED_TRIGGERS: set[str] = {"on_commit", "on_session_end"}

# Cooldown map: "trigger:project_id" -> last fired monotonic timestamp.
# Prevents rapid-fire LLM calls when multiple commits arrive in a burst.
_TRIGGER_COOLDOWNS: dict[str, float] = {}
_TRIGGER_COOLDOWN_LOCK = threading.Lock()
_TRIGGER_COOLDOWN_SECONDS: float = 300.0  # 5 minutes per project per trigger


def _should_fire(trigger: str, project_id: str) -> bool:
    """Return True if the cooldown has elapsed for this trigger/project."""
    key = f"{trigger}:{project_id}"
    now = time.monotonic()
    with _TRIGGER_COOLDOWN_LOCK:
        last = _TRIGGER_COOLDOWNS.get(key, 0.0)
        if now - last < _TRIGGER_COOLDOWN_SECONDS:
            logger.debug("Trigger %s skipped for project %s (cooldown active)", trigger, project_id)
            return False
        _TRIGGER_COOLDOWNS[key] = now
    return True


def on_commit(project_id: str, commit_hash: str, commit_message: str) -> None:
    """
    Fired when a new commit is detected by GitPollerThread (memory/capture.py).

    Uses the lightweight trigger→action path in planner.py instead of the
    full orchestrator loop, so this stays fast and never blocks the poller.
    """
    logger.info(
        "on_commit trigger fired | project=%s commit=%s msg='%s...'",
        project_id,
        commit_hash[:8] if len(commit_hash) > 8 else commit_hash,
        commit_message[:60],
    )

    if not _should_fire("on_commit", project_id):
        return

    _log_trigger_event("on_commit", project_id, {
        "commit_hash": commit_hash,
        "commit_message": commit_message[:200],
    })

    context = {
        "project_id": project_id,
        "commit_hash": commit_hash,
        "commit_message": commit_message[:500],
    }

    try:
        from decision_engine.planner import plan
        plan_result = plan("on_commit", context)
        logger.info(
            "on_commit actions executed | project=%s actions=%d",
            project_id,
            len(plan_result.get("actions", [])),
        )
    except Exception as exc:
        logger.warning("on_commit: plan failed — %s", exc)

    # Background: periodically refresh taste preferences from recent activity
    try:
        import agent_actions as _aa
        _aa.analyze_taste_preferences(project_id, developer_id=project_id)
    except Exception as exc:
        logger.debug("on_commit: taste preferences refresh skipped — %s", exc)


def on_session_end(project_id: str, session_id: str) -> None:
    """
    Fired when a developer session ends (db/client.end_session triggers this).

    Uses the lightweight trigger→action path in planner.py instead of the
    full orchestrator loop, so this stays fast and never blocks the session.
    """
    logger.info(
        "on_session_end trigger fired | project=%s session=%s",
        project_id,
        session_id,
    )

    if not _should_fire("on_session_end", project_id):
        return

    _log_trigger_event("on_session_end", project_id, {
        "session_id": session_id,
    })

    context = {
        "project_id": project_id,
        "session_id": session_id,
    }

    try:
        from decision_engine.planner import plan
        plan_result = plan("on_session_end", context)
        logger.info(
            "on_session_end actions executed | project=%s actions=%d",
            project_id,
            len(plan_result.get("actions", [])),
        )
    except Exception as exc:
        logger.warning("on_session_end: plan failed — %s", exc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _log_trigger_event(trigger: str, project_id: str, context: dict[str, Any]) -> None:
    """Log a trigger event to decision_log for provenance tracking."""
    try:
        from db.client import insert_decision
        decision_text = f"Trigger '{trigger}' fired for project {project_id}"
        rationale = (
            f"Trigger '{trigger}' was detected automatically. "
            f"Context: {context}. "
            "This is a passive trigger — reversible actions are auto-executed, "
            "environment-changing actions are only suggested."
        )
        insert_decision(project_id, decision_text, rationale)
    except Exception as exc:
        logger.warning("Failed to log trigger event to decision_log — %s", exc)
