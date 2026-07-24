# Backend Skill — AUTOMATA (SKILLS.md §4)

## When to use
When building or modifying Memory Engine (`backend/memory/`), Reasoning Engine (`backend/ai/`), or Automation Layer (`backend/automation/`).

## Checklist
- [ ] All CockroachDB writes: `backend/db/client.py` → `get_session()` only
- [ ] All Bedrock calls: `backend/ai/bedrock_client.py` only
- [ ] Long-running capture runs in daemon threads — never blocking FastAPI
- [ ] Redact secrets before any CockroachDB write: call `memory.capture.redact_secrets()`
- [ ] Idempotent writes: re-running capture must not create duplicate rows

## Phase 1 task order (TASK-005 → TASK-014)
1. DB connection (TASK-005) — confirm graceful degradation when connection string is missing
2. Schema migration (TASK-006) — run `backend/db/schema.sql` against real cluster; update VECTOR(1024) dimension first
3. Project tracking — `projects` CRUD (TASK-008)
4. Session tracking — start/end in `sessions` table (TASK-009)
5. File watcher — `FileWatcherThread` in `memory/capture.py` using `watchdog` (TASK-010)
6. Git poller — `GitPollerThread` using `GitPython` (TASK-011)
7. Terminal capture + `redact_secrets()` (TASK-012)
8. TODO extraction from code comments (TASK-013)
9. Architecture notes storage (TASK-014)

## Failure modes to avoid
- Blocking the agent on a slow Bedrock call — always have a timeout + fallback to raw memories
- Storing full file contents — store change summaries only to avoid bloating storage
