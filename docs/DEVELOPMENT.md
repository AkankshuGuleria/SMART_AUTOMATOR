# Development guide

## Prerequisites

| Tool | Version | Used for |
| --- | --- | --- |
| Windows | 10 / 11 | Desktop automation targets Windows |
| Python + [uv](https://docs.astral.sh/uv/) | 3.12+ | Agent (`backend/`) |
| Node.js + npm | 20+ | UI (`frontend/`) |
| Rust (stable) | latest | Desktop app build (`frontend/src-tauri/`) only |
| Ollama | optional | Offline models — Setup & health can install it |
| CockroachDB | optional | Cloud copy of memory; local SQLite memory works without it |

## First run

```powershell
git clone https://github.com/AkankshuGuleria/SMART_AUTOMATOR.git
cd SMART_AUTOMATOR
Copy-Item backend\.env.example backend\.env      # optional — every setting has a default
cd backend;  uv sync --extra dev;  cd ..
cd frontend; npm ci;               cd ..
.\scripts\dev.ps1                               # agent + UI at http://localhost:5173
```

`scripts/dev.ps1` reuses an agent that already answers on `/health`, otherwise
starts one with auto-reload in its own window (moving to a free port if 8000 is
taken), then starts the UI. Flags: `-Desktop` runs the Tauri app in dev mode,
`-BackendOnly` starts only the agent.

Manual equivalent:

```powershell
cd backend;  uv run python main.py         # agent on http://127.0.0.1:8000 (API docs: /docs)
cd frontend; npm run dev                    # UI on http://localhost:5173
cd frontend; npm run tauri dev              # or: the desktop app
```

## Configuration

All settings live in `backend/.env` (git-ignored); see `backend/.env.example`
for the full, commented list and [TECH_STACK.md](TECH_STACK.md#configuration).
Nothing is required: without keys AUTOMATA uses local memory and, if installed,
Ollama. Never put real values in tracked files — see [SECURITY.md](SECURITY.md).

Runtime flags (environment variables):

| Variable | Effect |
| --- | --- |
| `AUTOMATA_DATA_DIR` | Folder for `memory.db`, `tasks.db`, `usage.db`, logs (default `%LOCALAPPDATA%\AUTOMATA`) |
| `AUTOMATA_DISABLE_BACKGROUND=1` | Skip capture, sync, snapshots and task recovery at startup |
| `AUTOMATA_DISABLE_USAGE_TRACKER=1` | No app-usage recording |
| `AUTOMATA_DISABLE_DESKTOP_INPUT=1` | Hard block on synthetic keys and focus (always on in tests) |
| `AUTOMATA_FORCE_ONLINE=0\|1` | Override the connectivity check |
| `AUTOMATA_BACKEND_DIR` | Where the desktop app looks for `backend/main.py` |
| `AUTOMATA_TASK_WATCH_MAX/QUIET/POLL` | Task watch-step timing (seconds) |
| `AUTOMATA_TASK_MODEL_QUESTIONS=0` | Skip model-suggested task questions |
| `VITE_API_BASE`, `VITE_WS_BASE` | UI → agent address (default `127.0.0.1:8000`) |

Optional offline embeddings without Ollama: `uv sync --extra local-ai`, then
`POST /ai/local/offline-embeddings {"enabled": true}`.

## Tests and quality gates

Run these before every commit (CI runs the same — `.github/workflows/ci.yml`):

```powershell
cd backend
uv run pytest tests/ -q                                   # 395 tests
uv run ruff check .                                       # lint + bandit security rules

cd ../frontend
npx tsc -b          # type-check
npx oxlint src      # lint
npm test            # vitest
npm run build       # production build
```

`backend/tests/conftest.py` blanks every database and provider setting before
the app is imported, points data at a temporary folder, disables background
threads and sets `AUTOMATA_DISABLE_DESKTOP_INPUT=1`. Tests therefore never touch
your real database, a paid model API, the keyboard or the screen. New tests must
mock `automation.win32` / `automation.desktop.capture` for anything visual.

Dependency and security audits: see [SECURITY_AUDIT.md §5](SECURITY_AUDIT.md#5-re-running-the-audit).

## Desktop app

```powershell
cd frontend
npx tauri build --no-bundle      # → src-tauri\target\release\app.exe
```

The app supervises the agent: if nothing answers on `127.0.0.1:8000` it starts
`backend\.venv\Scripts\pythonw.exe main.py` (no console) and restarts it if it
dies. It finds `backend/` by walking up from the exe, or via
`AUTOMATA_BACKEND_DIR`. Rust crate versions in `Cargo.lock` must match the
`@tauri-apps/*` npm packages (same major.minor); update both together.

**Start at sign-in** (Settings → Background agent) uses the Tauri autostart
plugin in the desktop app (starts hidden in the tray). In the browser UI the
same switch writes a Startup-folder launcher for the agent only.

## Data and logs

| What | Where |
| --- | --- |
| Local memory, tasks, app usage | `%LOCALAPPDATA%\AUTOMATA\memory.db`, `tasks.db`, `usage.db` |
| Agent log (desktop app / autostart) | `%LOCALAPPDATA%\AUTOMATA\agent.log` |
| Desktop shell log | `%LOCALAPPDATA%\com.automata.dev\logs\AUTOMATA.log` |
| Work bar shortcut | `%APPDATA%\com.automata.dev\workbar.json` |
| Workflow checkpoints | `%LOCALAPPDATA%\AUTOMATA\workflow_checkpoints\` |

## Utility scripts

| Script | Purpose |
| --- | --- |
| `scripts/dev.ps1` | Start agent + UI for development |
| `scripts/check_env.py` | Report which optional cloud settings in `backend/.env` are filled |
| `scripts/check_db_status.py` | Row counts in the optional CockroachDB copy |
| `scripts/seed_project.py` | Register this repository as a project with architecture notes |

Run Python scripts from the repo root with `uv run --project backend python scripts/<name>.py`.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| UI says the agent is offline | `http://127.0.0.1:8000/health`; another program on port 8000; `VITE_API_BASE` |
| No answers offline | Setup & health → Local AI: install Ollama and pull the recommended model |
| Work bar shortcut does nothing | Settings → AI work bar shows whether the shortcut is active; pick another if an app owns it |
| "Unauthorized changes blocked" when Spotify starts | Windows Defender Controlled folder access — see USER_GUIDE.md → Permissions |
| No activity captured | Select a project whose folder exists (Projects screen) |
| Desktop actions fail | They report why (window not found, focus refused); they never pretend to succeed |
