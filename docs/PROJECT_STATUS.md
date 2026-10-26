# Project status and feature checklist

Last full verification: **2026-10-26** on the dev laptop (Windows 11, 16 GB RAM,
RTX 3050 4 GB). "Verified" means an automated test asserts it **and/or** it was
exercised against the running app. Nothing is marked verified because a screen
or route exists.

Legend: ✅ verified · ⚠️ works with a caveat · ⬜ not verified · ❌ missing

## Health at the end of this pass

| Check | Result |
| --- | --- |
| Backend tests `uv run pytest tests/` | ✅ 350 passed (isolated from real DB, providers, keyboard, screen) |
| Frontend `tsc -b` / `oxlint` / `npm test` | ✅ clean / clean / 5 passed |
| Frontend production build | ✅ startup bundle ≈260 KB; screens lazy-loaded |
| Desktop app `npx tauri build --no-bundle` | ✅ `app.exe` built (10.8 MB) |
| Live API end-to-end script (22 checks) | ✅ 22/22 |
| Live UI: Dashboard, Tasks, Inbox, Setup, Resources, Companion | ✅ rendered against the real backend |
| Live desktop app: tray, close-to-tray, single instance, `--hidden`, backend supervisor | ✅ |

## Feature checklist

### Always-on workspace (Phase 1)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Tray app; closing the window hides to tray | ✅ | Live: process kept running after close |
| Single instance | ✅ | Live: second launch exited |
| Start at sign-in (app, hidden) | ✅ | Settings toggle via tauri-plugin-autostart; `--hidden` start verified. Off until the user turns it on |
| Backend supervisor (start/restart agent) | ✅ | Live: app started `pythonw main.py` when port 8000 was free; logs to `%LOCALAPPDATA%\AUTOMATA\agent.log` |
| Native notifications (task needs approval, new needs) | ⚠️ | Wired; not observed on screen in this pass |
| AI work bar (Alt+Space / Ctrl+Alt+A) | ✅ | Live in the built app: opens top-centre with focus, second press hides, hides on click-away. It was broken before (toggled on key-down and key-up) |
| No console windows popping up | ✅ | Every child process gets CREATE_NO_WINDOW (`automation/no_console.py`); live: no console windows while self-check / agent status / media endpoints ran |
| Self-check screen with fix hints | ✅ | Live: 10 checks |

### Memory continuity (Phase 1)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Local offline memory (SQLite FTS5) | ✅ | Tests + live: 1 100+ memories mirrored |
| Cloud → local sync (idempotent) | ✅ | Live: commits/decisions/edits/terminal mirrored |
| Projects work without CockroachDB | ✅ | Test: register/list/get fall back to local store |
| Chat answers grounded in local memory | ✅ | Test + live companion answer. Ranking by term coverage, kind weight and recency; results de-duplicated (`tests/test_memory_quality.py`) |
| Duplicate-free capture | ✅ | Terminal capture resumes from its saved history position; writes de-duplicated by content; reads (access-time events) no longer count as edits. Live: 9,108 duplicate rows removed, re-activation adds none |
| Chat turns and briefs remembered | ✅ | Tests |
| Session snapshot (every 10 min, on idle, on shutdown, manual) | ✅ | Live: branch, 30 changed files, 10 recent files, dev servers 5173/8000, current task |
| Resume workspace (editor + recent files, terminal, dev servers) | ✅ | Tests (launches mocked); skips servers already running |
| Capture follows the selected project | ✅ | Live: activate → 3 capture threads on D:\AUTOMATA |
| Terminal capture for any project | ✅ | Fixed: old check used the backend's own folder |
| Semantic (vector) search offline | ⚠️ | Needs Ollama `nomic-embed-text` or the `local-ai` extra; keyword search always works |

### Local AI / offline (Phase 1)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Offline detection → skip cloud, use Ollama | ✅ | Test |
| "Which model answered" | ✅ | Live: Setup shows "last answer: OpenRouter" |
| Model recommendation for this PC | ✅ | Live: qwen2.5-coder:3b for 4 GB VRAM |
| Install Ollama / download model with progress / select model | ⚠️ | UI + API tested with mocks; **Ollama is not installed** on this PC yet |
| `OLLAMA_*` settings respected | ✅ | Fixed: were hard-coded |
| Fast Ollama probe | ✅ | Fixed: each check cost 2–4 s when Ollama is off (Windows refused-connect delay); now ≤150 ms |

### Project intelligence (Phase 2)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Stack, package managers, DBs, infra, ports | ✅ | Tests (Next.js+Prisma, Django, empty) + live on this repo |
| Run book (install/dev/build/test) | ✅ | Used by restore, resume and task verification |
| Env requirements (names only, set/missing, example defaults) | ✅ | Tests confirm values never leave files |
| Modules from the project's own structure + explained score | ✅ | Replaced the fixed AUTOMATA module list everywhere |
| Profile injected into chat and agent prompts | ✅ | Live: task prompt contains the stack |

