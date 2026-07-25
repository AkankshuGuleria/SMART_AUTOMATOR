# TECH_STACK.md

> Blanks are filled in as tooling choices are finalized.
> Agents: treat remaining blanks as "ask before assuming a version."

## Frontend
- React — version: 19
- Tauri — version: 2.x
- Tailwind CSS — version: latest (via `@tailwindcss/vite` Vite plugin)
- State management: TBD — must be decided before Phase 3 (RestoreWorkspace UI gains live data)
- Frontend ↔ Python Agent transport: FastAPI + WebSocket over localhost HTTP

## Core Agent
- Python — version: 3.12
- Web framework: FastAPI
- Process/scheduling model: background watcher threads running inside the FastAPI process; watcher threads are daemon threads so they don't block server shutdown
- File watching library: `watchdog`
- Git integration: `GitPython`
- Credential vault: `keyring` (OS-native — Windows Credential Manager on the primary OS, per `SKILLS.md` §8)

## Database
- CockroachDB — version: (fill in once provisioned — confirm it supports Distributed Vector Indexing)
- Driver/ORM: SQLAlchemy + `psycopg2-binary` (CockroachDB dialect — postgresql+psycopg2)
- Vector indexing feature in use: CockroachDB Distributed Vector Indexing
- Embedding model: TBD — name + dimension must be filled in before Phase 2; must match at write time and query time
## AI

- **Ollama** (temporary free backend) — local LLM service, no API keys required
  - Default model: `qwen2.5:7b` (pull with `ollama pull qwen2.5:7b`)
  - Default URL: `http://localhost:11434`
  - Supports both text generation and embeddings
  - Completely free, no rate limits, runs locally
- **Amazon Bedrock** (permanent backend — uncomment in `ai/bedrock_client.py` when keys are available)
  - Model(s) in use: TBD — fill in before Phase 2
  - LiteLLM — not in use (single-model path for MVP; add only if multi-model routing is needed)
- Prompt templates location: `backend/ai/prompts/`

## AWS

- Amazon Bedrock — region: TBD (fill in before Phase 2)
  - **Note:** Bedrock has no permanent free tier. New AWS accounts get up to $200 in credits (6 months).
  - For the free-tier demo, Ollama is used as the default backend instead.
  - Uncomment the Bedrock section in `ai/bedrock_client.py` and fill in `.env` when keys are available.
- Amazon S3 — not used in MVP; stretch goal only
## CockroachDB tooling
- Distributed Vector Indexing — confirmed in use.
- Managed MCP Server — confirmed in use as a consumed service (AUTOMATA is an MCP client, not server) — see `ARCHITECTURE.md` §7 (decided).

## Logging
- Library: Python standard `logging` module
- Configuration: `backend/logging_config.py` — configures root logger, level from `LOG_LEVEL` env var (default `INFO`), consistent formatter (timestamp | level | module | message), stream handler to stdout
- Applied once at startup in `backend/main.py` and `backend/api/server.py`

## Dev tooling
- Package manager (frontend): npm
- Package manager (backend): `uv` (pyproject.toml + uv.lock — NOT requirements.txt; lock file is committed for reproducible installs)
- Linting/formatting: TBD (recommended: `ruff` for Python, `ESLint + Prettier` for TypeScript — add before first PR review)
- Testing frameworks: see `SKILLS.md` → Testing Skill; `pytest` + `pytest-asyncio` for backend, Vitest for frontend

## Environment variables (names only — never commit real values)
```
COCKROACHDB_CONNECTION_STRING=
AWS_REGION=
AWS_BEDROCK_MODEL_ID=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
EMBEDDING_MODEL_ID=
EMBEDDING_DIMENSION=
LOG_LEVEL=INFO
```
Store real values in a local `backend/.env` (gitignored). Never hardcode secrets
in source files or commit them — see `SKILLS.md` §8 for the full checklist.
