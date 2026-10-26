# Backend skill — AUTOMATA

## When to use
Any change under `backend/` (agent, memory, reasoning, automation, tasks, assist, security).
Start with `docs/AGENTS.md` (repo map and rules) and `docs/ARCHITECTURE.md`.

## Checklist
- [ ] Model calls only through `backend/ai/bedrock_client.py` (timeouts + offline fallback)
- [ ] Cloud DB only via `backend/db/client.py`; local memory only via `backend/memory/local_store.py`
- [ ] Desktop effects only via `automation/desktop.py` / `automation/chat_apps.py`, verified after acting
- [ ] Anything that controls the PC goes through `security/permissions.check()` (or a chat approval card)
- [ ] Captured text passes `memory.capture.redact_secrets()` before it is stored or sent to a model
- [ ] Writes are idempotent (re-running capture or sync adds no duplicate rows)
- [ ] Long-running work runs in daemon threads, never blocking FastAPI handlers
- [ ] New/changed endpoint → `docs/API_REFERENCE.md`; new table/store → `docs/DATABASE_SCHEMA.md`

## Failure modes to avoid
- Reporting success because a command ran — confirm the effect
- Storing file contents (store change summaries only)
- Blocking on a slow model call — always time-box and fall back to raw memories
