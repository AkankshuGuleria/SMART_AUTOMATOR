# FEATURES_PHASE.md - MVP-Winning Feature Context

This phase exists to turn AUTOMATA from a memory-first developer agent into a
practical automation layer a developer can use in real work. The goal is not to
add broad "Jarvis" behavior. The goal is to add narrow, useful, auditable
cross-app actions that make the persistent memory engine immediately valuable.

## 1. Feature Phase Goal

AUTOMATA should be able to:

1. Understand a developer's task.
2. Retrieve relevant project memory.
3. Generate a useful prompt, command, summary, or plan.
4. Place that output into the right tool or application.
5. Ask before sending private context outside the local machine.
6. Verify whether the action worked.
7. Store the outcome and rationale back into memory.

The feature phase should preserve the core product story:

```
Observe -> Remember -> Retrieve -> Reason -> Plan -> Act -> Verify -> Learn
```

The new emphasis is the `Act -> Verify` part of the loop.

## 2. Primary Use Case

Example:

> "Make a good prompt for ChatGPT to design this backend feature and copy it."

Expected behavior:

1. AUTOMATA retrieves relevant project context.
2. AUTOMATA drafts a prompt grounded in that context.
3. AUTOMATA previews or returns the prompt.
4. AUTOMATA copies the prompt to the clipboard.
5. If asked, AUTOMATA opens ChatGPT.
6. AUTOMATA asks before pasting or submitting project context into ChatGPT.
7. AUTOMATA logs the prompt handoff in `decision_log`.

This is the smallest useful workflow: generation plus clipboard handoff. It is
safe, demoable, and genuinely useful.

## 3. Cross-App Control Actions

Start with a narrow action set:

| Action | Purpose | Default policy |
|---|---|---|
| `open_app` | Launch a known local application such as VS Code, terminal, browser, Cursor, Claude, or ChatGPT web. | `auto_execute` for known safe apps |
| `open_url` | Open a URL in the default browser. | `auto_execute` for normal URLs |
| `focus_app` | Bring a known existing window to the foreground. | `confirm_once` |
| `copy_to_clipboard` | Copy generated prompts, commit messages, commands, or summaries. | `auto_execute` |
| `paste_clipboard` | Paste clipboard content into the active target app. | `confirm_once` |
| `send_keystroke` | Send limited safe keys such as `Ctrl+V`, `Enter`, `Ctrl+L`, `Alt+Tab`. | `confirm_once` or `require_approval` depending on target |
| `submit_prompt_to_app` | Higher-level flow: generate prompt, open/focus app, copy, paste, optionally submit. | `require_approval` before external submission |
| `verify_result` | Confirm app opened, file changed, command completed, server started, or prompt was copied. | `auto_execute` |

Do not add arbitrary UI clicking or unsupervised screen control in the MVP.

## 4. Safety Model

Use three execution policies:

### `auto_execute`

For low-risk, reversible, local actions:

- copy text to clipboard
- open browser/app
- retrieve memory
- generate prompt
- verify local state

### `confirm_once`

For medium-risk actions where the user should know what will happen:

- paste into an external app
- focus a specific app/window
- start a dev server
- open a project in an editor

### `require_approval`

For high-risk or externally visible actions:

- submit a prompt to ChatGPT, Claude, Cursor, or another external AI
- run shell commands
- write or modify files
- install packages
- commit code
- send messages, emails, or issue comments

Important rule: copying a prompt is safe; submitting that prompt to an external
service is not automatically safe.

## 5. Privacy Guardrail

Before sending content to an external app or AI service, AUTOMATA must check:

- Does the prompt include project memory?
- Does the prompt include code snippets?
- Does the prompt include terminal output?
- Could the content contain credentials, tokens, private URLs, or customer data?

If yes, AUTOMATA must:

1. Redact obvious secrets.
2. Show the action as an external handoff.
3. Ask for approval before submission.
4. Log the handoff in `decision_log`.

## 6. Implementation Boundaries

Keep the existing module boundaries:

- `backend/automation/os_windows.py`
  Low-level Windows operations: clipboard, app launch, URL launch, window focus,
  limited keystrokes.

- `backend/decision_engine/tools.py`
  Tool registry entries: `copy_to_clipboard`, `paste_clipboard`, `open_url`,
  `focus_app`, `submit_prompt_to_app`, `verify_result`.

- `backend/decision_engine/planner.py`
  Policy routing: decide whether an action is `auto_execute`, `confirm_once`,
  or `require_approval`.

