# AUTOMATA — architecture rules

Full picture: `docs/ARCHITECTURE.md`.

| Area | Location | Owns | Must never |
| --- | --- | --- | --- |
| API | `backend/api/` | FastAPI routes, WebSocket | Hold business logic |
| Security | `backend/security/` | Permissions, local-only API guard, Defender notes | Change Windows security settings |
| Reasoning | `backend/ai/` | All model calls, offline routing, Ollama | Write to a DB, act on the PC |
| Memory | `backend/memory/` | Local SQLite memory, capture, cloud sync | Store secrets or file contents |
| Desktop control | `backend/automation/` | Verified focus/type/paste/OCR, AI-app hand-off | Act without verifying the result |
| Tasks | `backend/tasks/` | Delegation steps, questions, Needs inbox | Skip an approval gate |
| Quick assist | `backend/assist/` | Work bar commands (media, search, screen) | Run before permission |
| Project intelligence | `backend/intelligence/` | Stack, run book, env vars, modules | Read env var values |
| Frontend | `frontend/src/` | UI only, all HTTP in `lib/api.ts` | Render untrusted text as HTML |
| Desktop shell | `frontend/src-tauri/` | Tray, supervisor, work-bar shortcut | Bypass the agent API |

- Windows is the target platform; other platforms must fail with a clear message.
- The agent binds to `127.0.0.1:8000`; the UI talks HTTP + `ws://127.0.0.1:8000/ws`.
- Local memory (SQLite FTS5) works offline; CockroachDB is an optional cloud copy.
- Planner policies: `auto_execute` only for passive, reversible actions; PC
  control is `confirm_once` unless the user always-allowed that category.
