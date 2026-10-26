# Development setup

## Prerequisites

- Windows 10/11 for the supported OS automation path.
- Python 3.12+ and `uv`.
- Node.js 20+ and npm.
- A CockroachDB database with support for the schema's `VECTOR(1024)` columns.
- Optional: Ollama with a reasoning model and embedding model, or configured
  cloud provider credentials.

## Configure the backend

From the repository root:

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` locally. Set `COCKROACHDB_CONNECTION_STRING` to a
development/test database. Keep real credentials out of source control.
See [the security guide](SECURITY.md) and `TECH_STACK.md` for supported
configuration names.

Install dependencies and start the API:

```powershell
Set-Location backend
uv sync
uv run python main.py
```

The API binds to `127.0.0.1:8000`. Check `http://127.0.0.1:8000/health` and
open `http://127.0.0.1:8000/docs` for the API reference.

If initializing a fresh database, use the canonical
`backend/db/schema.sql` with a disposable development database. Do not run
schema experiments against production data.

## Configure and start the frontend

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

The default API base is `http://127.0.0.1:8000`. For a different local API
address, configure `VITE_API_BASE` and `VITE_WS_BASE` before starting Vite.
The convenience script `npm run dev:with-backend` also starts or reuses a
local backend and sets these values.

## Desktop shell

With frontend dependencies installed and the backend configured, run the
Tauri development command from `frontend`:

```powershell
npm run tauri dev
```

Desktop behavior, global shortcuts, and Windows automation should be
validated on the intended machine; browser-only development does not verify
the desktop shell.

## Tests and quality checks

```powershell
Set-Location backend
uv sync --extra dev   # once: installs pytest/ruff into backend/.venv
uv run pytest tests/ -v --tb=short
```

`tests/conftest.py` blanks every database and provider setting before the
backend is imported, so tests never touch the real CockroachDB cluster or a
paid model API even when `backend/.env` is filled in. It also disables the
app-usage tracker (`AUTOMATA_DISABLE_USAGE_TRACKER=1`).

```powershell
Set-Location frontend
npm test
npm run build
npm run lint
```

Tests must use mocks/fixtures for model services and OS effects. Integration
tests requiring CockroachDB must use an explicitly provisioned local/test
instance. See [the QA checklist](QA_CHECKLIST.md).

## Background agent

Settings → Background agent → **Start at sign-in** writes
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AUTOMATA Agent.vbs`,
which starts `backend\.venv\Scripts\pythonw.exe backend\main.py` with no
console. Logs then go to `%LOCALAPPDATA%\AUTOMATA\agent.log`. Turning the
switch off deletes the launcher. Set `AUTOMATA_DISABLE_USAGE_TRACKER=1` to
run the backend without app-usage recording; `AUTOMATA_DATA_DIR` moves the
usage database.

## Troubleshooting

- **Database unavailable:** check the local `.env` path and connection string;
  the backend can start in a disconnected state but memory will not persist.
- **No project capture:** register a project whose repository path exists;
  startup capture selects an available registered project.
- **No local model:** start Ollama and pull the selected models, or configure
  an available cloud provider.
- **Frontend shows backend offline:** check the API health URL, local port,
  and `VITE_API_BASE`.
- **Automation/OCR unavailable:** check Windows desktop permissions and
  optional application/OCR dependencies. These failures should be reported,
  not treated as successful actions.

## Desktop app build

Requires Rust stable (`rustup default stable`) plus the npm deps.

```powershell
cd frontend
npx tauri build --no-bundle   # → src-tauri\target\release\app.exe
```

Rust crate versions in `src-tauri/Cargo.lock` must match the `@tauri-apps/*`
npm packages (same major.minor) or the build stops; update with
`cargo update -p tauri -p tauri-plugin-autostart -p tauri-plugin-notification`.
The app finds `backend/` by walking up from the exe (or `AUTOMATA_BACKEND_DIR`).

## Environment flags

| Variable | Effect |
| --- | --- |
| `AUTOMATA_DATA_DIR` | Folder for memory.db, tasks.db, usage.db, logs (default `%LOCALAPPDATA%\AUTOMATA`) |
| `AUTOMATA_DISABLE_BACKGROUND=1` | Skip capture, sync, snapshots and task recovery at startup |
| `AUTOMATA_DISABLE_USAGE_TRACKER=1` | No app-usage recording |
| `AUTOMATA_DISABLE_DESKTOP_INPUT=1` | Hard block on synthetic keys/focus (always on in tests) |
| `AUTOMATA_FORCE_ONLINE=0\|1` | Override the connectivity check |
| `AUTOMATA_BACKEND_DIR` | Where the desktop app looks for `backend/main.py` |
| `AUTOMATA_TASK_WATCH_MAX/QUIET/POLL` | Task watch-step timing (seconds) |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL`, `OLLAMA_MODELS` | Local model server, defaults, model storage folder |

Optional offline embeddings without Ollama: `uv sync --extra local-ai`, then
enable them via `POST /ai/local/offline-embeddings`.
