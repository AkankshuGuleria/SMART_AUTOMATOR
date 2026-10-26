# Workflow engine

## 1. Purpose

The Workflow Engine executes named, versioned, multi-step workflows. It is a
deterministic executor, not an alternate reasoning or policy layer. Workflow
steps call registered tools and persist their state so gated work can pause
and resume.

Implementation: `backend/workflow_engine/`.

## 2. Workflow definitions

Definitions are YAML files under `backend/workflow_engine/definitions/`.
`registry.py` discovers definitions; `schema.py` validates the workflow and
run/step structures.

Templates can refer to workflow inputs and prior step outputs. Keep the
definition's expected input/output contract explicit and test template
resolution.

## 3. Execution and gates

`executor.py` runs each step and derives approval gates from the registered
tool policies. The policy tiers are documented in `FEATURES_PHASE.md`.
`gate_resolver.py` groups gated steps according to the contiguous-gate rules;
`auto_execute` steps break a gated sequence.

An approval decision must be persisted before the executor resumes protected
steps. Rejected or failed steps must remain distinguishable from successful
completion.

## 4. Checkpoints

`checkpoint_store.py` persists workflow run and step state through the shared
database client. A resumed workflow must not repeat completed side effects
unless the step is explicitly designed to be idempotent.

## 5. Triggers and provenance

`triggers.py` connects supported events to registered workflows. Triggered
actions must preserve the same safety policies and provenance expectations as
user-started runs.

## 6. Tests and operations

Test gate resolution, template rendering, checkpoint/resume behavior, and
failure handling with mocked tools and database fixtures. Never invoke real
desktop actions or production databases from automated tests.
