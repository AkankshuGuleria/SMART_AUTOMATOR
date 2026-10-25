"""workflow_engine/gate_resolver.py — AUTOMATA Workflow Engine: gate position resolver.

Owns:    Pure function that computes gate positions from a step sequence + tool policies.
Never:   No side effects, no I/O, fully unit-testable in isolation.
Ref:     WORKFLOW_ENGINE.md §2, §10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decision_engine.tools import Tool
    from workflow_engine.schema import StepDefinition


def _policy_for(tool: Tool | dict | None) -> str:
    if tool is None:
        return "auto_execute"
    if isinstance(tool, dict):
        return str(tool.get("policy", "auto_execute"))
    return getattr(tool, "policy", "auto_execute")


def resolve_gates(
    steps: list[StepDefinition],
    tool_registry: dict[str, Tool],
) -> list[int]:
    """
    Pure function: given a list of step definitions and the tool registry,
    compute the indices where execution must pause for user approval.

    Composition rule (from WORKFLOW_ENGINE.md §2):
    A workflow pauses at a gate immediately before the first step in a
    contiguous sequence whose policy is confirm_once or require_approval.
    Each separate contiguous run of gated steps gets its own gate.
    Steps with policy "auto_execute" break contiguity, so a later gated
    step after an auto_execute step always gets a fresh gate — an
    earlier approval never authorizes a later, non-contiguous
    require_approval action.

    Risk tiers (ascending):
      auto_execute  <  confirm_once  <  require_approval

    Returns:
        List of step indices where gates should be placed.
    """
    gates: list[int] = []
    i = 0
    while i < len(steps):
        step = steps[i]
        tool = tool_registry.get(step.tool)
        policy = _policy_for(tool)

        if policy in ("confirm_once", "require_approval"):
            # Gate before the first step of this contiguous gated block.
            gates.append(i)
            i += 1
            # After approval, continue through same or lower risk tiers.
            # Stop when we hit auto_execute (breaks contiguity) or a
            # higher tier (which needs its own approval).
            while i < len(steps):
                next_tool = tool_registry.get(steps[i].tool)
                next_policy = _policy_for(next_tool)
                if next_policy == "auto_execute":
                    break  # auto breaks contiguity — new gate needed
                elif next_policy == policy:
                    i += 1  # same tier — continue
                elif next_policy == "confirm_once" and policy == "require_approval":
                    i += 1  # lower tier — continue
                elif next_policy == "require_approval" and policy == "confirm_once":
                    break  # higher tier — new gate needed
                else:
                    i += 1
        else:
            i += 1

    return gates
