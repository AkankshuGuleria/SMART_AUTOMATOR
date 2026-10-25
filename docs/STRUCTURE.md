# Project structure

This document describes the canonical repository layout for autometav01.
Every file lives in one of three top-level domains: `backend/`, `frontend/`,
or `docs/`. Supporting configuration and scripts live at the repository root.

```
AUTOMATA/
├── docs/                          # All product and operational documentation
│   ├── AGENTS.md                  # AI agent operating rules
│   ├── API_REFERENCE.md           # HTTP and WebSocket endpoint index
│   ├── ARCHITECTURE.md            # Runtime components, data flows, trust boundaries
│   ├── CONVENTIONS.md             # Module boundaries and file placement
│   ├── DATABASE_SCHEMA.md         # CockroachDB tables and vector conventions
│   ├── DEVELOPMENT.md             # Environment, run, and test commands
│   ├── FEATURES_PHASE.md          # Execution policy, cross-app actions, workflow behavior
│   ├── PROJECT.md                 # MVP intent, capabilities, boundaries
│   ├── QA_CHECKLIST.md            # Verification gates before calling the MVP ready
│   ├── README.md                  # Documentation index
│   ├── ROADMAP.md                 # Current stabilization priorities
│   ├── SECURITY.md                # Data handling, action approvals, deployment limits
│   ├── SKILLS.md                  # Engineering playbooks (testing, bug-fixing, etc.)
│   ├── TECH_STACK.md              # Exact versions and tooling decisions
│   ├── USER_GUIDE.md              # First-run and feature workflows
│   └── WORKFLOW_ENGINE.md         # Checkpoints, gates, execution, provenance
├── backend/                       # Python FastAPI backend (all server-side logic)
│   ├── ai/                        # Reasoning engine — all Bedrock/provider calls
│   │   ├── __init__.py
│   │   └── bedrock_client.py
│   ├── api/                       # API server — FastAPI routes and WebSocket
│   │   ├── __init__.py
│   │   └── server.py
│   ├── automation/                # Automation layer — Windows OS actions only
│   │   ├── __init__.py
│   │   ├── agent_bridge.py
│   │   ├── command_executor.py
│   │   ├── dev_servers.py
│   │   ├── ocr.py
│   │   ├── os_windows.py
│   │   ├── restore.py
│   │   └── screen_capture.py
│   ├── db/                        # Persistence — CockroachDB client and schema
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── schema.sql
│   ├── decision_engine/           # Intent routing, planning, tools, triggers
│   │   ├── __init__.py
│   │   ├── intent_parser.py
│   │   ├── orchestrator.py
│   │   ├── planner.py
│   │   └── tools.py
│   ├── memory/                    # Persistent memory — capture, embeddings, retrieval
│   │   ├── __init__.py
│   │   ├── capture.py
│   │   ├── embeddings.py
│   │   └── retrieval.py
│   ├── workflow_engine/           # Checkpointed workflow execution
│   │   ├── __init__.py
│   │   ├── checkpoint_store.py
│   │   ├── context.py
│   │   ├── executor.py
│   │   ├── gate_resolver.py
│   │   ├── registry.py
│   │   ├── schema.py
│   │   ├── triggers.py
│   │   └── definitions/           # Versioned YAML workflow definitions
│   │       ├── chatgpt_prompt_handoff_v1.yaml
│   │       └── pr_review_v1.yaml
│   ├── monitoring/                # Local telemetry (no network)
│   │   ├── system_metrics.py      # CPU/GPU/RAM/disk/network sampler
│   │   └── app_usage.py           # Foreground-app tracker + usage analysis (SQLite)
│   ├── tests/                     # Backend unit and API tests (pytest)
│   ├── .env.example               # Environment variable template (gitignored .env)
│   ├── config.py                  # Backend settings and feature flags
│   ├── main.py                    # Backend process entry point
│   ├── pyproject.toml             # Python package manifest (uv)
│   ├── uv.lock                    # Pinned dependency versions
│   ├── agent_actions.py           # Agent action implementations
│   ├── check_db_status.py         # Database status check utility
│   ├── explain_repository.py      # Repository explanation logic
│   ├── logging_config.py          # Logging configuration
│   └── seed_project.py            # Project seeding utility
├── frontend/                      # React + Tauri frontend (presentation layer only)
│   ├── index.html                 # Vite entry HTML
│   ├── package.json               # npm package manifest
│   ├── package-lock.json          # Pinned dependency versions
│   ├── tsconfig.json              # TypeScript configuration
│   ├── tsconfig.app.json          # App TypeScript configuration
│   ├── tsconfig.node.json         # Node TypeScript configuration
│   ├── vite.config.ts             # Vite build configuration
│   ├── .oxlintrc.json             # Oxlint configuration
│   ├── .gitignore                 # Frontend gitignore
│   ├── src/                       # React source code
│   │   ├── components/            # Reusable UI and layout components
│   │   ├── lib/                   # Typed API and WebSocket client
│   │   ├── screens/               # Product screens
│   │   ├── styles/                # Global CSS tokens and styles
│   │   └── App.tsx                # App root — navigation and app-level state
│   └── src-tauri/                 # Tauri desktop shell
├── scripts/                       # Local development helpers
│   ├── check_env.py               # Environment readiness check
│   ├── dev-with-backend.ps1       # Start dev with backend
│   └── start_dev.ps1              # Start development server
├── .gitignore                     # Repository-level gitignore
├── .pre-commit-config.yaml        # Pre-commit hooks
├── .secrets.baseline              # Secret scanning baseline
└── kilo.jsonc                     # Kilo agent configuration
```

## Module boundaries

| Component | Owns | Must never |
| --- | --- | --- |
| `backend/ai/` | All Bedrock/reasoning provider calls | Write to DB, execute OS actions |
| `backend/api/` | FastAPI routes, WebSocket events | Contain business logic, touch DB/Bedrock directly |
| `backend/automation/` | Windows OS, app, command, visual actions | Write to DB directly, call Bedrock |
| `backend/db/` | CockroachDB client, schema, all DB writes | Call Bedrock, execute OS actions |
| `backend/decision_engine/` | Intent parsing, planning, tools, triggers | Bypass Agent Loop, call Bedrock/DB directly |
| `backend/memory/` | DB writes, embedding gen, vector retrieval | Call Bedrock directly, execute OS actions |
| `backend/workflow_engine/` | Workflow execution, checkpoints, approval gates | Call Bedrock/DB directly outside client.py |
| `frontend/` | UI rendering, API client | Talk to CockroachDB or Bedrock directly |

## Key rules

- **All CockroachDB writes** go through `backend/db/client.py` → `get_session()`.
- **All Bedrock calls** go through `backend/ai/bedrock_client.py`.
- **All OS actions** go through `backend/automation/os_windows.py`.
- **No real credentials** in any file — use `backend/.env` (gitignored) only.
- **Documentation lives only under `docs/`** — the root keeps only `README.md`
  and `AGENTS.md` as pointers.
- **Frontend is thin presentation only** — no memory logic, no DB calls, no Bedrock calls.