- `backend/automation/agent_bridge.py`
  Higher-level external AI/tool handoff with graceful fallback.

- `backend/agent_actions.py`
  Product-level actions that compose lower-level tools into useful developer
  workflows.

The Reasoning Engine generates and plans. The Automation Layer performs OS
actions. The Persistent Memory Engine records what happened.

## 7. MVP Demo Flow

Use this as the feature-phase demo:

1. Ask: "Write a prompt for ChatGPT to help design the next automation feature."
2. AUTOMATA retrieves relevant memory and drafts a specific prompt.
3. AUTOMATA copies the prompt to clipboard.
4. Ask: "Open ChatGPT."
5. AUTOMATA opens ChatGPT in the browser.
6. Ask: "Paste it there."
7. AUTOMATA asks for confirmation because this is an external app handoff.
8. After approval, AUTOMATA pastes the prompt.
9. AUTOMATA logs the handoff and shows provenance.

Stretch demo:

1. User asks: "Ask Cursor to implement this feature."
2. AUTOMATA drafts a grounded coding prompt.
3. AUTOMATA sends it through the external agent bridge.
4. AUTOMATA verifies changed files or test results.
5. AUTOMATA records success or failure into memory.

## 8. Definition Of Done

- [ ] Prompt generation can use project memory without fabricating facts.
- [ ] Generated prompt can be copied to clipboard.
- [ ] ChatGPT/browser can be opened from a natural-language command.
- [ ] Paste/submit actions require confirmation.
- [ ] External handoffs are logged in `decision_log`.
- [ ] Secrets are redacted before prompts are copied or sent externally.
- [ ] Failures are visible and recoverable.
- [ ] Tests cover policy routing and safe/unsafe action classification.

This phase should be built after the major backend/automation features are
stable, and before final UI polish.

## 9. Visual Feedback Layer

This feature lets AUTOMATA use what is visible on screen as context for
debugging, design review, prompt writing, and verification. It should feel like
the agent can understand the developer's current workspace without forcing the
developer to manually copy every error, UI label, or external AI response.

The goal is not full unrestricted screen control. The goal is a safe visual
feedback loop:

```
Capture screen -> OCR/visual analysis -> Reason with memory -> Generate prompt,
fix, review, or action -> Verify again -> Store outcome
```

### Primary Uses

1. Design preview review
   AUTOMATA captures the running frontend, reads visible UI text, checks the
   layout state, and suggests improvements before the final UI polish pass.

2. Prompt writing from visual context
   AUTOMATA looks at a visible design, error, tool response, or app state and
   writes a better prompt for ChatGPT, Cursor, Claude, Figma, or another tool.

3. Frontend QA
   AUTOMATA verifies that expected labels, buttons, panels, and states appear
   after a change.

4. Error debugging
   AUTOMATA reads browser error overlays, terminal output, test failures, and
   stack traces when the user says "look at this error" or "fix what is on my
   screen."

5. External AI response capture
   AUTOMATA can read visible output from ChatGPT/Cursor/Claude, summarize the
   useful result, and store the handoff outcome in memory.

6. Demo verification
   AUTOMATA can check that the demo screen shows the expected state before
   recording or presenting.

### New Tool Actions

| Action | Purpose | Default policy |
|---|---|---|
| `capture_screen` | Capture full screen, active window, or selected region. | `confirm_once` unless user explicitly says to read the screen |
| `ocr_image` | Extract text from a screenshot/image. | `auto_execute` after capture |
| `read_visible_context` | Capture and OCR the current visible workspace. | `confirm_once` |
| `diagnose_visible_error` | Parse visible error text and connect it to project memory. | `confirm_once` |
| `review_visible_design` | Analyze current UI/design preview and generate improvement notes. | `confirm_once` |
| `generate_prompt_from_screen` | Use visible context plus project memory to draft a prompt for another tool. | `auto_execute` for draft, approval required before external submission |
| `verify_visible_result` | Check whether expected UI text/state appears after an action. | `auto_execute` |

### Implementation Boundaries

- `backend/automation/screen_capture.py`
  Captures screen, active window, or selected region on Windows.

- `backend/automation/ocr.py`
  Extracts text from images and redacts secret-shaped strings before storage or
  model handoff.

- `backend/decision_engine/tools.py`
  Registers visual tools such as `capture_screen`, `ocr_image`,
  `read_visible_context`, `diagnose_visible_error`,
  `review_visible_design`, `generate_prompt_from_screen`, and
  `verify_visible_result`.

