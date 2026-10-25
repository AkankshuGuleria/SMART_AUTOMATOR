# Architecture

## 1. System overview

```text
React + Tauri desktop UI
        | HTTP + WebSocket (loopback)
        v
FastAPI service (backend/api/server.py)
        |
        +-- memory/ ------------ capture, embedding, retrieval
        +-- db/ ---------------- CockroachDB access and schema
        +-- ai/ ---------------- reasoning and provider integrations
        +-- decision_engine/ --- intents, plans, tools, triggers
        +-- workflow_engine/ --- checkpointed multi-step execution
        +-- automation/ -------- Windows and external-app actions
```

The frontend is a presentation and interaction layer. The Python backend
coordinates application behavior and is the only application layer that
accesses CockroachDB or reasoning providers.

## 2. Runtime lifecycle

`backend/main.py` loads configuration, resolves the newest registered project
whose repository path exists, starts file/git/terminal capture threads for
that project, and launches the API on `127.0.0.1:8000`. The UI uses the
typed client in `frontend/src/lib/api.ts` for HTTP and WebSocket communication.

Capture threads are daemon threads. They report through `backend/db/client.py`;
capture is not started when there is no usable registered local project.

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

### 3.9 Persistence

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
  -> retrieve relevant project memories
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