### Desktop control (Phases 0 + 3)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Focus app (verified by Windows) | ✅ | Live probe + tests; multi-process apps handled |
| Keys / paste only into a verified target; never into AUTOMATA | ✅ | Live probe + tests; kill-switch in tests |
| Type text with read-back (UIA, then OCR) | ✅ | Tests |
| Browser tabs: list / switch (UI Automation) | ✅ | Live: listed Edge tabs; switch verified in tests |
| List open windows ("what windows are open") | ✅ | Live |
| OCR (Windows engine) + DPI-correct capture | ✅ | Live: exact text; 1920×1080 capture |
| Prompt handoff: confirms paste before Enter, restores clipboard | ✅ | Live probe + tests |

### Agent tasks & Needs inbox (Phase 4)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| "using antigravity …" → task with 8 steps | ✅ | Live via chat |
| Clarifying questions (folder / save location, stack, features, design, extra) | ✅ | Tests + live: form in Tasks; folder created after answering; answers in the prompt |
| Approval gates (hand-off, build) | ✅ | Live: stopped at hand-off; tests cover the full flow |
| Antigravity IDE: open folder → Agent panel → paste into "Message input" → read back | ✅ | Live on a scratch folder: launched the IDE, pressed Ctrl+L when the panel was closed, text confirmed via UIA, a draft is never overwritten |
| Antigravity: full delegation end to end | ✅ | Live 2026-10-26: questions → folder created → prompt sent (box emptied, 4 s) → agent created `hello.html` in 14 s → watch saw 1 file → report. Antigravity then shows the change for you to Accept/Reject |
| Unicode-safe clipboard | ✅ | Native Win32 clipboard (no PowerShell): the first live run stopped because an em dash came back garbled through PowerShell's code page; now exact for any text, 9 ms |
| VS Code via `code chat --mode agent` | ⚠️ | Its chat box is a generic editor field, so delivery is reported as unconfirmed |
| Claude | ⚠️ | Claude app via the chat-box adapter (not probed live: this session runs inside it); Claude Code CLI not installed |
| ChatGPT (browser) | ⚠️ | Verified handoff logic; not run live |
| Cursor | ⚠️ | Chat-box adapter (Ctrl+L) when `cursor-agent` is missing; not probed live |
| Watch for file changes, run build/tests, report | ✅ | Tests with a fake agent editing a temp repo |
| Needs inbox with instructions per provider | ✅ | Live + tests; stale items close automatically |
| Save values to Credential Manager and/or `.env` (git-ignore check) | ✅ | Tests (keyring mocked) |
| Tasks survive restart (paused, resumable) | ✅ | Test |

### Work bar, media and screen (2026-10-26)

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Play / pause / next / previous / volume (system media keys) | ✅ | Live: each step confirmed through the Windows media session |
| "play <x> on spotify" | ✅ | Live: search → top result's Play via UIA → player confirmed playing (3.5 s) |
| What's playing | ✅ | Live (0.4 s) |
| Web search (google, youtube, github, …) | ✅ | Tests (URL); opens the default browser |
| Read / explain my screen (only on request) | ✅ | Live: explained a NameError shown in Notepad; image deleted after OCR |
| Main window recovers when it opens before the agent | ✅ | Health polls every 3 s while offline; screens reload once it is online |

### Earlier features (re-checked)

| Feature | Status | Notes |
| --- | --- | --- |
| System resources (CPU/GPU/RAM/disk/network/processes) | ✅ | GPU utilisation retries (laptop GPU answers ~every 2.5 s) |
| App-usage tracking + analysis | ✅ | |
| Morning brief (works offline from local memory) | ✅ | |
| Workspace restore (honest, run-book commands, no duplicate servers) | ✅ | |
| Chat intents, approvals, workflows API | ✅ | Workflows have no dedicated screen |
| Memory graph, analytics, activity feed | ✅ | |

## What is left / known limits

1. **Install Ollama** (Setup → Local AI) and download `qwen2.5-coder:3b` + `nomic-embed-text` for full offline AI and semantic search. C: has ~7 GB free; set `OLLAMA_MODELS` to a folder on D: if space runs low.
2. **Try a real delegation**: "using antigravity …" → approve the hand-off. The CLI path is verified; the end-to-end agent run is yours to watch.
3. **Turn on Start at sign-in** in Settings (inside the desktop app) if you want it always running.
4. Re-register **SAM MOTO FINAL** with its full folder path (stored as `SAM_MOTO_FINAL`).
5. No installer yet (`tauri build` with bundling needs WiX/NSIS); the backend still runs from the repo's `backend/.venv` (no PyInstaller sidecar yet).
6. Workflow engine has no UI; Cursor needs `cursor-agent`; browser-tab restore on resume is not implemented.
7. API has no authentication — keep it bound to 127.0.0.1.
8. `.kilo/worktrees/` holds two extra git worktrees (one with uncommitted changes) — review before deleting.
9. C: drive is ~97 % full.
