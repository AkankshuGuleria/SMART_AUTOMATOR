# Architecture

## 1. System overview

```text
Tauri desktop shell (tray, autostart, single instance, backend supervisor)
  └─ React UI  ──HTTP/WebSocket (127.0.0.1:8000)──►  FastAPI agent
                                                     │
   memory/ ─────────── capture → local_store (SQLite, offline) ◄─sync─ db/ (CockroachDB, optional)
   workspace/ ──────── active project, session snapshots, resume
   intelligence/ ───── project profile (stack, run book, env, modules)
   ai/ ─────────────── model router: cloud providers → Bedrock → Ollama (offline)
   decision_engine/ ── chat intents → planner (policies) → tools
   tasks/ ──────────── delegation tasks with approval gates, Needs inbox
   automation/ ─────── verified desktop control (desktop.py, win32, uia, ocr), agent bridge
   workflow_engine/ ── checkpointed YAML workflows
   monitoring/ ─────── system metrics, app-usage tracking
```

The frontend is a presentation and interaction layer. The Python backend
coordinates application behavior and is the only application layer that
accesses CockroachDB or reasoning providers.

## 2. Runtime lifecycle

The Tauri shell (`frontend/src-tauri/src/lib.rs`) starts hidden in the tray
when launched with `--hidden` (autostart), checks `127.0.0.1:8000` every 10 s
and starts `backend/.venv/Scripts/pythonw.exe main.py` when nothing answers
(at most 3 restarts per minute). Closing the window hides it.

`backend/main.py` configures logging (a rotating file under the data folder
when there is no console) and runs uvicorn. The FastAPI **lifespan** starts all
background work: system sampler, app-usage tracker, memory sync, the capture
manager (follows the last active project, else the newest project with a real
folder), the snapshot thread, and recovery of interrupted tasks. Shutdown saves
a final snapshot. `AUTOMATA_DISABLE_BACKGROUND=1` skips these (tests).

## 3. Components

### 3.1 Frontend

`frontend/src/App.tsx` owns navigation and app-level state. Screens live in
`frontend/src/screens/`; reusable controls and layouts live in
`frontend/src/components/`; network types and calls live in `frontend/src/lib/`.
The Tauri shell is under `frontend/src-tauri/`.

### 3.2 API

