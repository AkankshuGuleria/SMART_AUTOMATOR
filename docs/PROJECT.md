# Product brief

## 1. Product

**AUTOMATA** (repository: `SMART_AUTOMATOR`) is a local-first AI development
workspace for one developer on Windows.

## 2. Problem

Project context is fragmented across files, git history, terminal sessions,
and chat. Developers repeatedly reconstruct what changed, why it changed, and
what remains to be done — and spend more time again briefing AI coding tools.

## 3. Intended user

One developer on one Windows machine working across several local
repositories. Not a team or hosted multi-user product.

## 4. Core experience

1. Register a local repository; AUTOMATA works out its stack, run commands,
   environment variables and modules.
2. It captures activity (edits, commits, terminal commands) in the background
   and keeps it in local memory that works offline.
3. Ask about the project in chat or the work bar (Alt+Space) and get answers
   grounded in that memory.
4. Hand work to an AI app (Antigravity, Kilo Code, Claude, Cursor, VS Code):
   AUTOMATA asks what it needs, writes the prompt, delivers it with your
   approval, watches the result and lists keys you still have to provide.
5. Come back later to a brief and **Resume** — the editor you last used, your
   recent files, terminal and dev servers.

## 5. Capabilities

| Capability | Where |
| --- | --- |
| Always-on tray app, agent supervisor, start at sign-in | `frontend/src-tauri/` |
| Local memory (SQLite FTS5), optional CockroachDB cloud copy | `memory/`, `db/` |
| Activity capture, snapshots and resume | `memory/capture.py`, `workspace/` |
| Project profiles (stack, run book, env vars, modules) | `intelligence/` |
| Chat and intent routing with approval cards | `decision_engine/`, `api/` |
| Delegation tasks with questions, approval gates, Needs inbox | `tasks/`, `automation/chat_apps.py` |
| Verified desktop control and OCR | `automation/` |
| AI work bar: music, search, screen reading | `assist/`, `CompanionApp.tsx` |
| Permissions and local-only API | `security/` |
| System and app-usage analytics, briefs, workflows | `monitoring/`, `workflow_engine/` |
| Cloud models online, Ollama offline | `ai/` |

Verification status of each: [PROJECT_STATUS.md](PROJECT_STATUS.md).

## 6. Boundaries

- Single local user; no accounts, teams or hosted tenancy.
- Windows is the supported platform for desktop automation.
- Local memory is the source of truth; CockroachDB is an optional copy.
- Cloud model providers, Ollama, OCR language packs and other apps may be
  unavailable or need setup; AUTOMATA reports that instead of failing silently.
- The UI orchestrates work; it does not replace the IDE or terminal.

## 7. Output style

Replies and briefs are short, factual and grounded in captured data. Recalled
facts are kept apart from suggestions. With no supporting memory the answer is
"No memory found for that query" — never invented detail.

## 8. Safety

Passive, reversible work runs automatically. Anything that controls the PC asks
first, and sending work to another app or running builds needs explicit
approval. See [ACTION_POLICIES.md](ACTION_POLICIES.md) and [SECURITY.md](SECURITY.md).

## 9. Success criteria

- Fresh setup works without machine-specific paths or required cloud services.
- Health and setup expose missing services clearly, with a fix for each.
- Capture, retrieval, brief, chat and restore pass automated tests and the
  manual checks in [QA_CHECKLIST.md](QA_CHECKLIST.md).
- OS and provider failures stay visible and never masquerade as success.
- No real credentials are committed, persisted in memory or sent to a model.

## 10. Out of scope

- Multi-user access control, hosted deployment and team features.
- Cross-platform automation parity.
- Unbounded autonomous execution or silent irreversible changes.

## 11. Manual acceptance flow

1. Start the app; confirm agent and database status are visible.
2. Register and select a disposable test project.
3. Confirm captured commits and edits appear in activity and memory.
4. Ask a factual question supported by captured data and inspect its sources.
5. Generate a brief and check it reflects stored activity.
6. Resume the test workspace and inspect each reported step.
7. Trigger an approval-gated action and confirm nothing happens before approval.
8. Stop optional services and confirm the UI/API report degraded behaviour.

Run this only against a disposable project and a non-production database.
