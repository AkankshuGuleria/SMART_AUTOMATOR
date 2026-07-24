# AUTOMATA — Start Here (All Agents)

## Project identity
AUTOMATA is an autonomous developer agent using **CockroachDB** (persistent memory + vector indexing + Managed MCP Server) and **Amazon Bedrock** (reasoning). It is a hackathon submission with a hard deadline.

## Read these docs BEFORE touching any code (in order)
1. `PROJECT.md` — what it is, why it exists, demo story
2. `ARCHITECTURE.md` — components, data flow, module map
3. `DATABASE_SCHEMA.md` — all CockroachDB tables
4. `CONVENTIONS.md` — folder structure, naming, module boundaries
5. `TECH_STACK.md` — exact versions and tooling decisions
6. `ROADMAP.md` → Current Phase — what is in scope RIGHT NOW

## Current phase
**Phase 0 - In Progress** (`TASK.md` TASK-002 is partially complete; TASK-005+ remain blocked until CockroachDB is provisioned)

## Non-negotiable rules
- Never write real credentials into any file. Use placeholder names only.
- Never write to CockroachDB from outside `backend/db/client.py`.
- Never call Bedrock from outside `backend/ai/bedrock_client.py`.
- Never execute OS actions from outside `backend/automation/`.
- Every schema change → update `DATABASE_SCHEMA.md` in the same change.
- Every architecture change → update `ARCHITECTURE.md` in the same change.
- Check `ROADMAP.md` current phase — don't build Phase 3 features during Phase 1.

## Dev commands
```powershell
# Backend
cd backend
$env:Path = "C:\Users\hp\.local\bin;$env:Path"
uv run python main.py              # start FastAPI at http://127.0.0.1:8000
uv run pytest tests/ -v            # run tests

# Frontend
cd frontend
npm run dev                        # Vite dev server at http://localhost:5173
npm run build                      # type-check + production build
```
