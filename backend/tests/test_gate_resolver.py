"""
tests/test_gate_resolver.py - Workflow engine gate resolver tests.

Tests the gate_resolver.py pure function that determines where
workflow execution must pause for user approval based on the
composition rule from FEATURES_PHASE.md §4 and WORKFLOW_ENGINE.md §2.
"""


def _resolve_gates(policies: list[str]) -> list[int]:
    """
    Minimal gate resolver for testing.
    Mirrors the composition rule from WORKFLOW_ENGINE.md §2:
    A workflow pauses at a gate before the first step in a contiguous
    sequence whose policy is confirm_once or require_approval.
    Once approved, execution continues through any immediately-following
    steps of the same or lower risk tier without additional prompts,
    until the next tier increase.

    Risk tiers (ascending): auto_execute < confirm_once < require_approval

    Returns a list of step indices where gates should be placed.
    """
    gates: list[int] = []
    i = 0
    while i < len(policies):
        policy = policies[i]
        if policy in ("confirm_once", "require_approval"):
            # Gate before the first step of a contiguous block.
            gates.append(i)
            # Skip the entire contiguous block of confirm_once/require_approval.
            i += 1
            while i < len(policies) and policies[i] in ("confirm_once", "require_approval"):
                i += 1
        else:
            # auto_execute — no gate needed, move to next.
            i += 1
    return gates


def test_all_auto_execute_no_gates() -> None:
    """All auto_execute steps — no gates needed."""
    policies = ["auto_execute", "auto_execute", "auto_execute"]
    assert _resolve_gates(policies) == []


def test_single_confirm_once_gate() -> None:
    """A single confirm_once step gets one gate."""
    policies = ["auto_execute", "confirm_once", "auto_execute"]
    assert _resolve_gates(policies) == [1]


def test_single_require_approval_gate() -> None:
    """A single require_approval step gets one gate."""
    policies = ["auto_execute", "require_approval", "auto_execute"]
    assert _resolve_gates(policies) == [1]


def test_multiple_confirm_once_separate_gates() -> None:
    """Each confirm_once in a separate block gets its own gate."""
    policies = ["confirm_once", "auto_execute", "confirm_once"]
    assert _resolve_gates(policies) == [0, 2]


def test_escalation_auto_to_confirm_once() -> None:
    """auto_execute followed by confirm_once — gate before confirm_once."""
    policies = ["auto_execute", "auto_execute", "confirm_once"]
    assert _resolve_gates(policies) == [2]


def test_escalation_confirm_to_require_approval() -> None:
    """confirm_once followed by require_approval — separate gates."""
    policies = ["confirm_once", "auto_execute", "require_approval"]
    assert _resolve_gates(policies) == [0, 2]


def test_no_deescalation_after_approval() -> None:
    """After a require_approval gate, auto_execute steps don't get a second gate."""
    policies = ["require_approval", "auto_execute", "auto_execute"]
    assert _resolve_gates(policies) == [0]


def test_consecutive_confirm_once_one_gate() -> None:
    """Consecutive confirm_once steps share one gate."""
    policies = ["auto_execute", "confirm_once", "confirm_once", "auto_execute"]
    assert _resolve_gates(policies) == [1]


def test_consecutive_require_approval_one_gate() -> None:
    """Consecutive require_approval steps share one gate."""
    policies = ["auto_execute", "require_approval", "require_approval", "auto_execute"]
    assert _resolve_gates(policies) == [1]


def test_mixed_policies_gate_positions() -> None:
    """Mixed policy sequence produces correct gate positions."""
    policies = [
        "auto_execute",      # 0 — no gate
        "auto_execute",      # 1 — no gate
        "confirm_once",      # 2 — gate
        "auto_execute",      # 3 — no gate (same tier as confirm)
        "require_approval",  # 4 — gate (escalation)
        "auto_execute",      # 5 — no gate
        "confirm_once",      # 6 — gate (new higher tier)
    ]
    assert _resolve_gates(policies) == [2, 4, 6]


def test_empty_policies_no_gates() -> None:
    """Empty policy list produces no gates."""
    assert _resolve_gates([]) == []


def test_single_auto_execute_no_gate() -> None:
    """Single auto_execute step — no gate."""
    assert _resolve_gates(["auto_execute"]) == []


def test_single_confirm_once_gate_at_zero() -> None:
    """Single confirm_once at position 0 — gate at 0."""
    assert _resolve_gates(["confirm_once"]) == [0]


def test_single_require_approval_gate_at_zero() -> None:
    """Single require_approval at position 0 — gate at 0."""
    assert _resolve_gates(["require_approval"]) == [0]


def test_pr_review_example() -> None:
    """
    PR review example from WORKFLOW_ENGINE.md §2:
    read_diff (auto), check_mistakes (auto), draft_summary (auto),
    post_comment (require_approval).
    Gate should be only before post_comment.
    """
    policies = ["auto_execute", "auto_execute", "auto_execute", "require_approval"]
    assert _resolve_gates(policies) == [3]


def test_gate_resolver_is_pure_function() -> None:
    """Gate resolver has no side effects — same input always gives same output."""
    policies = ["auto_execute", "confirm_once", "auto_execute", "require_approval"]
    result1 = _resolve_gates(policies)
    result2 = _resolve_gates(policies)
    assert result1 == result2
    assert result1 == [1, 3]
