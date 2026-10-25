# User guide

## 1. Start the app

Follow [Development setup](DEVELOPMENT.md) to configure the backend and
frontend. Confirm that the UI reports the backend online and that the health
endpoint reports the services you intend to use.

## 2. Add and select a project

Register a local repository through the project UI/API and select it as the
active project. The directory must exist. Capture threads use an available
registered local project when the backend starts.

Use a test repository first. Capture can record project paths, file edit
events, commits, terminal history, and TODOs.

## 3. Review memory and activity

Use the dashboard/activity views to inspect captured work. Ask factual
questions through chat or memory query. Check source memories and timestamps
before relying on an answer; generated suggestions are not historical facts.

If no relevant memory was captured, the product should report that limitation
rather than inventing a plausible answer.

## 4. Use briefs and project actions

The brief summarizes stored activity and pending work. Agent actions include
repository explanation, code-location queries, work continuation, commit
message generation, and development-environment startup. Review the returned
status and any action card before taking a consequential action.

## 5. Restore a workspace

Start restore from the selected project. Review each step and its result.
Restore can involve git and local process changes; use a disposable project
until the behavior is verified on the target machine.

## 6. Approvals and workflows

Workflows may pause for approval before gated steps. Read the action and
inputs, approve only when the target and outcome are understood, and check
the final status. Rejected, failed, and completed states should remain
distinct.

External app handoffs and prompt submissions may send project context to
another service. Review and redact that context before approving.

## 7. When something is unavailable

- A disconnected database means activity may not persist.
- A missing model provider may prevent generated answers or embeddings.
- A missing OCR dependency or desktop permission may prevent visual tools.
- A failed OS action should appear as an error or partial result.

Use the feature-specific QA steps in `QA_CHECKLIST.md` when reporting a
reproducible defect.
