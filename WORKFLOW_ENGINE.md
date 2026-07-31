# WORKFLOW_ENGINE.md - Multi-Step Workflow Engine Spec

## 0. Why This Exists

Today every AUTOMATA action is evaluated and approved independently. That is
correct for single actions, but real work is rarely one action. "Review this
PR" is a chain: read diff, check memory, draft summary, then post comment.
Those steps have different risk levels.

Without a workflow layer, the product gets one of two bad outcomes:

- Every step interrupts the user for approval.
- A broad action gets quietly widened to `auto_execute` to reduce friction.

The workflow engine exists to let multiple tool calls execute as one coherent
unit, with approval checkpoints collapsed to the minimum number the risk
profile actually requires: never fewer, never more.

This slots into the module boundaries already defined in `FEATURES_PHASE.md`
without renaming or restructuring existing modules.

## 1. Core Concepts

| Term | Definition |
|---|---|
| **Workflow Definition** | Static, named, versioned description of an ordered or branching sequence of steps. Stored as data, not code. |
| **Workflow Run** | One execution instance of a workflow definition, with its own state, inputs, and outputs. |
| **Step** | A single unit of work. A step wraps exactly one registered tool call from `decision_engine/tools.py` or one sub-workflow. |
| **Gate** | A point where execution pauses for user approval before continuing. Gates are derived, not authored. |
| **Execution Context** | Accumulated run state: inputs, step outputs, retrieved memory, redaction decisions, and timing. |
| **Checkpoint** | Persisted snapshot of execution context after a step, enabling pause/resume/rollback. |

A workflow run is the unit that appears in the approval queue and audit UI. The
user approves runs at their gates, not raw tool calls.

## 2. Relationship To The Existing Policy Model

The engine does not introduce a new policy system. It composes the existing
three tiers every individual tool declares:

- `auto_execute`
- `confirm_once`
- `require_approval`

Composition rule:

> A workflow run pauses at a gate immediately before the first step in a
> contiguous sequence whose policy is `confirm_once` or `require_approval`.
> Once approved, execution continues through immediately-following steps of
> the same or lower risk tier without additional prompts, until the next tier
> increase.

Example:

```text
1. read_git_diff        auto_execute
2. check_mistake_log    auto_execute
3. draft_pr_summary     auto_execute
--- gate: require_approval
4. post_pr_comment      require_approval
5. verify_result        auto_execute
```

Steps 1-3 run without interruption. Step 4 needs one approval because it is
externally visible. Step 5 does not need a second gate because it only verifies
the already-approved action.

Escalation exception:

If rendered inputs for an `auto_execute` or `confirm_once` step contain
secrets, code, private URLs, or sensitive project context that was not known
when the run started, the step is force-escalated to `require_approval`. This
is evaluated at step-execution time because upstream steps may generate the
content.

## 3. Module Boundaries

The workflow engine is a coordination layer between the planner and tool
registry. It does not replace either.

```text
backend/workflow_engine/
    __init__.py
    schema.py             # WorkflowDefinition, StepDefinition, WorkflowRun models
    registry.py           # load/validate/list registered workflow definitions
    executor.py           # runs workflows step by step; owns gate flow
    gate_resolver.py      # pure function for gate positions
    context.py            # ExecutionContext serialization and redaction hooks
    checkpoint_store.py   # persist/restore context snapshots
    definitions/          # YAML/JSON workflow definitions
```

Touched modules:

- `backend/decision_engine/tools.py`
  Existing tool registry. Workflow steps call registered tools only.

- `backend/decision_engine/planner.py`
  Existing planner can select workflows or individual tools.

- `backend/agent_actions.py`
  Existing composed product actions become the first workflow definitions.

- `backend/db/client.py`
  Adds persistence functions for workflow runs and steps when implemented.

Non-negotiable boundary:

`workflow_engine/executor.py` never calls OS-level code directly. Every effect
goes through `decision_engine/tools.py`. The workflow engine is only a
sequencing and gating layer.

