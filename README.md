# SMART_AUTOMATOR (AUTOMATA)

A local-first **AI development workspace for Windows**. It runs in the
background, remembers your work on every project, understands each project's
stack, controls other apps with verified actions, hands multi-step tasks to
Antigravity / Claude / VS Code / ChatGPT, and keeps working offline with a
local model.

## What it does

- **Always on** — tray app that starts at sign-in (optional), supervises the
  Python agent, and opens the **AI work bar** with **Alt+Space** or **Ctrl+Alt+A**: ask, command, play music, search, or read your screen.
- **Remembers your work** — files, commits, terminal, chats, briefs and
  decisions in a local SQLite memory (synced from CockroachDB when configured);
  **Where you left off** snapshots and one-click **Resume workspace**.
- **Understands each project** — detects stack, run/test/build commands, ports,
  required env vars and modules from the project's own files.
- **Delegates work** — "using antigravity create a landing page": writes a
  grounded prompt, waits for your approval, hands it off, watches for changes,
  runs the build, and lists the keys and connection strings it still needs
  (**Needs from you** inbox → Windows Credential Manager or `.env`).
- **Controls the desktop honestly** — focus apps, type, paste, list/switch
  browser tabs, read the screen (Windows OCR); every action confirms its effect.
- **Monitors** CPU / GPU / RAM / disk / processes and where your time goes.
- **Offline AI** — cloud models when online, Ollama when offline; Setup screen
  installs Ollama and picks a model for your GPU.

## Quick start

```powershell
# 1. backend (Python 3.12 + uv)
cd backend
copy .env.example .env          # optional: CockroachDB / cloud API keys
uv sync --extra dev
uv run python main.py           # http://127.0.0.1:8000/docs

# 2. UI (Node 20+)
cd frontend
npm ci
npm run dev                     # http://localhost:5173

# 3. desktop app (Rust stable) — tray, autostart, starts the backend for you
npx tauri build --no-bundle     # → frontend\src-tauri\target\release\app.exe
```

Then open **Setup & health** in the app to see what is configured.

## Documentation

- [Start here (agents & contributors)](docs/AGENTS.md)
- [Project status & feature checklist](docs/PROJECT_STATUS.md)
- [User guide](docs/USER_GUIDE.md)
- [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API_REFERENCE.md) · [Data stores](docs/DATABASE_SCHEMA.md)
- [Development](docs/DEVELOPMENT.md) · [Security](docs/SECURITY.md) · [Tech stack](docs/TECH_STACK.md)
- [Smart workspace plan](docs/SMART_WORKSPACE_PLAN.md) · [Roadmap](docs/ROADMAP.md) · [QA checklist](docs/QA_CHECKLIST.md)
- [Full documentation index](docs/README.md)

## Boundaries

Single developer, single Windows machine. The API listens on 127.0.0.1 only
and has no authentication — do not expose it to a network.