- `backend/agent_actions.py`
  Composes visual tools into product workflows like "read this error",
  "review this design", and "write a prompt from what is on screen."

- `backend/db/client.py`
  Stores only useful extracted text, summaries, decisions, or mistakes. Do not
  store screenshots by default.

### Privacy Rules

- Ask before screen capture unless the user's command clearly requests it.
- Redact secrets before OCR text is stored or passed into a reasoning prompt.
- Do not persist raw screenshots by default.
- Ask before sending OCR-derived project context to an external AI service.
- Log visual handoffs and decisions in `decision_log`.
- Store recurring visible errors and fixes in `mistake_log`.

### MVP Demo Flow

1. Run the frontend locally.
2. Ask: "Preview this design and write a better prompt for Cursor."
3. AUTOMATA captures the visible app window after confirmation.
4. AUTOMATA extracts visible text and combines it with project memory.
5. AUTOMATA drafts a specific prompt for improving the design.
6. AUTOMATA copies the prompt to the clipboard.
7. AUTOMATA asks before sending the prompt to an external tool.

This feature strengthens the MVP because it connects memory, automation, and
real visible workspace context in a way users can immediately understand.










# WORKFLOW_ENGINE — Extended Draft

Implementation source of truth: `WORKFLOW_ENGINE.md`.

The section below is the broader workflow-engine draft/backlog. For the MVP,
build the smaller vertical slice defined in `WORKFLOW_ENGINE.md` first:
`chatgpt_prompt_handoff_v1` with derived approval gates, checkpointing,
verification, and decision-log provenance.

## 0. Why this exists

Today every AUTOMATA action is evaluated and approved independently. That's
correct for single actions but breaks down for real work, which is rarely one
action — "review this PR" is *read diff → check memory → draft summary → post
comment*, four tool calls with very different risk levels. Without a workflow
layer you get one of two bad outcomes: either every step interrupts the user
for approval (death by a thousand confirmations), or someone quietly widens a
single action's policy to `auto_execute` to reduce friction, which is exactly
the scope-creep failure mode the whole product is designed to avoid.

The workflow engine exists to let multiple tool calls execute as one coherent
unit, with approval checkpoints collapsed to the minimum number the risk
profile actually requires — never fewer, never more.

Everything below is designed to slot into the module boundaries already
defined in `FEATURES_PHASE.md` without renaming or restructuring anything that
exists.

---

## 1. Core concepts

| Term | Definition |
|---|---|
| **Workflow Definition** | A static, named, versioned description of an ordered (or branching) sequence of steps. Stored as data, not code. |
| **Workflow Run** | One execution instance of a Workflow Definition, with its own state, inputs, and outputs. |
| **Step** | A single unit of work inside a run. A step wraps exactly one registered tool call from `decision_engine/tools.py` or one sub-workflow. |
| **Gate** | A point in the run where execution pauses for user approval before continuing. Gates are *derived*, not authored — see §4. |
| **Execution Context** | The accumulated state of a run: inputs, each step's output, retrieved memory, redaction decisions, and timing. Passed step-to-step. |
| **Checkpoint** | A persisted snapshot of a run's Execution Context, written after every step, enabling pause/resume/rollback. |

A Workflow Run is the unit that appears in the approval queue and audit
dashboard from Phase C — not individual steps. The user reviews and approves
*runs at their gates*, not raw tool calls.

---

## 2. Relationship to the existing policy model

The engine does not introduce a new policy system. It composes the existing
three tiers (`auto_execute`, `confirm_once`, `require_approval`) that every
individual tool already declares in `decision_engine/tools.py`.

**Composition rule (the core design decision):**

> A workflow run pauses at a gate immediately *before* the first step in a
> contiguous sequence whose policy is `confirm_once` or `require_approval`,
> and does not resume automatically past it. Once approved, execution
> continues through any immediately-following steps of the *same or lower*
> risk tier without additional prompts, until the next tier increase.

In plain terms: risk only ever **escalates** silently-continuable execution
into a pause — it never de-escalates a pause back into silence. A single
approval covers a run of consecutive steps at that risk level; a new,
higher-risk step always gets its own gate, even later in the same run.

Concretely, for the PR-review example:

```
1. read_git_diff            auto_execute
2. check_mistake_log        auto_execute
3. draft_pr_summary         auto_execute      (generation, stays local)
──────────────────────────────────────────── gate (require_approval)
4. post_pr_comment          require_approval  (externally visible)
```

