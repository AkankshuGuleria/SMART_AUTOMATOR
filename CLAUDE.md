# AUTOMATA — Claude Code Instructions

## Project
Autonomous developer agent using **CockroachDB** (persistent memory + vector indexing + Managed MCP Server) and **Amazon Bedrock** (reasoning). Hackathon submission — hard deadline.

## Current phase
**Phase 0 - In Progress** (`TASK.md` TASK-002 is partially complete; TASK-005+ remain blocked until CockroachDB is provisioned)

## Read before any code change
`PROJECT.md` → `ARCHITECTURE.md` → `DATABASE_SCHEMA.md` → `CONVENTIONS.md` → `TECH_STACK.md` → `ROADMAP.md`

## Stack
- **Backend**: Python 3.12, FastAPI, uv, SQLAlchemy + psycopg2-binary, watchdog, GitPython, keyring, boto3
- **AI Backend**: Ollama (free, local) — default. Amazon Bedrock (optional) — uncomment in ai/bedrock_client.py when keys are available.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS (`@tailwindcss/vite`), npm
- **DB**: CockroachDB (tables + Distributed Vector Indexing)
- **AI**: Amazon Bedrock (reasoning + embeddings)
- **OS**: Windows (primary and only target for MVP)

## Module boundaries — NEVER violate these
```
Frontend          → only calls backend/api/server.py
db/client.py      → only file allowed to touch CockroachDB
ai/bedrock_client → only file allowed to call boto3/Bedrock
automation/       → only modules allowed to call OS APIs / subprocess
decision_engine/  → must use the Agent Loop; never call DB/Bedrock directly
```

## Commands
```powershell
# Backend
cd backend
$env:Path = "C:\Users\hp\.local\bin;$env:Path"
uv sync --all-extras          # install deps
uv run python main.py         # start agent (FastAPI on :8000)
uv run pytest tests/ -v       # run tests

# Frontend
cd frontend
npm install && npm run dev    # Vite dev server on :5173
npm run build                 # type-check + build
```

## Secrets rule
- Real values: `backend/.env` only (gitignored — NEVER commit)
- Template: `backend/.env.example` (safe to commit)
- CockroachDB NEVER stores secret values — only `credential_refs` labels
- Apply `memory/capture.redact_secrets()` before any DB write or Bedrock call

## Schema rule
If you change `backend/db/schema.sql` → update `DATABASE_SCHEMA.md` in the same commit.
`VECTOR(1024)` is a placeholder — update the dimension when `EMBEDDING_DIMENSION` is decided.

## Definition of done
- Code follows module boundaries
- Docs updated in same change
- Tests written (no live DB/Bedrock in unit tests)
- Manually tested against the demo flow step (`PROJECT.md §13`)

## See also
- `.claude/rules/skills_testing.md` — testing playbook
- `.claude/rules/skills_backend.md` — backend playbook
- `.claude/rules/skills_security.md` — secrets handling
- `.claude/rules/output_naturalness.md` — how to write user-facing text
