"""workflow_engine/gate_resolver.py — AUTOMATA Workflow Engine: gate position resolver.

Owns:    Pure function that computes gate positions from a step sequence + tool policies.
Never:   No side effects, no I/O, fully unit-testable in isolation.
Ref:     WORKFLOW_ENGINE.md §2, §10.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decision_engine.tools import Tool


def resolve_gates(
    steps: list[StepDefinition],
    tool_registry: dict[str, Tool],
) -> list[int]:
    """
    Pure function: given a list of step definitions and the tool registry,
    compute the indices where execution must pause for user approval.

    Composition rule (from WORKFLOW_ENGINE.md §2):
    A workflow pauses at a gate immediately before the first step in a
    contiguous sequence whose policy is confirm_once or require_approval,
    and does not resume automatically past it. Once approved, execution
    continues through any immediately-following steps of the same or lower
    risk tier without additional prompts, until the next tier increase.

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
        policy = tool.policy if tool else "auto_execute"

        if policy in ("confirm_once", "require_approval"):
            gates.append(i)
            i += 1
            # After approval, continue through same or lower risk tiers.
            # Stop when we hit a higher risk tier.
            while i < len(steps):
                next_tool = tool_registry.get(steps[i].tool)
                next_policy = next_tool.policy if next_tool else "auto_execute"
                if next_policy == "auto_execute":
                    # Lower tier — continue
                    i += 1
                elif next_policy == policy:
                    # Same tier — continue
                    i += 1
                elif next_policy == "confirm_once" and policy == "require_approval":
                    # Lower tier (confirm_once < require_approval) — continue
                    i += 1
                elif next_policy == "require_approval" and policy == "confirm_once":
                    # Higher tier — stop and place new gate
                    break
                else:
                    i += 1
        else:
            i += 1

    return gates
