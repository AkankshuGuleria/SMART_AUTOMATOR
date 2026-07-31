"""workflow_engine/triggers.py — AUTOMATA Workflow Engine: trigger-based run initiation.

Owns:    Scheduled and event-based workflow run initiation.
Never:   Must not bypass the gate model — triggers only waive the
         initiation confirmation, never internal step gates.
Ref:     WORKFLOW_ENGINE.md §8.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from workflow_engine.executor import WorkflowExecutor

logger = logging.getLogger(__name__)


@dataclass
class TriggerConfig:
    """Configuration for a workflow trigger."""
    id: str
    workflow: str
    event: str
    policy_override: str = "confirm_once_first_time"  # confirm_once_first_time | auto_execute


class TriggerManager:
    """Manages workflow triggers and their confirmation state."""

    def __init__(self) -> None:
        self._triggers: dict[str, TriggerConfig] = {}
        self._confirmed_triggers: set[str] = set()

    def register(self, config: TriggerConfig) -> None:
        self._triggers[config.id] = config

    def confirm_trigger(self, trigger_id: str) -> None:
        """Mark a trigger as confirmed so subsequent firings skip initiation confirmation."""
        self._confirmed_triggers.add(trigger_id)
        logger.info("trigger_manager: confirmed trigger | id=%s", trigger_id)

    def is_confirmed(self, trigger_id: str) -> bool:
        return trigger_id in self._confirmed_triggers

    def needs_confirmation(self, trigger_id: str) -> bool:
        """Returns True if this trigger firing requires initiation confirmation."""
        config = self._triggers.get(trigger_id)
        if config is None:
            return True
        # confirm_once_first_time: first time needs confirmation, subsequent don't
        if config.policy_override == "confirm_once_first_time":
            return not self.is_confirmed(trigger_id)
        return False

    def fire(self, trigger_id: str, executor: WorkflowExecutor, inputs: dict[str, Any] = None) -> dict[str, Any]:
        """
        Fire a trigger to start a workflow run.

        If the trigger requires confirmation and hasn't been confirmed yet,
        returns a pending response asking for confirmation.
        """
        config = self._triggers.get(trigger_id)
        if config is None:
            return {"success": False, "error": f"Unknown trigger: {trigger_id}"}

        if self.needs_confirmation(trigger_id):
            return {
                "success": False,
                "pending_confirmation": True,
                "trigger_id": trigger_id,
                "workflow": config.workflow,
                "message": f"Trigger '{trigger_id}' wants to start workflow '{config.workflow}'. Confirm to proceed.",
            }

        # Trigger is confirmed — start the workflow
        return executor.start(config.workflow, inputs or {}, initiated_by=f"trigger:{trigger_id}")
