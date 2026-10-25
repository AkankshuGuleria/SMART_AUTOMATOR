# MVP feature and action policies

This document describes the behavior boundaries used by cross-app tools and
workflows. The implementation is in `backend/decision_engine/tools.py`,
`backend/decision_engine/planner.py`, and `backend/workflow_engine/`.

## 1. Execution policy

| Policy | Intended use | Required behavior |
| --- | --- | --- |
| `auto_execute` | Passive, reversible actions | May run without a prompt when the tool policy allows it |
| `confirm_once` | Reversible environment changes | Pause and obtain confirmation before the gated sequence |
| `require_approval` | External or high-impact actions | Require explicit approval for each protected action |

Actual classification is defined by the registered tool policy. Do not infer
that an action is safe solely from its name.

## 2. Cross-app actions

The tool layer includes clipboard copy/paste, opening URLs, focusing apps,
limited keystrokes, external prompt submission, and result verification.
Screen capture and OCR tools provide visual context. These actions are
Windows-oriented and may require a running desktop session or OCR dependency.

External handoffs can expose project context to another application or
provider. Redact sensitive data and obtain the required approval before
submission.

## 3. Workflow behavior

Workflow definitions are versioned YAML under
`backend/workflow_engine/definitions/`. Workflows use registered tools,
persist step/run state, and may pause at approval gates. See
`WORKFLOW_ENGINE.md` for checkpoints, input templates, and resume behavior.

## 4. Provenance

Decision and workflow results should include the requested action, execution
state, and available provenance. An approval-required action must not be
reported as complete before it actually runs.

## 5. Verification

The documented policies are design constraints, not a claim that every
external application integration has been manually exercised. Verify each
action against the cases in `docs/QA_CHECKLIST.md`.