Steps 1–3 run without interruption. One approval gate appears before step 4,
because posting a comment is externally visible. If step 4 were instead two
steps — `submit_prompt_to_app` (require_approval) then `verify_result`
(auto_execute) — the engine does **not** insert a second gate for
`verify_result`, since it steps back down in risk after the approved action;
verification is not itself a new privileged action, it's confirmation the
already-approved one worked.

**Escalation exception:** if the Execution Context accumulated before a
`confirm_once`/`auto_execute` step is found (via the Privacy Guardrail check
from `FEATURES_PHASE.md` §5) to contain secrets, code, or private URLs that
weren't present when the run started, that step is force-escalated to
`require_approval` regardless of its declared default. This is evaluated at
step-execution time, not workflow-definition time, because the content isn't
known until upstream steps run.

---

## 3. Module boundaries (new + touched)

Consistent with the existing layering — Reasoning Engine generates/plans,
Automation Layer performs OS actions, Persistent Memory Engine records
outcomes — the workflow engine is a new coordination layer that sits between
the planner and the tool registry. It does not replace either.

```
backend/workflow_engine/
    __init__.py
    schema.py          # WorkflowDefinition, Step, WorkflowRun dataclasses/pydantic models
    registry.py         # load/validate/list registered workflow definitions
    executor.py          # runs a WorkflowRun step by step; owns the gate logic from §2
    gate_resolver.py    # pure function: given a step sequence + policies, compute gate positions
    context.py            # ExecutionContext: accumulation, redaction hooks, serialization
    checkpoint_store.py  # persist/restore ExecutionContext snapshots per step
    triggers.py            # scheduled/event-based run initiation (Phase B tie-in, §8)

backend/decision_engine/
    planner.py           # UNCHANGED contract, but now also called by executor.py per-step
    tools.py               # UNCHANGED contract; workflow steps call existing registered tools

backend/agent_actions.py  # existing product-level actions become the *first generation*
                              # of workflow definitions (see §9); no removal of direct-call path

backend/db/
    client.py                # add workflow_runs, workflow_steps tables (§6)
```

**Non-negotiable boundary:** `workflow_engine/executor.py` never calls OS-level
code directly. Every effect goes through `decision_engine/tools.py`, exactly
as single-action requests do today. The workflow engine is purely a
*sequencing and gating* layer — it has no more capability than a user manually
invoking the same tools one at a time. This is what keeps the workflow engine
itself out of the risk model; the risk lives entirely in the tools it calls.

---

## 4. Workflow Definition schema

Definitions are data (JSON/YAML), not Python, so they can be listed, diffed,
and edited without a code change — and so `agent_actions.py`'s existing
product flows can be expressed as definitions rather than hand-rolled call
chains.

```yaml
id: pr_review_v1
name: "Review current PR"
description: >
  Reads the working diff, checks it against known past mistakes,
  drafts a summary, and posts it as a PR comment after approval.
version: 1
inputs:
  - name: pr_reference
    type: string
    required: true
steps:
  - id: read_diff
    tool: read_git_diff
    inputs:
      ref: "{{ inputs.pr_reference }}"
    on_error: abort          # abort | skip | fallback
  - id: check_mistakes
    tool: check_mistake_log
    inputs:
      files: "{{ steps.read_diff.output.changed_files }}"
    on_error: skip
  - id: draft_summary
    tool: draft_pr_summary
    inputs:
      diff: "{{ steps.read_diff.output }}"
      known_issues: "{{ steps.check_mistakes.output }}"
    on_error: abort
  - id: post_comment
    tool: post_pr_comment
    inputs:
      pr_reference: "{{ inputs.pr_reference }}"
      body: "{{ steps.draft_summary.output.text }}"
    on_error: abort
outputs:
  - name: comment_url
    from: steps.post_comment.output.url
```

Field notes:

- `tool` must reference an entry already registered in
  `decision_engine/tools.py`; the workflow engine does not define new
  capabilities, only sequences of existing ones.
- `on_error` is per step, not per workflow, because failure severity differs
  by step (a failed `check_mistake_log` shouldn't abort a review; a failed
  `draft_summary` should).
- Templated inputs (`{{ steps.X.output.Y }}`) are resolved from the
  Execution Context at run time, not definition time.
- Gates are **not** declared in the definition. They are computed by
  `gate_resolver.py` from the referenced tools' policies at load time, so a
  policy change in `tools.py` automatically changes where a workflow pauses
  without editing every workflow that uses that tool.

---