## 4. Workflow Definition Schema

Definitions are data, preferably YAML or JSON, so they can be listed, diffed,
and edited without code changes.

```yaml
id: chatgpt_prompt_handoff_v1
name: "ChatGPT prompt handoff"
description: >
  Generate a prompt from project memory, copy it, open ChatGPT,
  then paste only after user approval.
version: 1
inputs:
  - name: user_goal
    type: string
    required: true
steps:
  - id: generate_prompt
    tool: generate_prompt
    inputs:
      goal: "{{ inputs.user_goal }}"
    on_error: abort
  - id: copy_prompt
    tool: copy_to_clipboard
    inputs:
      text: "{{ steps.generate_prompt.output.text }}"
    on_error: abort
  - id: open_chatgpt
    tool: open_url
    inputs:
      url: "https://chatgpt.com"
    on_error: skip
  - id: paste_prompt
    tool: paste_clipboard
    inputs:
      expected_target: "chatgpt"
    on_error: abort
  - id: log_handoff
    tool: record_decision
    inputs:
      decision: "Prompt handed off to ChatGPT"
      rationale: "{{ steps.generate_prompt.output.text }}"
    on_error: skip
outputs:
  - name: prompt
    from: steps.generate_prompt.output.text
```

Field notes:

- `tool` must reference a tool already registered in `decision_engine/tools.py`.
- `on_error` is per step: `abort`, `skip`, or `fallback`.
- Templated inputs resolve from the execution context at run time.
- Gates are computed from tool policies, not declared in the definition.

## 5. Step And Run State Machines

Step states:

```text
pending -> running -> succeeded
                    -> failed -> (abort | skipped | retried)
         -> waiting_for_approval -> approved -> running
                                  -> rejected -> run cancelled
```

Run states:

```text
created -> running -> completed
                    -> failed
                    -> awaiting_approval -> running
                                      -> cancelled
        -> paused -> running
```

A run in `awaiting_approval` carries:

- the step it is paused before
- rendered inputs the step will receive
- redactions already applied
- the reason approval is required

## 6. Persistence

Two new tables are needed when this is implemented. They are additive to
`decision_log` and `mistake_log`, not replacements.

```sql
CREATE TABLE workflow_runs (
    id               TEXT PRIMARY KEY,
    workflow_id      TEXT NOT NULL,
    workflow_version INTEGER NOT NULL,
    status           TEXT NOT NULL,
    inputs_json      TEXT NOT NULL,
    started_at       TIMESTAMPTZ NOT NULL,
    completed_at     TIMESTAMPTZ,
    initiated_by     TEXT NOT NULL,
    project_id       UUID NOT NULL
);

CREATE TABLE workflow_steps (
    id                   TEXT PRIMARY KEY,
    run_id               TEXT NOT NULL REFERENCES workflow_runs(id),
    step_def_id          TEXT NOT NULL,
    tool                 TEXT NOT NULL,
    policy               TEXT NOT NULL,
    status               TEXT NOT NULL,
    rendered_inputs_json TEXT,
    output_json          TEXT,
    redactions_json      TEXT,
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ,
    approved_by          TEXT,
    approved_at          TIMESTAMPTZ
);
```

Every completed step also writes a normal entry to `decision_log`, tagged with
`run_id`. The workflow tables are structured indexes; `decision_log` remains
the human-readable narrative.

## 7. Checkpointing, Pause, Resume, Rollback

- After every step, persist the execution context.
- Resume from the last checkpoint and never re-run completed steps implicitly.
- Retry of a completed step is always explicit.
- Rollback is scoped per step and only offered when the tool registered a
  pre-write snapshot.
- Cancelling at a gate marks the run `cancelled`, logs the reason, and performs
  no destructive cleanup by itself.

Rollback is useful but not required for the first MVP slice unless the workflow
performs file writes.

## 8. Triggers

