# AUTOMATA — Backend Skill (SKILLS.md §4)

**Apply when building or modifying Memory Engine, Reasoning Engine, or Automation Layer.**

## Checklist
- [ ] Respect module boundaries (`CONVENTIONS.md §3`) — no exceptions
- [ ] All CockroachDB writes through `backend/db/client.py` → `get_session()`
- [ ] All Bedrock calls through `backend/ai/bedrock_client.py`
- [ ] Long-running capture (file watcher, git hooks) runs in background daemon threads — never blocking the API server
- [ ] Redact secrets from terminal commands and file diffs **before** writing to CockroachDB (use `memory/capture.redact_secrets()`)
- [ ] Idempotent writes — re-running capture must not create duplicate rows (use UNIQUE constraints)

## Phase 1 tasks (TASK-005 to TASK-014)
Implement in this order:
1. `db/client.py` → connect CockroachDB (TASK-005)
2. `db/schema.sql` → run against real cluster (TASK-006) — update VECTOR(1024) dimension first
3. Project tracking — `projects` table CRUD (TASK-008)
4. Session tracking — start/end sessions (TASK-009)
5. File watcher → `FileWatcherThread` in `memory/capture.py` (TASK-010)
6. Git poller → `GitPollerThread` (TASK-011)
7. Terminal capture with `redact_secrets()` (TASK-012)
8. TODO extraction from code comments (TASK-013)
9. Architecture notes storage (TASK-014)

## Common failure modes to AVOID
- Blocking the agent process on a slow Bedrock call — always have a timeout and fallback
- Storing full file contents — store change summaries only
- Ad-hoc `create_engine()` calls scattered across modules