`backend/api/server.py` exposes health/configuration, project/session, memory,
chat, workflow, automation, agent-action, analytics, diagnostic, system-metric
and app-usage routes. Routes that touch the database, git, OS or a model
provider are plain `def` handlers so FastAPI runs them in its threadpool; a
slow model call never blocks other requests.
It also publishes WebSocket events used for live activity and action progress.
The API reference is in [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

### 3.3 Persistent memory

`backend/memory/capture.py` observes selected activity. Captured text passes
through secret redaction before persistence. `memory/embeddings.py` supplies
embeddings when a configured provider is available, and
`memory/retrieval.py` implements recent and vector-based retrieval.
All database access is centralized in `backend/db/client.py`.

### 3.4 Reasoning

`backend/ai/bedrock_client.py` centralizes reasoning and embedding provider
integrations, timeout/error handling, and provider fallback behavior. The
planner supplies retrieved project context to reasoning tasks. Factual
responses should not imply facts unsupported by retrieved memories.

### 3.5 Decision engine

`backend/decision_engine/` parses user intent, selects tools, applies action
policies, and handles explicit triggers such as commit/session events. It
records decision provenance and routes actions through the common tool layer.

### 3.6 Automation

`backend/automation/` contains Windows OS operations, workspace restore,
development-server control, command execution, external-agent bridges, screen
capture, and OCR. It must report failures to the caller; it must not write
directly to CockroachDB.

Cross-app and visual actions have one implementation, `automation/desktop.py`,
built on `automation/win32.py`. Each action confirms its effect before
reporting success: focus is read back from Windows, keys are only sent to a
verified target (never to AUTOMATA itself), and a prompt handoff stops before
pressing Enter if the target window is not in front. OCR uses the built-in
Windows engine via `automation/windows_ocr.ps1`.

`automation/chat_apps.py` hands prompts to AI apps' chat boxes. Per-app recipes
(window exe, accessible name of the chat box, shortcut that opens the panel,
"new conversation" button) come from probing the real apps: Antigravity IDE and
the Antigravity desktop app both expose **"Message input"**. Delivery: find or
launch the window (IDE opened on the task folder) → activate → find the box via
UI Automation (pressing Ctrl+L if the panel is closed) → refuse if it holds a
draft → `SetFocus` → paste → read back through the UIA Text pattern (OCR
fallback) → only when allowed press Enter and confirm the box emptied.

`automation/no_console.py` patches `subprocess.Popen` at startup so every child
process gets `CREATE_NO_WINDOW` unless it asks for `CREATE_NEW_CONSOLE` (terminal,
installer, dev servers). The agent runs windowless (`pythonw`), so without this
each PowerShell/git/CLI call flashed a console window over the user's work.

### 3.6a Work bar and quick assist

`assist/commands.py` recognises everyday commands with regexes and runs them
locally; `/chat` and `POST /assist` call it first and fall through to the normal
chat path when nothing matches. `assist/media.py` presses system media keys
(play/pause/next/previous/volume) and reads "now playing" from the Windows media
session (`assist/media_session.ps1`); Spotify search-and-play opens
`spotify:search:<q>`, invokes the top result's Play button through UI
Automation and confirms the player switched to Pause. `assist/screen.py`
captures the front-most non-AUTOMATA window with `PrintWindow` (correct even
when the bar covers it), OCRs it, deletes the image and sends only redacted text
to the model, and only when the user asks. The Tauri shell registers Alt+Space
and Ctrl+Alt+A (toggle on key-down only), places the frameless, transparent bar
at the top centre of the cursor's monitor and hides it on blur.

### 3.7 Workflow engine

`backend/workflow_engine/` executes versioned YAML workflows, resolves step
inputs, persists checkpoints, and pauses at policy-derived approval gates.
Workflow side effects call registered decision-engine tools rather than
performing OS operations directly.

### 3.8 Monitoring

`backend/monitoring/` holds local device telemetry, started with the API
(FastAPI lifespan):

- `system_metrics.py` — a daemon sampler for CPU, GPU (NVIDIA via NVML),
  RAM, disk, network and battery. It samples every 2 s while a client is
  reading metrics and every 15 s otherwise; the ~200 ms process scan runs
  only on request and is cached for 8 s.
- `app_usage.py` — a daemon tracker that polls the foreground window once a
  second (Win32 `GetForegroundWindow`, `GetLastInputInfo`), skips idle time
  (2 min without input), and stores one row per focus segment in a local
  SQLite file (`%LOCALAPPDATA%\AUTOMATA\usage.db`). Window titles are
  redacted and truncated. Data older than 90 days is pruned.

App usage is deliberately not stored in CockroachDB: it is high-frequency,
personal, and must keep working when the database is unreachable.
`automation/autostart.py` can add a hidden Startup-folder launcher so the
agent (and these trackers) run whenever the user is signed in.

### 3.9 Local memory and continuity

- `memory/local_store.py` — SQLite (`memory.db`): projects, memories (kind,
  content, ref, meta, optional float32 vector), FTS5 index, snapshots, kv.
  Writes are idempotent via `(project_id, kind, ref)`. Search blends BM25 with
  cosine similarity when vectors exist.
- `memory/sync.py` — on start and every 15 min mirrors recent cloud rows into the
  local store (`ref = db:<table>:<id>`); every minute embeds memories without a
  vector when a local embedding model (fastembed or Ollama) is available.
- `db/client.py` — project CRUD falls back to the local store when CockroachDB
  is unreachable, so the workspace works offline.
- `workspace/capture_manager.py` — one set of capture threads following the
  active project (`POST /projects/{id}/activate`).
- `workspace/snapshot.py` — snapshots (branch, changed/recent files, open dev
  windows, dev servers by port + cwd, TODOs, last chat, current task) every 10
  min, on idle and on shutdown; `resume()` reopens editor/terminal/servers.

### 3.10 Project intelligence

`intelligence/profile.py` walks the repo (bounded, ignoring build/vendor
folders) and detects languages, frameworks, databases, package managers,
infrastructure, ports, a run book per app, environment variables (declared in
`.env.example` or referenced in non-test code; *set* only when a real `.env`
has a value or the example ships a default) and modules from the folder
structure. `score_modules()` explains each readiness score (tests, TODOs,
recent edits). Profiles are cached in the local store for 10 min
(`PROFILE_VERSION` busts the cache). `prompt_context()` feeds chat and agent
prompts.

### 3.11 Model routing

`ai/bedrock_client.py` checks connectivity (`is_online`, cached 30 s). Online:
Groq → OpenRouter → Gemini → Cohere → NVIDIA → MiniMax → Bedrock → Ollama.
Offline: Ollama only, no cloud timeouts. Ollama is probed with a 150 ms TCP
check first (a refused connection costs ~2 s on Windows). `LAST_ANSWER`
records which provider answered. `ai/local_models.py` recommends, pulls and
selects local models.

### 3.12 Tasks and the Needs inbox

`tasks/engine.py` runs delegation tasks: **clarify (input)** → context → prompt →
**handoff (approval)** → watch file changes → **verify build/tests (approval)** → needs →
report. Each step persists its output in `tasks.db`; approval steps block until
`approve()`. The clarify step (`tasks/questions.py`) asks where to work (project
folder or where to save a new project), stack, features, design and anything
else, plus up to two model-suggested questions (time-boxed); the task waits in
`waiting_input` until `POST /tasks/{id}/answer`. The chosen folder is created
then, becomes the task's working folder, and the answers go into the prompt.
Interrupted tasks are marked `paused` on startup. The hand-off uses
`automation/agent_bridge.py`: Claude Code CLI (`claude -p`) or `cursor-agent`
when installed; otherwise the verified chat-box delivery in
`automation/chat_apps.py` (Antigravity IDE/app, Cursor, Claude app); VS Code via
`code chat --mode agent -` (reported as unconfirmed); clipboard + manual
instructions as the last resort. `tasks/needs.py` turns unset keys/connection strings into Inbox
items with provider instructions; values go to Windows Credential Manager
and/or the project's `.env` only.

### 3.13 Persistence (cloud)

`backend/db/schema.sql` is the canonical DDL. It stores project-scoped
activity and workflow records, plus developer-scoped taste preferences.
Embedding columns use `VECTOR(1024)`; see [the data model](DATABASE_SCHEMA.md).

## 4. Principal data flows

### Capture

```text
file/git/terminal event
  -> background capture thread
  -> redaction and normalization
  -> db/client.py structured write
  -> embedding generation when supported and applicable
  -> vector stored with the memory row
```

### Query

```text
UI question
  -> POST /query or POST /chat
  -> local memory search (BM25 + local vectors), then cloud vector search
  -> project profile facts added to the system prompt
  -> reasoning provider composes a grounded answer or plan
  -> API returns answer, sources, and/or action cards
  -> approved action executes through registered tools
```

### Autonomous trigger

```text
commit/session event
  -> explicit trigger
  -> planner classifies passive action vs. suggestion/approval
  -> registered action runs or waits for user confirmation
  -> decision provenance is persisted
```

## 5. Trust boundaries and failures

- The UI-to-API boundary is local HTTP/WebSocket; the current service is not a
  public authenticated API.
- The backend-to-provider boundary may send query text and selected memory
  context to a configured external provider.
- The backend-to-OS boundary can launch processes or interact with windows;
  changes must follow approval policy.
- Database, model, OCR, and OS dependencies can be absent. Their failure must
  be reported distinctly from success; see [Security](SECURITY.md).

## 6. Deployment constraints

The supported development/demo target is one Windows machine with local UI
and API processes. CockroachDB and model providers may be local or remote.
There is no documented production deployment, multi-user authentication, or
cross-platform automation guarantee.
