# Repository structure

```text
SMART_AUTOMATOR/
├── backend/                     Python agent (FastAPI, uv)
│   ├── main.py                  entry point → uvicorn on 127.0.0.1:8000
│   ├── config.py                settings from backend/.env
│   ├── logging_config.py
│   ├── agent_actions.py         explain repo, commit message, open app/URL, dev env
│   ├── explain_repository.py
│   ├── api/                     server.py (core routes, lifespan), workspace_routes.py
│   ├── security/                permissions.py, http_guard.py, defender.py
│   ├── ai/                      bedrock_client.py (all model calls), local_models.py (Ollama)
│   ├── memory/                  local_store.py (SQLite), capture.py, sync.py, retrieval.py, embeddings.py
│   ├── workspace/               capture_manager.py, snapshot.py (save / resume)
│   ├── intelligence/            profile.py (stack, run book, env, modules), providers.py
│   ├── automation/              desktop.py, chat_apps.py, win32.py, uia.py, ocr.py,
│   │                            agent_bridge.py, os_windows.py, no_console.py, …
│   ├── assist/                  work bar commands: commands.py, media.py, screen.py
│   ├── tasks/                   engine.py, questions.py, store.py, needs.py
│   ├── decision_engine/         intent_parser.py → planner.py → tools.py, orchestrator.py
│   ├── workflow_engine/         YAML workflows with checkpoints and approval gates
│   ├── monitoring/              system_metrics.py, app_usage.py
│   ├── db/                      client.py (CockroachDB, optional), schema.sql
│   ├── tests/                   pytest suite
│   ├── .env.example             configuration template (copy to .env, git-ignored)
│   ├── pyproject.toml, uv.lock
├── frontend/                    React 19 + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx, main.tsx    shell, navigation, active project
│   │   ├── CompanionApp.tsx     AI work bar (index.html#companion)
│   │   ├── screens/             Dashboard, AI Chat, Tasks, Inbox, Setup, Settings, …
│   │   ├── components/          shared UI (permission prompt, profile card, …)
│   │   ├── lib/                 api.ts (all HTTP), permissions.ts, desktop.ts, usePolling.ts
│   │   └── styles/              design tokens
│   ├── src-tauri/               Tauri 2 shell: tray, agent supervisor, work-bar shortcut, CSP
│   ├── package.json, package-lock.json
├── docs/                        documentation (index: docs/README.md)
│   └── history/                 dated reports and the original design plan
├── scripts/                     dev.ps1 and small utilities
├── .github/                     CI workflow, PR template
├── .claude/rules/, .kilo/rules/ shared rules for AI coding assistants
├── README.md, CONTRIBUTING.md, CHANGELOG.md, SECURITY.md
└── .editorconfig, .gitattributes, .gitignore, .pre-commit-config.yaml, .secrets.baseline
```

Module responsibilities and boundaries: [ARCHITECTURE.md](ARCHITECTURE.md) and
[AGENTS.md](AGENTS.md#4-rules-that-matter-here). Naming and placement rules:
[CONVENTIONS.md](CONVENTIONS.md).
