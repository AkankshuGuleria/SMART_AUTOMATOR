"""workflow_engine/schema.py — AUTOMATA Workflow Engine: data models.

Owns:    WorkflowDefinition, Step, WorkflowRun, WorkflowStep dataclasses/pydantic models.
Never:   Must not call Bedrock or CockroachDB directly.
Ref:     docs/ACTION_POLICIES.md, docs/WORKFLOW_ENGINE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StepDefinition:
    """A single step in a workflow definition."""

    id: str
    tool: str
    inputs: dict[str, Any] = field(default_factory=dict)
    on_error: str = "abort"  # abort | skip | fallback


@dataclass(frozen=True)
class WorkflowDefinition:
    """A static, named, versioned workflow definition loaded from YAML/JSON."""

    id: str
    name: str
    description: str
    version: int
    inputs: list[dict[str, Any]] = field(default_factory=list)
    steps: list[StepDefinition] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionContext:
    """Accumulated state of a workflow run, passed step-to-step."""

    inputs: dict[str, Any] = field(default_factory=dict)
    step_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    retrieved_memories: list[dict[str, Any]] = field(default_factory=list)
    redactions: list[dict[str, Any]] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)


@dataclass
class WorkflowRun:
    """One execution instance of a Workflow Definition."""

    id: str
    workflow_id: str
    workflow_version: int
    status: str  # created | running | completed | failed | awaiting_approval | paused | cancelled
    inputs: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    completed_at: str | None = None
    initiated_by: str = "user"
    project_id: str = ""


@dataclass
class WorkflowStep:
    """One step within a workflow run."""

    id: str
    run_id: str
    step_def_id: str
    tool: str
    policy: str = "auto_execute"
    status: str = "pending"  # pending | running | succeeded | failed | waiting_for_approval | approved | rejected
    rendered_inputs: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    redactions: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
