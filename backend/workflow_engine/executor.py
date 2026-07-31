"""
workflow_engine/executor.py — AUTOMATA Workflow Engine: step-by-step execution.

Owns:    Running a WorkflowRun step by step; owns the gate logic
         from WORKFLOW_ENGINE.md §2; coordinates with the tool
         registry, checkpoint store, and decision log.
Never:   Must not call OS-level code directly. Every effect goes
         through decision_engine/tools.py, exactly as single-action
         requests do today. The workflow engine is purely a
         sequencing and gating layer.
Ref:     WORKFLOW_ENGINE.md §3, §5, §7, §10.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from db.client import (
    get_workflow_run,
    get_workflow_runs,
    get_workflow_steps,
    insert_decision,
    insert_workflow_run,
    insert_workflow_step,
    update_workflow_run_status,
    update_workflow_step,
)
from decision_engine.tools import execute_tool, get_tool, get_tool_descriptions
from workflow_engine.checkpoint_store import (
    list_checkpoints,
    load_checkpoint,
    save_checkpoint,
)
from workflow_engine.context import (
    ExecutionContext,
    check_privacy_guardrail,
    redact_content,
    resolve_template,
)
from workflow_engine.gate_resolver import resolve_gates
from workflow_engine.registry import get_definition
from workflow_engine.schema import (
    StepDefinition,
    WorkflowDefinition,
    WorkflowRun,
)

logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Executes a WorkflowRun step by step with gate logic."""

    def __init__(self) -> None:
        self._tool_registry = {t["name"]: t for t in get_tool_descriptions()}
        # Build a proper Tool-like lookup for gate_resolver
        self._tools_by_name: dict[str, Any] = {}
        for t in get_tool_descriptions():
            self._tools_by_name[t["name"]] = t

    def start(
        self,
        workflow_id: str,
        inputs: dict[str, Any],
        project_id: str,
        initiated_by: str = "user",
    ) -> WorkflowRun:
        """Start a new workflow run."""
        definition = get_definition(workflow_id)
        if definition is None:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Persist to DB
        try:
            inputs_json = json.dumps(inputs)
            db_run_id = insert_workflow_run(
                workflow_id=definition.id,
                workflow_version=definition.version,
                inputs_json=inputs_json,
                project_id=project_id,
                initiated_by=initiated_by,
            )
            if db_run_id:
                run_id = db_run_id
        except Exception as exc:
            logger.warning("workflow_executor: DB insert failed in start — %s", exc)

        run = WorkflowRun(
            id=run_id,
            workflow_id=definition.id,
            workflow_version=definition.version,
            status="running",
            inputs=inputs,
            started_at=now,
            initiated_by=initiated_by,
            project_id=project_id,
        )

        # Resolve gates from the definition
        gates = resolve_gates(definition.steps, self._tools_by_name)

        # Execute steps up to the first gate (or all if no gates)
        self._execute_steps(definition, run, gates, inputs)

        return run

    def resume(self, run_id: str) -> WorkflowRun:
        """Resume a paused workflow run from the last checkpoint."""
        logger.info("workflow_executor: resume | run=%s", run_id)

        # Load all checkpoints for this run, pick the latest
        checkpoints = list_checkpoints(run_id)
        if not checkpoints:
            raise ValueError(f"No checkpoint found for run {run_id}")

        # The latest checkpoint filename is {run_id}_{step_id}.ckpt
        last_checkpoint = checkpoints[-1]
        step_id = Path(last_checkpoint).stem.replace(f"{run_id}_", "")
        context = load_checkpoint(run_id, step_id)
        if context is None:
            raise ValueError(f"Failed to load checkpoint for run {run_id}, step {step_id}")

        # Reconstruct the run from DB
        run = self._reconstruct_run_from_db(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found in DB")

        definition = get_definition(run.workflow_id)
        if definition is None:
            raise ValueError(f"Unknown workflow: {run.workflow_id}")

        # Find the index of the last checkpointed step, continue from next
        gate_set = set()
        resume_from = 0
        for i, step_def in enumerate(definition.steps):
            if step_def.id == step_id:
                resume_from = i + 1
                break

        # Resolve gates again
        gates = resolve_gates(definition.steps, self._tools_by_name)
        gate_set = set(gates)

        # Resume execution from resume_from
        self._execute_steps_from(definition, run, gate_set, context, resume_from)

        return run

    def approve_gate(self, run_id: str, approved_by: str) -> WorkflowRun:
        """Approve a pending gate and continue execution."""
        logger.info("workflow_executor: approve_gate | run=%s by=%s", run_id, approved_by)

        run = self._reconstruct_run_from_db(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found in DB")

        definition = get_definition(run.workflow_id)
        if definition is None:
            raise ValueError(f"Unknown workflow: {run.workflow_id}")

        # Find the step that's waiting for approval
        db_steps = get_workflow_steps(run_id)

        # Update the waiting step to approved
        if db_steps:
            for db_step in db_steps:
                if db_step.get("status") == "waiting_for_approval":
                    now = datetime.now(timezone.utc).isoformat()
                    update_workflow_step(
                        db_step["id"],
                        status="approved",
                        approved_by=approved_by,
                        approved_at=now,
                    )

        # Restore run to running
        update_workflow_run_status(run_id, "running")

        # Load checkpoint and resume execution
        checkpoints = list_checkpoints(run_id)
        if not checkpoints:
            raise ValueError(f"No checkpoint found for run {run_id}")
        step_id = Path(checkpoints[-1]).stem.replace(f"{run_id}_", "")
        context = load_checkpoint(run_id, step_id)
        if context is None:
            raise ValueError(f"Failed to load checkpoint for run {run_id}")

        gates = resolve_gates(definition.steps, self._tools_by_name)
        gate_set = set(gates)

        # Find resume position from checkpoint
        resume_from = 0
        for i, step_def in enumerate(definition.steps):
            if step_def.id == step_id:
                resume_from = i + 1
                break

        self._execute_steps_from(definition, run, gate_set, context, resume_from)

        return run

    def reject_gate(self, run_id: str, reason: str | None = None) -> WorkflowRun:
        """Reject a pending gate and cancel the run."""
        logger.info("workflow_executor: reject_gate | run=%s reason=%s", run_id, reason)

        run = self._reconstruct_run_from_db(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found in DB")

        run.status = "cancelled"
        now = datetime.now(timezone.utc).isoformat()
        try:
            update_workflow_run_status(run_id, "cancelled", now)
        except Exception as exc:
            logger.warning("workflow_executor: DB update failed in reject_gate — %s", exc)

        # Mark waiting steps as rejected
        db_steps = get_workflow_steps(run_id)
        for db_step in db_steps:
            if db_step.get("status") == "waiting_for_approval":
                try:
                    update_workflow_step(db_step["id"], status="rejected")
                except Exception:
                    pass

        run.completed_at = now
        return run

    def cancel(self, run_id: str, reason: str | None = None) -> WorkflowRun:
        """Cancel a running workflow run."""
        logger.info("workflow_executor: cancel | run=%s reason=%s", run_id, reason)

        run = self._reconstruct_run_from_db(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found in DB")

        run.status = "cancelled"
        now = datetime.now(timezone.utc).isoformat()
        try:
            update_workflow_run_status(run_id, "cancelled", now)
        except Exception as exc:
            logger.warning("workflow_executor: DB update failed in cancel — %s", exc)

        # Mark running/pending steps as cancelled
        db_steps = get_workflow_steps(run_id)
        for db_step in db_steps:
            if db_step.get("status") in ("pending", "running", "waiting_for_approval"):
                try:
                    update_workflow_step(db_step["id"], status="rejected")
                except Exception:
                    pass

        run.completed_at = now
        return run

    def get_run(self, run_id: str) -> WorkflowRun | None:
        """Get a workflow run by ID."""
        return self._reconstruct_run_from_db(run_id)

    def list_runs(
        self, project_id: str, status: str | None = None
    ) -> list[WorkflowRun]:
        """List workflow runs for a project."""
        try:
            rows = get_workflow_runs(project_id, status)
        except Exception as exc:
            logger.warning("workflow_executor: list_runs DB failed — %s", exc)
            return []

        runs: list[WorkflowRun] = []
        for row in rows:
            inputs = {}
            try:
                inputs = json.loads(row.get("inputs_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                pass

            run = WorkflowRun(
                id=row["id"],
                workflow_id=row["workflow_id"],
                workflow_version=row["workflow_version"],
                status=row["status"],
                inputs=inputs,
                started_at=row.get("started_at", ""),
                completed_at=row.get("completed_at"),
                initiated_by=row.get("initiated_by", "user"),
                project_id=row.get("project_id", project_id),
            )
            runs.append(run)

        return runs

    # ─── Internal execution ──────────────────────────────────

    def _reconstruct_run_from_db(self, run_id: str) -> WorkflowRun | None:
        """Reconstruct a WorkflowRun dataclass from DB row."""
        try:
            row = get_workflow_run(run_id)
        except Exception:
            return None
        if row is None:
            return None
        inputs = {}
        try:
            inputs = json.loads(row.get("inputs_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass
        return WorkflowRun(
            id=row["id"],
            workflow_id=row["workflow_id"],
            workflow_version=row["workflow_version"],
            status=row["status"],
            inputs=inputs,
            started_at=row.get("started_at", ""),
            completed_at=row.get("completed_at"),
            initiated_by=row.get("initiated_by", "user"),
            project_id=row.get("project_id", ""),
        )

    def _execute_steps(
        self,
        definition: WorkflowDefinition,
        run: WorkflowRun,
        gates: list[int],
        inputs: dict[str, Any],
    ) -> None:
        """Execute steps up to the first gate, or all steps if no gates."""
        context = ExecutionContext(inputs=inputs)
        self._execute_steps_from(definition, run, set(gates), context, 0)

    def _execute_steps_from(
        self,
        definition: WorkflowDefinition,
        run: WorkflowRun,
        gate_set: set[int],
        context: ExecutionContext,
        start_index: int,
    ) -> None:
        """Execute steps starting from a given index, pausing at gates."""
        for i in range(start_index, len(definition.steps)):
            step_def = definition.steps[i]

            if i in gate_set:
                run.status = "awaiting_approval"
                logger.info(
                    "workflow_executor: paused at gate | run=%s step_index=%d tool=%s",
                    run.id, i, step_def.tool,
                )
                save_checkpoint(run.id, step_def.id, context)
                try:
                    update_workflow_run_status(run.id, "awaiting_approval")
                except Exception as exc:
                    logger.warning("workflow_executor: DB status update failed — %s", exc)
                return

            self._execute_step(step_def, run, context, definition)

        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc).isoformat()
        try:
            update_workflow_run_status(run.id, "completed", run.completed_at)
        except Exception as exc:
            logger.warning("workflow_executor: DB status update failed — %s", exc)
        logger.info("workflow_executor: completed | run=%s", run.id)

    def _execute_step(
        self,
        step_def: StepDefinition,
        run: WorkflowRun,
        context: ExecutionContext,
        definition: WorkflowDefinition,
    ) -> None:
        """Execute a single workflow step."""
        tool_name = step_def.tool
        tool = get_tool(tool_name)

        # Determine policy from tool registry
        policy = "auto_execute"
        if tool_name in self._tool_registry:
            registry_tool = self._tool_registry[tool_name]
            if hasattr(registry_tool, "policy"):
                policy = registry_tool.policy
            elif isinstance(registry_tool, dict) and "policy" in registry_tool:
                policy = registry_tool["policy"]

        # Insert step into DB
        step_db_id = None
        try:
            step_db_id = insert_workflow_step(
                run_id=run.id,
                step_def_id=step_def.id,
                tool=tool_name,
                policy=policy,
                rendered_inputs_json=None,
                output_json=None,
                redactions_json=None,
            )
        except Exception as exc:
            logger.warning("workflow_executor: insert_workflow_step failed — %s", exc)

        if tool is None:
            logger.error("workflow_executor: unknown tool | run=%s step=%s tool=%s", run.id, step_def.id, tool_name)
            if step_db_id:
                try:
                    update_workflow_step(step_db_id, status="failed")
                except Exception:
                    pass
            if step_def.on_error == "abort":
                run.status = "failed"
                try:
                    update_workflow_run_status(run.id, "failed")
                except Exception:
                    pass
                return
            elif step_def.on_error == "skip":
                if step_db_id:
                    try:
                        update_workflow_step(step_db_id, status="failed")
                    except Exception:
                        pass
                return
            return

        # Resolve templated inputs
        rendered_inputs: dict[str, Any] = {}
        for key, value in step_def.inputs.items():
            if isinstance(value, str) and "{{" in value:
                rendered_inputs[key] = resolve_template(value, {
                    "inputs": context.inputs,
                    "step_outputs": context.step_outputs,
                })
            else:
                rendered_inputs[key] = value

        # Check privacy guardrail on rendered inputs
        input_text = str(rendered_inputs)
        if check_privacy_guardrail(input_text):
            redacted, was_redacted = redact_content(input_text)
            if was_redacted:
                context.redactions.append({
                    "step_id": step_def.id,
                    "tool": tool_name,
                    "redacted_at": datetime.now(timezone.utc).isoformat(),
                })
                rendered_inputs = {"text": redacted}

        # Execute the tool
        try:
            result = execute_tool(tool_name, rendered_inputs)
            context.step_outputs[step_def.id] = result

            # Update step as succeeded
            output_json = None
            try:
                output_json = json.dumps(result)
            except (TypeError, ValueError):
                output_json = json.dumps({"raw": str(result)})
            if step_db_id:
                try:
                    now = datetime.now(timezone.utc).isoformat()
                    update_workflow_step(
                        step_db_id,
                        status="succeeded",
                        output_json=output_json,
                    )
                except Exception:
                    pass

            # Log to decision_log
            try:
                insert_decision(
                    project_id=run.project_id,
                    decision=f"Workflow step {step_def.id}: {tool_name}",
                    rationale=f"Workflow {definition.id} v{definition.version}, step {step_def.id}",
                )
            except Exception:
                pass  # Don't fail the step if logging fails

            # Save checkpoint after step
            save_checkpoint(run.id, step_def.id, context)

        except Exception as exc:
            logger.error("workflow_executor: step failed | run=%s step=%s error=%s", run.id, step_def.id, exc)
            if step_db_id:
                try:
                    now = datetime.now(timezone.utc).isoformat()
                    update_workflow_step(step_db_id, status="failed", completed_at=now)
                except Exception:
                    pass
            if step_def.on_error == "abort":
                run.status = "failed"
                try:
                    update_workflow_run_status(run.id, "failed")
                except Exception:
                    pass
            elif step_def.on_error == "skip":
                pass  # Continue to next step
