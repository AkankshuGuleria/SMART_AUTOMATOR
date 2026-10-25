# Project status and feature checklist

Last full review: 2026-10-26. "Verified" means an automated test asserts the
behaviour **and/or** it was exercised against the running app on the dev
laptop (Windows 11, RTX 3050). Nothing here is marked verified just because a
screen or route exists.

Legend: ✅ verified · ⚠️ works with a caveat · ⬜ not verified this pass · ❌ missing

## Health checks at the end of this pass

| Check | Result |
| --- | --- |
| Backend tests (`uv run pytest tests/`) | ✅ 215 passed, isolated from the real DB and model APIs |
| Frontend type-check (`tsc -b`) | ✅ clean |
| Frontend lint (`oxlint`) | ✅ no warnings |
| Frontend tests (`npm test`) | ✅ 3 passed |
| Frontend production build | ✅ startup bundle ~260 KB (was 918 KB) |
| Live run (backend + Vite UI) | ✅ all 8 screens load; no console errors besides restart reconnects |

## Feature checklist

### Core

| Feature | Status | Notes |
| --- | --- | --- |
| Backend starts, `/health` reports DB/provider state | ✅ | Live: DB connected |
| UI shows offline banner when backend is down | ✅ | |
| Tauri desktop shell | ⬜ | Not built or run in this pass |
| Selected project remembered across restarts | ✅ | `localStorage`, falls back to first project |

### Projects

| Feature | Status | Notes |
| --- | --- | --- |
| Register project | ✅ | Rejects missing folders (422), returns existing project for a duplicate path, reports DB failure (503) instead of a fake success |
| Project list / switcher / insights | ✅ | Insights polling reduced from 3–10 s to 15–30 s |
| Existing project **SAM MOTO FINAL** | ⚠️ | Stored path is `SAM_MOTO_FINAL` (relative), so git, restore and branch fail. Re-register it with its full folder path |

### Memory capture

| Feature | Status | Notes |
| --- | --- | --- |
| File-edit capture | ✅ | Fixed: now ignores `node_modules`, `.venv`, `.git`, `dist`, `target`, caches, lock/minified files; one row per file per 30 s |
| Commit capture, terminal capture | ✅ | Threads start live; covered by existing tests |
| Secret redaction before storage | ✅ | Tests |
| Capture follows the selected project | ⚠️ | Capture starts at backend launch for the newest registered project only; switching projects in the UI does not move it |
| Embeddings / vector search | ⚠️ | Live: Cohere returns 429 (rate limit), Groq has no embedding model, Ollama is not running. Retrieval falls back to recent memories |

### Chat and agent actions

| Feature | Status | Notes |
| --- | --- | --- |
| Intent routing + action cards + approval | ✅ | 30+ intent tests restored |
| Desktop commands without a project ("open spotify", clipboard, screen) | ✅ | Fixed: previously refused with "No project selected" |
| Agent replies rendered safely | ✅ | Fixed: HTML is escaped before formatting (was an XSS path for captured text) |
| Command palette "Ask AI" | ✅ | Fixed: was never wired to the chat screen |
| Commit message, find auth, continue work, summary, dev env | ⚠️ | Unit tests pass; not exercised live (needs a valid project path and an AI provider) |
| Reasoning providers (Groq → OpenRouter → Gemini → Cohere → NVIDIA → MiniMax → Bedrock → Ollama) | ✅ | Order test fixed; duplicate provider loop removed |

### Brief, restore, workflows

| Feature | Status | Notes |
| --- | --- | --- |
| Morning brief on the dashboard | ✅ | New card: highlights, pending items, last edited file, refresh, "Restore & continue". Falls back to plain text when no AI provider answers |
| Workspace restore | ✅ | Fixed: no longer reports "fully restored" after failures; stops before opening terminal/editor when the folder is missing; readable dev-server detail |
| Browser-tab restore | ❌ | Backend step is a placeholder |
| Workflow engine (checkpoints, approval gates) | ⚠️ | API + tests only; no UI screen |
| Cross-app control, screen capture, OCR | ⚠️ | Unit tests only; OCR depends on locally installed tooling |

### Analytics

| Feature | Status | Notes |
| --- | --- | --- |
| Activity feed | ✅ | Auto-refreshes every 30 s; clear message when no project is selected |
| Project analytics, live metrics, module readiness | ✅ | Expensive checks (Ollama probe, tool versions) now cached |
| Memory graph | ✅ | Fixed quadratic same-day edges (8 nodes: 28 → 7 edges) and filler-word keyword matches |

### New in this pass

| Feature | Status | Notes |
| --- | --- | --- |
| CPU / GPU / RAM / disk / network / battery monitor | ✅ | Live: RTX 3050 utilisation, VRAM, temperature, power; per-thread CPU; top processes grouped by name |
| Background app-usage tracking | ✅ | Live: records focused app, skips idle (2 min), local SQLite, redacted titles |
| Usage analysis (today / 7 days / 30 days) | ✅ | Time per app and category, timeline, hourly/daily charts, focus %, switches, longest session |
| Pause / resume tracking | ✅ | Resources → App usage, and Settings |
| Start at sign-in (hidden background agent) | ✅ | Toggle in Settings; tested against a temp folder. **Not switched on** on this PC — that is your choice |
| Dashboard live resource tiles + today's usage card | ✅ | Replaced hard-coded "unavailable" placeholders |

## Optimisations made

- 38 blocking API routes moved off the event loop (a 45 s AI call no longer freezes every other request).
- `/tools/status` cached 5 min (it spawned 4 processes, including PowerShell, on every 5 s poll).
- Reasoning-backend availability cached 30 s (its Ollama probe could take 2 s per poll).
- System sampler: 2 s while viewed, 15 s otherwise; process scan only on demand.
- All frontend polling goes through `usePolling` (pauses while hidden, never overlaps).
- Screens lazy-loaded; 11 unused npm packages removed (three.js, @react-three, 7 Radix packages, clsx).
- File watcher no longer floods the DB and embedding APIs during installs/builds.

## Cleanup

Removed 30 dead or duplicate files: 12 unreachable frontend screens/components
and assets, 9 root-level doc stubs (docs live in `docs/`), 4 ad-hoc root
scripts (one printed raw env values), 2 broken test-runner scripts, a duplicate
76 MB `uv.exe`, and 6 stub test files. The 22 real backend test files that had
been overwritten with a placeholder were restored from git and fixed.

## What is left

1. Re-register **SAM MOTO FINAL** with its full folder path.
2. Get embeddings working: run Ollama with `nomic-embed-text`, or use a provider key without the 429 limit.
3. Decide whether to enable **Start at sign-in** (Settings → Background agent).
4. Make capture follow the selected project without restarting the backend.
5. Build and test the Tauri desktop app; add a tray icon / close-to-background.
6. Add a workflow screen (approve/reject gates from the UI).
7. Implement browser-tab restore or remove the step.
8. Grow frontend tests (3 today) and run the manual items in `QA_CHECKLIST.md`.
9. `.kilo/worktrees/` holds two extra git worktrees (124 MB); one has 15 uncommitted changes. Review, then `git worktree remove` if unneeded.
10. Drive `C:` is 95% full (about 12 GB free).
11. The API has no authentication; keep it bound to `127.0.0.1`.
