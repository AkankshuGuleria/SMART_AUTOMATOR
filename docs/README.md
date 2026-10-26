# autometav01

**autometav01** is a local, single-developer MVP for carrying project context
between coding sessions. It captures selected development activity, stores
structured and semantic memory in CockroachDB, and exposes retrieval,
workspace, and workflow actions through a React desktop UI and a Python API.

The repository and several runtime labels still use the internal name
**AUTOMATA**. This documentation uses **autometav01** as the product name.

## Capabilities

- Always-on tray app (autostart, single instance, backend supervisor, Alt+Space / Ctrl+Alt+A AI work bar).
- Local offline memory (SQLite FTS5) synced from CockroachDB; session snapshots and resume.
- Project profiles detected from each project's files (stack, run book, env vars, modules).
- Chat with memory-grounded answers; cloud models online, Ollama offline.
- Delegation tasks to Antigravity / Claude / VS Code / ChatGPT with approval gates.
- "Needs from you" inbox for keys and connection strings (Credential Manager / .env).
- Verified desktop control: focus, type, paste, browser tabs, OCR read-back.
- System resources and app-usage analytics; briefs, restore, analytics, workflows.

## Run locally

Prerequisites: Windows, Python 3.12+, `uv`, Node.js 20+, npm, and a
CockroachDB database with vector support. Ollama is optional; configured
cloud reasoning or embedding providers can be used instead.

1. Configure `backend\.env` using [the development guide](docs/DEVELOPMENT.md).
2. Start the backend from the repository root:

   ```powershell
   cd backend
   uv sync
   uv run python main.py
   ```

3. In a second terminal, start the frontend:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

The API is available at `http://127.0.0.1:8000`; its interactive OpenAPI
reference is at `http://127.0.0.1:8000/docs`. The Vite development UI is
available at `http://localhost:5173`.

## Documentation index

| Document | Location | Purpose |
| --- | --- | --- |
| [Product scope](docs/PROJECT.md) | `docs/PROJECT.md` | MVP intent, capabilities, boundaries, and acceptance flow |
| [Architecture](docs/ARCHITECTURE.md) | `docs/ARCHITECTURE.md` | Runtime components, data flows, and trust boundaries |
| [Data model](docs/DATABASE_SCHEMA.md) | `docs/DATABASE_SCHEMA.md` | CockroachDB tables and vector conventions |
| [Development setup](docs/DEVELOPMENT.md) | `docs/DEVELOPMENT.md` | Environment, run, and test commands |
| [API reference](docs/API_REFERENCE.md) | `docs/API_REFERENCE.md` | HTTP and WebSocket endpoint index |
| [User guide](docs/USER_GUIDE.md) | `docs/USER_GUIDE.md` | First-run and feature workflows |
| [Security](docs/SECURITY.md) | `docs/SECURITY.md` | Data handling, action approvals, and deployment limits |
| [QA checklist](docs/QA_CHECKLIST.md) | `docs/QA_CHECKLIST.md` | Verification gates before calling the MVP ready |
| [Start here (agents & contributors)](docs/AGENTS.md) | `docs/AGENTS.md` | Product summary, repo map, run/test, rules |
| [Project status](docs/PROJECT_STATUS.md) | `docs/PROJECT_STATUS.md` | Feature checklist, verification results, remaining work |
| [Audit report](docs/AUDIT_REPORT.md) | `docs/AUDIT_REPORT.md` | 2026-10-26 audit against the problem statement, test results, findings |
| [Smart workspace plan](docs/SMART_WORKSPACE_PLAN.md) | `docs/SMART_WORKSPACE_PLAN.md` | Live test findings, missing features, stack and phased update plan |
| [Conventions](docs/CONVENTIONS.md) | `docs/CONVENTIONS.md` | Module boundaries and file placement |
| [Technology stack](docs/TECH_STACK.md) | `docs/TECH_STACK.md` | Exact versions and tooling decisions |
| [Engineering playbooks](docs/SKILLS.md) | `docs/SKILLS.md` | Testing, bug-fixing, frontend, backend, prompts, output |
| [Roadmap](docs/ROADMAP.md) | `docs/ROADMAP.md` | Current stabilization priorities |
| [Feature policies](docs/FEATURES_PHASE.md) | `docs/FEATURES_PHASE.md` | Execution policy, cross-app actions, workflow behavior |
| [Workflow engine](docs/WORKFLOW_ENGINE.md) | `docs/WORKFLOW_ENGINE.md` | Checkpoints, gates, execution, and provenance |
| [AI agent rules](docs/AGENTS.md) | `docs/AGENTS.md` | Operating rules for autonomous coding agents |

## Current product boundary

This is a local-first, single-user MVP, not a hosted multi-tenant service.
The backend is intended to bind to loopback, automation targets Windows, and
external providers require user-supplied configuration. Do not expose the API
to an untrusted network. See [Security](docs/SECURITY.md).
