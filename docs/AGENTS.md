# AGENTS.md — start here (for AI coding agents and new contributors)

Read this file first. It gives you enough context to work safely in this
repository without re-discovering everything. Last full update: 2026-10-26.

## 1. What this product is

**AUTOMATA** (repository `SMART_AUTOMATOR`) is a local-first
**AI development workspace for one developer on Windows**. It:

- runs in the background (Tauri tray app that supervises a Python agent) and
  starts at sign-in if the user enables it;
- remembers work per project (files, commits, terminal, chats, briefs,
  decisions, session snapshots) in a **local SQLite memory** that works
  offline, with CockroachDB as optional cloud sync;
- understands each project from its files (stack, run book, env vars,
  modules) instead of showing a fixed template;
- controls other apps with **verified** actions (focus, type, paste, browser
  tabs, OCR read-back) — always after asking the user — and hands multi-step
  tasks to Antigravity / Kilo Code / Claude / Cursor / VS Code / ChatGPT, then
  tracks what is still needed from the user;
- offers an AI work bar (Alt+Space) for questions, music, search and screen reading;
- monitors the machine (CPU/GPU/RAM/disk) and which apps the user spends time in;
- uses cloud LLMs when online and a local Ollama model when offline.

Product status, the feature checklist and what is left: `docs/PROJECT_STATUS.md`.
Security model and the latest audit: `docs/SECURITY.md`, `docs/SECURITY_AUDIT.md`.

## 2. Repository map

```
backend/                 Python 3.12 FastAPI agent (uv)
  main.py                entry: python main.py  → uvicorn api.server:app on 127.0.0.1:8000
  api/server.py          core routes (projects, chat, brief, restore, analytics…) + lifespan
  api/workspace_routes.py  smart-workspace routes (AI setup, memory, snapshots, profile,
                         desktop, tasks, needs, self-check)
  ai/bedrock_client.py   ALL model calls: cloud providers → Bedrock → Ollama; offline detection;
                         local embeddings; LAST_ANSWER (which provider answered)
  ai/local_models.py     Ollama recommendation / pull / select / installer launch
  memory/local_store.py  local SQLite memory (FTS5 + optional vectors), projects, snapshots, kv
  memory/sync.py         mirrors cloud rows into local memory; fills local vectors
  memory/capture.py      file watcher, git poller, terminal capture (+ secret redaction)
  workspace/             capture_manager (follows active project), snapshot (save/resume)
  intelligence/          profile.py (stack/run book/env/modules), providers.py (env var → how-to)
  automation/desktop.py  THE verified desktop layer: focus, press, type, paste, tabs, capture,
                         OCR read-back, verify, prompt handoff
  automation/win32.py    ctypes Win32 (windows, foreground, keys, unicode, DPI-correct PNG capture)
  automation/uia.py      UI Automation (focused field text, browser tabs) via comtypes
  automation/ocr.py      Windows OCR (windows_ocr.ps1) → Tesseract fallback
  automation/agent_bridge.py  picks the hand-off path: CLI, chat-box adapter, VS Code chat CLI, clipboard
  automation/chat_apps.py  verified paste into AI apps' chat boxes (Antigravity, Kilo Code, Cursor, Claude), agent_busy()
  automation/no_console.py  CREATE_NO_WINDOW for every child process (no console popups)
  assist/                 work bar quick commands: media keys + Spotify, web search, read screen
  security/               permissions (ask before PC control), http_guard (local-only API), defender
  tasks/                 engine (clarify questions → ... → approval gates), questions, store (tasks.db), needs
  monitoring/            system_metrics (CPU/GPU/RAM…), app_usage (foreground-app tracker)
  decision_engine/       intent_parser (regex intents) → planner (actions + policies) → tools
  workflow_engine/       YAML workflows with checkpoints and gates
  db/client.py           ALL CockroachDB access (falls back to the local store when offline)
  tests/                 pytest (395 tests); conftest isolates DB/providers/input
frontend/                React 19 + Vite + TypeScript UI, Tauri 2 shell in src-tauri/
  src/App.tsx            navigation, active project, badges, health
  src/lib/api.ts         ALL HTTP calls + types;  src/lib/usePolling.ts  visibility-aware polling
  src/screens/           Dashboard, AIChat, Tasks, Inbox, Setup, Resources, Memory, Projects…
  src/CompanionApp.tsx   AI work bar, Alt+Space, changeable in Settings (index.html#companion)
  src-tauri/src/lib.rs   tray, close-to-tray, single instance, autostart, backend supervisor
docs/                    all documentation (this file, architecture, API, schema, status…)
```

