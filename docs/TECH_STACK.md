# Technology and configuration

This file records the runtime and dependency sources used by the repository.
Version ranges in manifests are authoritative; lock files pin resolved
versions for reproducible installs.

## Frontend and desktop

- React 19, TypeScript, Vite, Framer Motion, Recharts and lucide-react.
- Secondary screens are lazy-loaded; the chart library downloads only when a
  chart screen opens. Polling uses `src/lib/usePolling.ts`, which pauses
  while the window is hidden.
- Tauri 2 desktop shell under `frontend/src-tauri/` with `tray-icon`,
  `tauri-plugin-autostart`, `tauri-plugin-single-instance`,
  `tauri-plugin-notification`, `tauri-plugin-global-shortcut` (Alt+Space, Ctrl+Alt+A).
  JS side: `@tauri-apps/api`, `@tauri-apps/plugin-autostart`,
  `@tauri-apps/plugin-notification` (loaded lazily via `src/lib/desktop.ts`).
- npm and `frontend/package-lock.json`.
- HTTP/WebSocket access to FastAPI through `frontend/src/lib/api.ts`.

## Backend

- Python 3.12+, FastAPI, and Uvicorn.
- `uv` with `backend/pyproject.toml` and `backend/uv.lock`.
- SQLAlchemy + psycopg2 for CockroachDB.
- Watchdog and GitPython for activity capture (generated folders such as
  `node_modules`, `.venv`, `.git`, `dist`, `target` are ignored).
- psutil for host metrics and process names; nvidia-ml-py (NVML) for NVIDIA
  GPU metrics. Other GPUs report "unavailable".
- SQLite (standard library) for local app-usage history.
- pytest for backend tests; Ruff is configured in the backend manifest.

## Data and model providers

- CockroachDB is the structured memory store and supports the `VECTOR(1024)`
  columns in `backend/db/schema.sql`.
- `backend/ai/bedrock_client.py` owns supported reasoning/embedding provider
  calls and fallback behavior.
- Ollama is supported for local reasoning/embeddings. Cloud provider support
  is optional and depends on environment configuration.
- Use compatible embedding models and dimensions for both write and query
  paths; see `DATABASE_SCHEMA.md`.

## OS and integrations

- Windows is the supported automation target.
- Automation uses Python/PowerShell and Windows facilities for process,
  clipboard, window, screen-capture, and credential-store operations.
- OCR support depends on the configured/installed OCR path.
- External app or model integrations are optional and should be treated as
  external data-sharing boundaries.

## Environment variables

Backend configuration is loaded from `backend/.env` (if present) and the
process environment. Start from `backend/.env.example`; keep real values out
of source control.

| Variable | Purpose |
| --- | --- |
| `COCKROACHDB_CONNECTION_STRING` | CockroachDB connection |
| `REASONING_MODE` | `auto`, `local`, or `cloud` reasoning selection |
| `OLLAMA_BASE_URL` | Ollama service URL |
| `OLLAMA_MODEL` | Local reasoning model |
| `OLLAMA_EMBEDDING_MODEL` | Local embedding model |
| `AWS_REGION`, `AWS_BEDROCK_MODEL_ID` | Optional Bedrock configuration |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Optional AWS credentials; prefer managed credentials when available |
| `GROQ_API_KEY`, `GROQ_EMBEDDING_API_KEY` | Optional Groq reasoning/embedding credentials |
| `GEMINI_API_KEY` | Optional Gemini credential |
| `NVIDIA_API_KEY` | Optional NVIDIA credential |
| `MINIMAX_API_KEY` | Optional MiniMax credential |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Optional OpenRouter configuration |
| `COHERE_API_KEY` | Optional Cohere credential |
| `EMBEDDING_MODEL_ID`, `EMBEDDING_DIMENSION` | Optional explicit embedding configuration |
| `LOG_LEVEL` | Python log level |

`API_KEY` is read by configuration code but is not evidence that the FastAPI
routes enforce authentication. Treat the current service as a trusted local
development process; see `docs/SECURITY.md`.

## Smart-workspace additions

- **SQLite** (stdlib, FTS5) for local memory, tasks and usage.
- **comtypes** for Windows UI Automation (`automation/uia.py`).
- **Windows.Media.Ocr** through `automation/windows_ocr.ps1` (no extra install).
- **keyring** for Windows Credential Manager (Needs inbox).
- **Ollama** (optional, user-installed) for offline chat/embeddings;
  recommended `qwen2.5-coder:3b` + `nomic-embed-text` on a 4 GB GPU.
- **fastembed** (optional extra `local-ai`) for offline embeddings without Ollama.
- **Rust stable** to build the desktop shell.
