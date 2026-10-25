# Product brief

## 1. Product identity

**autometav01** is a local developer-workflow memory product. The codebase
uses the internal name AUTOMATA in package metadata, logs, and some UI text.

## 2. Product problem

Project context is fragmented across files, git history, terminal sessions,
and chat. Developers repeatedly reconstruct what changed, why it changed, and
what remains to be done.

## 3. Intended user

The MVP serves one developer on one Windows machine working across one or more
local repositories. It is not a team collaboration or hosted multi-user
product.

## 4. Core experience

1. Register a local repository and select it in the desktop UI.
2. Capture project activity in the background while the backend is running.
3. Ask questions or request an action from the project context.
4. Review generated answers, action cards, progress, and approval prompts.
5. Return later to a brief, activity history, or workspace restore flow.

## 5. Capability inventory

| Capability | Implementation surface |
| --- | --- |
| Project and session management | FastAPI project/session routes and CockroachDB client |
| Activity capture | File watcher, git poller, and terminal-history capture |
| Persistent memory | Structured CockroachDB rows and vector columns |
| Memory retrieval | Recent-row and semantic-vector retrieval paths |
| Chat and intent routing | Chat API, intent parser, planner, and action cards |
| Morning brief and activity | Brief API, activity feed, and related UI screens |
| Agent actions | Commit message, explain repository, find code, continue work, start environment |
| Workspace automation | Windows restore and development-server controls |
| Diagnostics and analytics | Project diagnostics, analytics, and live metrics routes |
| Autonomous decisions | Commit/session triggers with decision-log provenance |
| Cross-app and visual actions | Clipboard, app focus, keystrokes, screen capture, and OCR tools |
| Workflow execution | Versioned workflows with checkpoints and approval gates |

The table records code surfaces, not a guarantee that every integration has
passed end-to-end verification. Check [the QA checklist](QA_CHECKLIST.md)
for the evidence required to call a feature verified.

## 6. MVP boundaries

- Single local developer; no accounts, teams, or hosted tenancy.
- Windows is the supported automation target. Other operating systems are
  not promised.
- CockroachDB is the persistent memory store; disconnected startup is
  degraded operation, not durable memory.
- External model services, Ollama, OCR engines, and desktop applications may
  be unavailable or require separate setup.
- The UI is an orchestration surface, not a replacement IDE or terminal.

## 7. User-facing output

Keep replies and briefs concise, factual, and grounded in captured data.
Distinguish recalled facts from generated suggestions. If retrieval has no
supporting result, say that no memory was found instead of inventing details.

## 8. Runtime and data boundary

The frontend communicates with the local FastAPI service. The backend owns
database access, provider calls, memory capture/retrieval, planning, and
automation. Captured activity can include repository paths, commit messages,
file names, and redacted terminal commands.

## 9. Action safety

Passive and reversible operations may run automatically. Actions that change
the workspace or interact with another app must use the planner/workflow
approval policy. External submission requires explicit approval. See
[the security guide](SECURITY.md).

## 10. Success criteria

- Fresh setup instructions work without undocumented machine-specific paths.
- Health and project setup expose missing services clearly.
- Core memory capture, retrieval, brief, chat, and restore flows pass automated
  tests and the manual checks in `docs/QA_CHECKLIST.md`.
- OS and external-provider failures remain visible and do not masquerade as
  successful actions.
- No real credentials are committed, persisted in memory, or sent to a model.

## 11. Product status

The repository contains implementations for the capability inventory above.
The current phase is MVP stabilization: validate each user-facing surface,
record reproducible defects, and fix them one at a time.

## 12. Out of scope

- Multi-user access control, hosted deployment, and team features.
- Cross-platform automation parity.
- Unbounded autonomous execution or silent irreversible changes.
- Claims of production readiness before the security and QA gates are met.

## 13. Manual acceptance flow

1. Start the API and UI; confirm backend and database status are visible.
2. Register and select a local test project.
3. Confirm captured commits/file edits can be found in activity and memory.
4. Ask a factual question supported by captured data and inspect its sources.
5. Generate a brief and verify it reflects stored project activity.
6. Restore a disposable test workspace and inspect each reported step.
7. Trigger an approval-gated action and confirm it does not proceed before
   approval.
8. Stop optional services and verify the UI/API report degraded behavior.

Run this flow only against a disposable local project and a non-production
test database.
