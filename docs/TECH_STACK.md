# Technology stack

Version ranges in the manifests are authoritative; lockfiles (`backend/uv.lock`,
`frontend/package-lock.json`, `frontend/src-tauri/Cargo.lock`) pin resolved
versions for reproducible installs. Versions below are the locked ones at the
last audit (2026-10-26).

## Agent (backend)

| Area | Choice | Notes |
| --- | --- | --- |
| Runtime | Python 3.12, managed with **uv** | `backend/pyproject.toml` |
| API | FastAPI 0.139, Uvicorn 0.51 | Binds `127.0.0.1:8000`; guarded by `security/http_guard.py` |
| Local memory | SQLite (stdlib) with FTS5 | `memory.db`, `tasks.db`, `usage.db`; optional float32 vectors |
| Cloud memory (optional) | CockroachDB via SQLAlchemy 2.0 + psycopg2 | `VECTOR(1024)` columns, `db/schema.sql` |
| Activity capture | watchdog 6, GitPython 3.2.1 | Generated folders (`node_modules`, `.venv`, `.git`, `dist`, `target`) ignored |
| Desktop control | ctypes Win32, comtypes 1.4 (UI Automation), Windows.Media.Ocr via PowerShell | Verified actions only |
| Monitoring | psutil 7, nvidia-ml-py 13 (NVML) | Non-NVIDIA GPUs report "unavailable" |
| Secrets | keyring 25 → Windows Credential Manager | Needs inbox values |
| Models | Groq, OpenRouter, Gemini, Cohere, NVIDIA, MiniMax, Amazon Bedrock (boto3), Ollama | All calls in `ai/bedrock_client.py`; offline → Ollama |
| Offline embeddings (optional) | fastembed (`--extra local-ai`) | Or Ollama `nomic-embed-text` |
| Tests and quality | pytest 8, ruff, bandit, pip-audit, detect-secrets, pre-commit | `--extra dev` |

## UI (frontend)

| Area | Choice |
| --- | --- |
| Framework | React 19, TypeScript 6, Vite 8.3 |
| Styling | Tailwind CSS 4, CSS design tokens (`src/styles/globals.css`) |
| Motion and charts | Framer Motion 12, Recharts 3 (loaded only on chart screens) |
| Icons | lucide-react |
| Tests and lint | Vitest 4.1.12, Testing Library, oxlint |

## Desktop shell

| Area | Choice |
| --- | --- |
| Shell | Tauri 2 (Rust stable), WebView2 |
| Plugins | tray-icon, single-instance, autostart, notification, global-shortcut, log |
| Windows integration | webview2-com 0.39 (keyboard focus for the work bar) |
| Security | Strict Content Security Policy in `tauri.conf.json`; minimal capabilities |

## Configuration

Loaded from `backend/.env` (git-ignored) and the process environment. Every
setting is optional; `backend/.env.example` documents each one.

| Variable | Purpose |
| --- | --- |
| `COCKROACHDB_CONNECTION_STRING` | Cloud copy of memory |
| `REASONING_MODE` | `auto` (cloud → Bedrock → Ollama), `local`, `cloud` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL`, `OLLAMA_MODELS` | Local models (URL must be http/https) |
| `GROQ_API_KEY`, `GROQ_EMBEDDING_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `GEMINI_API_KEY`, `COHERE_API_KEY`, `NVIDIA_API_KEY`, `MINIMAX_API_KEY` | Cloud providers |
| `AWS_REGION`, `AWS_BEDROCK_MODEL_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Amazon Bedrock |
| `EMBEDDING_MODEL_ID`, `EMBEDDING_DIMENSION` | Cloud embedding model (dimension must match the schema) |
| `LOG_LEVEL` | Python log level |

Runtime flags (`AUTOMATA_*`, `VITE_*`): see [DEVELOPMENT.md](DEVELOPMENT.md#configuration).
