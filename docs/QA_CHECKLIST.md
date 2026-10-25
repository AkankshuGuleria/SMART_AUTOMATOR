# MVP verification checklist

Use a disposable local repository and an explicitly provisioned test
database. Keep real provider calls and production data out of automated
tests. Record the actual environment and results; do not mark a feature
verified because its screen or API route exists.

## Setup and health

- [ ] Fresh backend dependency install completes from `backend/`.
- [ ] Backend starts with documented configuration and reports missing
      services accurately.
- [ ] Frontend starts and displays backend connectivity status.
- [ ] Tauri desktop shell starts on the target Windows machine.

## Project and memory

- [ ] Register/select a local project and confirm invalid/missing paths are
      reported.
- [ ] Capture a file edit, commit, terminal command, and TODO using test data.
- [ ] Confirm secret-like values are redacted before storage.
- [ ] Restart backend and confirm persisted activity remains retrievable.
- [ ] Query stored facts using multiple phrasings and inspect returned sources.
- [ ] Verify empty retrieval does not produce invented facts.
- [ ] Generate a brief from stored activity and verify its fields/content.

## Chat and agent actions

- [ ] Exercise query, chat intent routing, and action-card rendering.
- [ ] Verify commit-message generation uses the intended diff context.
- [ ] Verify repository explanation and code-location responses reference
      real project data.
- [ ] Verify diagnostics correlate available history and clearly report
      missing sources.
- [ ] Check analytics and live metrics payloads render in the UI.

## Automation and workflows

- [ ] Restore a disposable workspace and compare each reported step with
      actual effects.
- [ ] Verify command suggestions do not execute before approval.
- [ ] Verify clipboard/app/keystroke actions honor their tool policies.
- [ ] Verify external prompt submission waits for explicit approval.
- [ ] Pause, approve/reject, fail, and resume workflow runs; confirm completed
      side effects are not repeated unexpectedly.
- [ ] Verify cross-app task progress and errors are visible.
- [ ] Verify OCR/screen capture behavior, consent, and secret redaction.

## Failure and privacy cases

- [ ] Test database, provider, and Ollama unavailable states.
- [ ] Test missing optional OCR/application dependencies.
- [ ] Confirm failures are not represented as completed actions.
- [ ] Confirm local API remains loopback-only.
- [ ] Confirm logs, screenshots, and test artifacts contain no credentials
      or private project data.

## Evidence

For each failed item, record the steps, expected and actual result, relevant
screen/API endpoint, and sanitized logs. Fix one reproducible issue at a
time, add a regression test where practical, and rerun the affected checklist
items.