Local data lives in `%LOCALAPPDATA%\AUTOMATA\` (`memory.db`, `tasks.db`,
`usage.db`, `agent.log`, `task_baselines/`), overridable with `AUTOMATA_DATA_DIR`.

## 3. Run and test

```powershell
.\scripts\dev.ps1                                             # agent + UI (-Desktop: Tauri app)
# backend
cd backend; uv sync --extra dev; uv run python main.py      # http://127.0.0.1:8000/docs
uv run pytest tests/ -q                                       # must stay green
uv run ruff check .                                           # + security lint, see DEVELOPMENT.md
# frontend
cd frontend; npm ci; npm run dev                              # http://localhost:5173
npx tsc -b; npx oxlint src; npm test                          # type-check, lint, tests
# desktop app (needs Rust stable)
npx tauri build --no-bundle    # → frontend/src-tauri/target/release/app.exe
```

CI (`.github/workflows/ci.yml`) runs the same checks on every push and pull request.

## 4. Rules that matter here

1. **Module boundaries.** DB access only through `db/client.py` (cloud) or
   `memory/local_store.py` (local). Model calls only through
   `ai/bedrock_client.py`. Desktop effects only through `automation/desktop.py`
   (never call `win32.send_chord` directly from new code).
2. **Never report success you did not verify.** Desktop actions confirm the
   foreground window / read text back; unknown checks fail; a handoff never
   presses Enter unless the paste was confirmed. Keep it that way.
3. **Tests never touch the real world.** `tests/conftest.py` blanks DB and
   provider settings, sets a temp `AUTOMATA_DATA_DIR`, forces
   `AUTOMATA_FORCE_ONLINE=1`, disables the usage tracker/background threads and
   sets `AUTOMATA_DISABLE_DESKTOP_INPUT=1` (hard kill-switch for synthetic
   keys/focus). Mock `automation.win32` / `automation.desktop.capture` in new
   tests; never send real keystrokes or read the real screen.
4. **Secrets.** Never write real keys anywhere in the repo. Captured text goes
   through `memory.capture.redact_secrets`. The Needs inbox writes values only
   to Windows Credential Manager (`keyring`, service `AUTOMATA:<project_id>`)
   or the project's `.env` — never to AUTOMATA's databases or logs. The profile
   reads env var *names*, never values.
5. **Approval gates.** Task steps `handoff` and `verify` require explicit user
   approval (`POST /tasks/{id}/approve`). Anything that controls the PC goes
   through `security/permissions.check()` (or a chat approval card). Never accept a
   caller-supplied "approved" flag, and never add auto-approval.
6. **Windows-first.** Automation targets Windows 10/11. Other platforms must
   fail with a clear message, not crash.
7. **Output style.** Short, factual, no chatbot filler; say "No memory found for
   that query" instead of inventing (`.claude/rules/output_naturalness.md`).

## 5. When you change things

- New/changed endpoint → `docs/API_REFERENCE.md`. New store/table →
  `docs/DATABASE_SCHEMA.md`. New module/data flow → `docs/ARCHITECTURE.md`.
  New dependency → `docs/TECH_STACK.md`. Feature status → `docs/PROJECT_STATUS.md`.
- Add tests next to the feature (`backend/tests/test_<area>.py`,
  `frontend/src/**/X.test.tsx`) that assert real outputs and failure states.
- Security-relevant change → regression test in `tests/test_permissions.py`
  and a line in `docs/SECURITY_AUDIT.md` if it fixes a finding.
- Notable change → `CHANGELOG.md` (Unreleased). See `CONTRIBUTING.md`.
- Commit only when the user asks.

## 6. Useful entry points for common requests

| Request | Start in |
| --- | --- |
| "AUTOMATA should do X when I say Y in chat" | `decision_engine/intent_parser.py` → `planner.py` (`_get_actions_for_trigger`, `ACTION_POLICY`, `_execute_action`) → `api/server.py` `trigger_by_intent` |
| Control another app / OCR | `automation/desktop.py` (+ `uia.py`, `win32.py`, `ocr.py`) |
| Hand work to an AI app | `tasks/engine.py` (steps), `tasks/questions.py`, `automation/agent_bridge.py`, `automation/chat_apps.py` |
| Work bar / quick commands (music, search, screen) | `assist/commands.py`, `assist/media.py`, `assist/screen.py`, `frontend/src/CompanionApp.tsx` |
| Project-specific analysis | `intelligence/profile.py` |
| Memory / offline | `memory/local_store.py`, `memory/sync.py`, `ai/bedrock_client.py` |
| Background / startup | `frontend/src-tauri/src/lib.rs`, `automation/autostart.py` |
| New screen | `frontend/src/lib/screens.ts`, `App.tsx`, `FloatingSidebar.tsx`, `CommandPaletteV2.tsx` |
