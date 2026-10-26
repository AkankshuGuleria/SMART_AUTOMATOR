# AUTOMATA — start here (all agents)

AUTOMATA is a local-first **AI development workspace for Windows**: a Tauri tray
app supervising a Python agent that remembers each project, understands its
stack, hands tasks to AI apps (Antigravity, Kilo Code, Claude, Cursor, VS Code)
with approval gates, and asks before it controls the PC.

**Read `docs/AGENTS.md` first** — repository map, run/test commands, rules and
where to start for common changes. Feature status: `docs/PROJECT_STATUS.md`.

## Non-negotiable rules

- Never write real credentials anywhere. Secrets live in `backend/.env`
  (git-ignored) or Windows Credential Manager.
- Module boundaries: model calls only in `backend/ai/bedrock_client.py`; cloud DB
  only via `backend/db/client.py`; local memory only via
  `backend/memory/local_store.py`; desktop effects only via
  `backend/automation/desktop.py` / `chat_apps.py`.
- Anything that controls the PC goes through `security/permissions.check()`
  (or a chat approval card). Never trust a caller-supplied "approved" flag.
- Never report an action as done without verifying it (window in front, text
  read back, file exists).
- Every endpoint / schema / architecture change updates its doc in the same change.

## Commands

```powershell
.\scripts\dev.ps1                      # agent + browser UI   (-Desktop for the app)
cd backend;  uv run pytest tests/ -q   # must stay green
cd frontend; npx tsc -b; npx oxlint src; npm test
```