## 5. Step and run state machines

**Step states:**

```
pending -> running -> succeeded
                    -> failed -> (abort | skipped | retried)
         -> waiting_for_approval -> approved -> running
                                  -> rejected -> (run: cancelled)
```

**Run states:**

```
created -> running -> completed
                    -> failed
                    -> awaiting_approval -> running (on approve)
                                          -> cancelled (on reject)
        -> paused (manual pause, e.g. user steps away) -> running (on resume)
```

A run in `awaiting_approval` is the thing that appears in the approval queue
from Phase C. It carries: which step it's paused before, the full rendered
inputs that step will receive (so the user sees *exactly* what will be
pasted/posted/committed, not an abstract description), and any redactions
already applied to that content.

---

## 6. Persistence

Two new tables, additive to the existing `decision_log` / `mistake_log`,
never replacing them:

```sql
CREATE TABLE workflow_runs (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT NOT NULL,
    workflow_version INTEGER NOT NULL,
    status          TEXT NOT NULL,
    inputs_json     TEXT NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    completed_at    TIMESTAMP,
    initiated_by    TEXT NOT NULL,      -- 'user' | 'trigger:<trigger_id>'
    project_id      TEXT NOT NULL
);

CREATE TABLE workflow_steps (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES workflow_runs(id),
    step_def_id     TEXT NOT NULL,       -- matches the `id` in the definition's steps[]
    tool            TEXT NOT NULL,
    policy          TEXT NOT NULL,       -- resolved policy at execution time
    status          TEXT NOT NULL,
    rendered_inputs_json TEXT,
    output_json     TEXT,
    redactions_json TEXT,                -- what was stripped before this step ran, if anything
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    approved_by     TEXT,
    approved_at     TIMESTAMP
);
```

Every completed step also writes a normal entry to `decision_log`, tagged
with `run_id`, so a run reads as a coherent story in the existing audit log
rather than a second, disconnected logging system. `workflow_runs` /
`workflow_steps` are the structured index; `decision_log` remains the
human-readable narrative.

---

## 7. Checkpointing, pause, resume, rollback

- After **every** step completes, `checkpoint_store.py` persists the full
  Execution Context. This is what makes `awaiting_approval` safe to sit in
  indefinitely — closing the app mid-run does not lose state.
- **Resume** replays from the last checkpoint; it does not re-run completed
  steps. Re-running a completed step is only ever an explicit user action
  ("retry this step"), never implicit.
- **Rollback** ties into the Phase C snapshot/rollback feature: any step
  whose tool performs a file write is required to register a pre-write
  snapshot in its tool definition. If a run is cancelled or fails after such
  a step, the executor offers `rollback_last_edit` for that step
  specifically — rollback is scoped to the step, not the whole run, since
  earlier steps (like posting a comment) may not be reversible and shouldn't
  be implied as "undone" by a rollback action.
- **Cancel** at a gate marks the run `cancelled`, logs the rejection with
  reason (if the user gives one) to `decision_log`, and performs no cleanup
  beyond what rollback explicitly does — cancellation itself must never
  trigger destructive action.

---

## 8. Triggers (event/schedule-initiated runs)

Ties directly into the Phase B "scheduled/triggered automation" feature.
Triggers create workflow runs; they do not bypass the gate model.

```yaml
trigger:
  id: on_test_failure
  workflow: diagnose_and_summarize_failure_v1
  event: test_suite.failed
  policy_override: confirm_once_first_time
```