Triggers can create workflow runs, but they do not bypass gates.

```yaml
trigger:
  id: on_test_failure
  workflow: diagnose_and_summarize_failure_v1
  event: test_suite.failed
  policy_override: confirm_once_first_time
```

`confirm_once_first_time` means the first trigger initiation asks permission to
start that workflow automatically in the future. Internal step gates still
apply every time.

Triggers are valuable but should be after the first manual workflow slice.

## 9. Migration Path For Existing Agent Actions

Existing hand-written chains in `agent_actions.py` should become the first
workflow definitions over time:

1. Create an equivalent `.yaml` definition in
   `backend/workflow_engine/definitions/`.
2. Keep the existing direct-call path until the workflow version passes
   equivalence tests.
3. Turn the existing `agent_actions.py` function into a thin wrapper around
   `WorkflowExecutor.start(...)`.

Direct single-tool calls remain untouched. The workflow engine is additive for
multi-step work, not mandatory indirection for everything.

## 10. API Surface

```python
class WorkflowExecutor:
    def start(
        self,
        workflow_id: str,
        inputs: dict,
        project_id: str,
        initiated_by: str = "user",
    ) -> WorkflowRun: ...

    def resume(self, run_id: str) -> WorkflowRun: ...

    def approve_gate(self, run_id: str, approved_by: str) -> WorkflowRun: ...

    def reject_gate(self, run_id: str, reason: str | None = None) -> WorkflowRun: ...

    def cancel(self, run_id: str, reason: str | None = None) -> WorkflowRun: ...

    def get_run(self, run_id: str) -> WorkflowRun: ...

    def list_runs(self, project_id: str, status: str | None = None) -> list[WorkflowRun]: ...
```

```python
def resolve_gates(
    steps: list[StepDefinition],
    tool_registry: ToolRegistry,
) -> list[GatePosition]:
    """Return gate positions from step policies as a pure function."""
```

`resolve_gates` should have the heaviest unit test coverage because it is the
safety boundary that decides when the user is asked for permission.

## 11. Concurrency

- One active run per `(project_id, workflow_id)` by default.
- Starting another run of the same workflow on the same project queues or
  rejects rather than parallel-executes.
- Different workflows or different projects may execute concurrently later.
- MVP should not build general parallel workflow execution.

## 12. Testing Requirements

- Table-driven gate resolver tests over policy sequences.
- Escalation-on-content tests.
- Checkpoint/resume tests with simulated interruption.
- Cancellation tests proving no destructive action happens automatically.
- Migration-equivalence tests for converted `agent_actions.py` flows.
- Concurrency test for one active run per project/workflow.

Rollback and trigger tests can wait until those parts are implemented.

## 13. MVP Slice

Build the workflow engine through one real vertical slice first:

```text
chatgpt_prompt_handoff_v1:
retrieve memory -> generate prompt -> copy clipboard -> open ChatGPT
-> approval gate -> paste -> verify -> log decision
```

This proves:

- workflow definitions can compose existing tools
- gates are derived from risk policy
- generated content can be previewed before external handoff
- approval is required before pasting/submitting externally
- the run is auditable through `decision_log`

Do not block final UI polish on branching workflows, triggers, rollback, PR
comments, or full concurrency.

## 14. Definition Of Done

- [ ] Workflow definitions are data, loaded and validated by `registry.py`.
- [ ] `gate_resolver.py` implements the composition rule as a pure function.
- [ ] Escalation-on-content can only raise risk, never lower it.
- [ ] A workflow run pauses before external paste/submission.
- [ ] Every completed step writes a structured step record and a decision log
      entry.
- [ ] Checkpointing persists after every step in the MVP workflow.
- [ ] Cancellation at a gate performs no destructive action by itself.
- [ ] `chatgpt_prompt_handoff_v1` exists as a real definition.
- [ ] Tests cover gate resolution, approval pauses, cancellation, and the MVP
      workflow's expected tool sequence.
