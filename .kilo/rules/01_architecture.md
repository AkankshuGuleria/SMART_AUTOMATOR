# AUTOMATA — Architecture Rules

## Agent Loop (the core concept)
Every feature must reinforce this loop — this is what makes AUTOMATA an *agent*, not a chatbot:
```
Observe → Store Memory → Reason → Plan → Execute → Update Memory → Repeat
```

## Component map
| Component | Code location | What it owns | What it must NEVER do |
|---|---|---|---|
| Persistent Memory Engine | `backend/memory/` | DB writes, embedding gen, vector retrieval | Call Bedrock directly, execute OS actions |
| Reasoning Engine | `backend/ai/` | All Bedrock calls | Write to DB, execute OS actions |
| Automation Layer | `backend/automation/` | OS-level actions (Windows only) | Write to DB directly, call Bedrock |
| Decision Engine | `backend/decision_engine/` | Trigger detection, suggest-vs-execute routing | Bypass the Agent Loop, call Bedrock/DB directly |
| API server | `backend/api/` | FastAPI routes, WebSocket | Contain business logic, touch DB/Bedrock directly |
| Frontend | `frontend/src/` | UI rendering | Talk to CockroachDB or Bedrock directly |

## Primary OS: Windows
- All automation code uses Windows APIs via `backend/automation/os_windows.py`.
- No cross-OS code in the MVP.

## Transport: FastAPI + WebSocket over localhost
- Frontend calls Python backend at `http://127.0.0.1:8000`.
- Live updates over `ws://127.0.0.1:8000/ws`.

## Memory types
- **Short-term**: RAM only — never persisted past process restart.
- **Long-term**: CockroachDB structured rows.
- **Semantic**: CockroachDB Vector Index (embeddings on `*_embedding` columns).

## Decision Engine guardrails
- `auto_execute`: passive, reversible actions (update summary, flag TODO, generate brief).
- `suggest`: environment-changing actions (restore workspace, launch editor) — NEVER auto-execute these.
- Every autonomous action is logged to `decision_log` with provenance.