`policy_override: confirm_once_first_time` is the rule from the earlier
discussion made concrete: the first time a given trigger fires, the *run
initiation itself* requires a one-time confirmation ("AUTOMATA wants to start
running this workflow automatically when tests fail — allow?"), independent
of whatever gates exist inside the workflow. Once approved, subsequent firings
skip that initiation confirmation, but internal step gates (§2) still apply
every time — trigger approval only ever waives "may this workflow start
running," never "may this specific privileged step run."

---

## 9. Migration path for existing `agent_actions.py` flows

The hand-written chains already in `agent_actions.py` (e.g. the MVP demo flow:
generate prompt → copy → open ChatGPT → confirm → paste → log) become the
first workflow definitions, not a parallel system:

1. Each existing composed action in `agent_actions.py` gets an equivalent
   `.yaml` definition in a new `backend/workflow_engine/definitions/` folder.
2. `agent_actions.py` functions become thin wrappers that call
   `executor.run(definition_id, inputs)` instead of hand-calling tools in
   sequence.
3. Direct single-tool calls (not composed flows) are untouched — the
   workflow engine is additive for multi-step work, not a mandatory
   indirection layer for everything.

This means zero regression risk to the MVP demo flow that already works — it
gets re-expressed as `definitions/chatgpt_prompt_handoff_v1.yaml` and should
produce byte-identical gate behavior to what it does today.

---

## 10. API surface

```python
# backend/workflow_engine/executor.py

class WorkflowExecutor:
    def start(self, workflow_id: str, inputs: dict, project_id: str,
               initiated_by: str = "user") -> WorkflowRun: ...

    def resume(self, run_id: str) -> WorkflowRun: ...

    def approve_gate(self, run_id: str, approved_by: str) -> WorkflowRun: ...

    def reject_gate(self, run_id: str, reason: str | None = None) -> WorkflowRun: ...

    def cancel(self, run_id: str, reason: str | None = None) -> WorkflowRun: ...

    def get_run(self, run_id: str) -> WorkflowRun: ...

    def list_runs(self, project_id: str,
                    status: str | None = None) -> list[WorkflowRun]: ...
```

```python
# backend/workflow_engine/gate_resolver.py

def resolve_gates(steps: list[StepDefinition],
                    tool_registry: ToolRegistry) -> list[GatePosition]:
    """
    Pure function, no side effects, fully unit-testable in isolation from
    the executor. Given resolved policies per step, returns the indices
    where execution must pause. This is the function that encodes the
    composition rule in §2 and should have the heaviest test coverage
    in the whole engine, since it's the actual safety boundary.
    """
```

Keeping `resolve_gates` pure and separate from `executor.py`'s I/O is
deliberate: it is the single function responsible for deciding when the user
gets asked for permission, so it needs to be testable with plain input/output
assertions, with no mocking of clipboard, browser, or DB required.

---

## 11. Concurrency

- One active run per `(project_id, workflow_id)` at a time by default —
  starting a second run of the same workflow on the same project while one is
  `running` or `awaiting_approval` queues rather than parallel-executes,
  to avoid two runs racing on the same files or the same external app.
- Runs against **different** workflows or **different** projects may execute
  concurrently.
- This limit is a default, not a hard constraint in the schema — a future
  workflow definition could declare `concurrency: parallel` once there's a
  real use case, but the MVP-plus scope here should not build for that
  before it's needed.

---

## 12. Testing requirements

- `gate_resolver.py`: exhaustive table-driven tests over policy sequences —
  every ordering of `auto_execute` / `confirm_once` / `require_approval`
  across 2–5 step runs, asserting exact gate positions.
- Escalation-on-content tests: a step declared `auto_execute` must be
  provably force-escalated when the Privacy Guardrail flags content in its
  rendered inputs.
- Checkpoint/resume tests: kill the executor mid-run (simulated), assert
  resume continues from the correct step with no re-execution of completed
  steps.
- Rollback scoping tests: assert rollback only reverts the specific
  file-writing step it's attached to, not the full run.
- Trigger tests: first-fire requires confirmation, subsequent fires don't,
  internal gates fire every time regardless of trigger confirmation state.
- Migration tests: each re-expressed `agent_actions.py` flow, run through the
  new engine, produces the same tool call sequence and same gate positions as
  the original hand-written version.

---

## 13. Definition of Done

- [ ] Workflow definitions are data (YAML/JSON), loaded and validated by
      `registry.py`, with no code required to add a new workflow that
      composes existing tools.
- [ ] `gate_resolver.py` implements the composition rule in §2 as a pure
      function with full table-driven test coverage.
- [ ] Escalation-on-content works: a step's declared policy can be
      overridden upward at execution time based on what its rendered inputs
      actually contain, never downward.
- [ ] Every step writes to both `workflow_steps` and `decision_log`; runs are
      visible end-to-end in the existing audit surfaces from Phase C, not a
      separate log a user has to know to check.
- [ ] Checkpointing persists after every step; resume never re-executes a
      completed step.
- [ ] Rollback is scoped per-step and only offered for steps that registered
      a pre-write snapshot.
- [ ] Cancellation at any gate performs no destructive action by itself.
- [ ] Triggers can initiate runs; trigger confirmation and internal gate
      confirmation are tracked and enforced independently.
- [ ] At least the MVP demo flow and the PR-review flow exist as real
      definitions and pass the migration-equivalence tests in §12.
- [ ] Concurrency default (one active run per project+workflow) is enforced
      and covered by a test that starts a second run mid-execution.
