# SMART_AUTOMATOR — smart workspace update plan

> **Status (2026-10-26): Phases 0–5 implemented and verified** — see
> `PROJECT_STATUS.md` for evidence and remaining limits. Deviations from the
> plan: the backend is supervised by the Tauri app from the repo's venv (no
> PyInstaller sidecar yet); local memory uses SQLite FTS5 + optional vectors
> stored in SQLite (no sqlite-vec); pywinauto was replaced by a small
> comtypes UI Automation helper; Antigravity/VS Code receive prompts through
> their `chat --mode agent` CLI instead of UI automation.

Written 2026-10-26 after live-testing every documented feature on the dev
laptop (Windows 11, 16 GB RAM, RTX 3050 4 GB, 8 GB free on C:).

**Goal:** turn AUTOMATA from "a dashboard with an AI chat" into an AI
development workspace that starts with Windows, remembers every project,
understands each project's own stack, runs multi-step tasks across other apps
(Claude, Antigravity, Cursor, VS Code, browser), tells you exactly what it
still needs from you, and keeps working offline on a local model.

---

## 1. What the live tests showed

| Documented feature | Result | Evidence |
| --- | --- | --- |
| Memory capture (files, commits, terminal) | ✅ works | Threads start; watcher now ignores build folders |
| Memory search (vector) | ⚠️ degraded | Every embedding provider fails (Cohere 429, Groq has no embedding model, Ollama not installed). Falls back to "recent rows" |
| Memory when offline | ❌ none | All memory lives in cloud CockroachDB |
| Morning brief / restore / analytics | ✅ works | Fixed in the review pass |
| **OCR** | ❌ broken | Returned the literal string `ocr_unavailable` as if it were the screen text. Tesseract not installed; the PowerShell fallback calls the Windows OCR API in a way PowerShell 5.1 can't run, and overwrites the user's clipboard with the image |
| Screen capture | ⚠️ wrong | Captures 1536×864 of a 1920×1080 screen (125 % display scaling ignored). Region capture references undefined PowerShell variables; two captures in the same second overwrite each other |
| Clipboard copy / read | ✅ works | Round-trip verified (≈200 ms each, one PowerShell process per call) |
| **Focus app / switch window** | ❌ fake success | Returned "activated" but Windows blocked the focus change; the paste went to the desktop instead of the target window. Fails outright for multi-process apps (Chrome, VS Code) |
| Paste / keystrokes | ❌ fake success | Keys go to whatever window is in front. Only 8 fixed keys allowed; cannot type text |
| Browser tab switching | ❌ missing | No implementation (`ctrl+tab` rejected; no tab model) |
| Prompt another app (`submit_prompt_to_app`) | ❌ unsafe | Copies, "focuses", pastes and presses Ctrl+Enter blind — can submit a prompt into the wrong app, and still reports success |
| External agents (Claude / Cursor / Antigravity) | ❌ wrong detection | Claude CLI not installed (desktop app only). Antigravity is installed but not on PATH → "not connected". Cursor reported "connected" because VS Code exists, then calls a `--cli --prompt` flag that does not exist |
| `verify_result` | ❌ fake success | Unknown check types return `verified: true` |
| Project analysis | ❌ generic | "Module readiness" is AUTOMATA's own 7 modules (Memory Engine, Vector Search, Reasoning Engine…) shown for **every** project. No tech-stack detection exists |
| Background running | ⚠️ partial | New "Start at sign-in" launches the backend hidden; the desktop app itself has no tray, autostart or single-instance |
| Local model support | ⚠️ partial | Code supports Ollama, but Ollama is not installed and the app never tells you that it is offline-blind |

**Root causes**

1. **Blind automation.** Every OS action is "send a command, assume it worked".
   Nothing checks the result.
2. **Cloud-only memory.** No local store, so no internet = no memory and no search.
3. **No project model.** The app never works out what a project *is*
   (stack, services, env vars, tests), so every screen shows the same things.
4. **No task model.** Chat produces one-shot actions. There is no long-running
   task that can plan, hand work to another app, wait, check, and ask you for
   what's missing.

---

## 2. Missing features (the new list)

### A. Always-on workspace
- A1. Single desktop app that starts at sign-in, lives in the **system tray**, closes to tray, and allows one instance only.
- A2. Backend bundled inside the app (sidecar `automata-agent.exe`), so there is nothing to start by hand.
- A3. Global hotkey (Alt+Space already exists) → quick-command bar over any app.
- A4. Native notifications: "Brief ready", "Task needs your input", "Tests failing in X".
- A5. Self-check on launch: DB, local model, internet, OCR, permissions — with one-click fixes.

### B. Memory continuity ("pick up where I left off")
- B1. **Local-first memory**: SQLite + full-text search + vector index on disk; CockroachDB becomes optional sync/backup.
- B2. **Offline embeddings in-process** (small ONNX model) — no Ollama or API key needed for search.
- B3. **Session snapshot** on idle/shutdown: branch, open files, terminal folders, running dev servers, open TODOs, last chat, current task.
- B4. **Resume on login**: brief + "Continue" restores the snapshot (editor, terminal, servers, browser tabs).
- B5. Capture follows the **active project** and watches several projects at once.
- B6. Decisions, chat history and agent-task outcomes stored as memory, not lost when the window closes.

### C. Project intelligence (dynamic per project)
- C1. **Project profile detector**: languages, frameworks (Next.js, Django, FastAPI, Spring…), package managers, test runners, databases, Docker/compose, CI, deploy targets.
- C2. **Requirements scan**: env vars from `.env.example`/config/code, required services (Postgres, Redis…), missing API keys, ports.
- C3. **Dynamic modules**: dashboard health cards generated from the project's real structure (e.g. *Frontend · API · Database · Auth · Tests* for a Next.js + Prisma app), each scored from real signals (tests in that area, recent failures, TODO density, churn).
- C4. Per-project run book: how to install, run, test, build — detected, then confirmed by actually running it.
- C5. Project-aware prompts: everything sent to a model or another app includes the profile + relevant memory.

### D. Reliable desktop control
- D1. Replace PowerShell `AppActivate`/`SendKeys` with **UI Automation** (pywinauto) + a proper Win32 foreground switch, and **verify after every action** (is the right window in front? did the text land?).
- D2. Type text, select menus, click named buttons, read fields — via UI elements, not blind keys.
- D3. Window and **browser tab** control: list windows/tabs, switch to a tab by title or URL, open/close tabs (Chrome/Edge via DevTools protocol where enabled, UI Automation otherwise).
- D4. **Working OCR**: Windows built-in OCR engine called in-process (≈100 ms), DPI-correct capture of screen / window / region, optional higher-accuracy local OCR model.
- D5. Per-app adapters with known-good recipes: Claude desktop, ChatGPT web, Antigravity, Cursor, VS Code, Chrome, Windows Terminal.
- D6. Clipboard that saves and restores what you had copied.

### E. Agent tasks and app orchestration
- E1. **Task engine**: "Using Antigravity, build a landing page for X" becomes a visible task with steps: gather context → write prompt → open app → hand off → watch progress → check result → report.
- E2. **Handoff paths ranked by reliability**: CLI/API first (Claude Code CLI, Antigravity/VS Code `chat` CLI, Cursor agent CLI), UI automation second, copy-to-clipboard + instructions last.
- E3. **Prompt builder** that packs project profile, relevant memory, constraints and acceptance criteria.
- E4. **"Needs from you" inbox**: API keys, DB connection strings, account sign-ups, design choices — each with step-by-step instructions. Secrets go straight to Windows Credential Manager; only a label is stored.
- E5. Result verification: files changed, build passes, tests pass, server responds, screenshot + OCR check.
- E6. Approval policy per step (auto / confirm / require approval), pause/resume/cancel, full step log.

### F. Local AI and offline mode
- F1. **Model router**: picks local vs cloud per task (offline → local always), with timeouts and visible "which model answered".
- F2. Guided Ollama setup sized for this machine (see §4) with download progress and disk check.
- F3. Offline indicator; queue cloud-only work until back online.

### G. Look and feel
- G1. Windows 11 Mica/acrylic window, tray menu, compact "agent strip" over other apps.
- G2. **Task board** with live step progress; **Inbox** for things it needs from you.
- G3. Project switcher showing each project's stack icons and health.
- G4. Command bar first: every feature reachable by typing.

---

## 3. Stack decisions

| Layer | Choice | Why |
| --- | --- | --- |
| Desktop shell | **Tauri 2** (keep) + plugins: `autostart`, `single-instance`, `notification`, tray, `global-shortcut` (have), window effects (Mica) | Already in the repo; small, fast, native Windows features |
| Backend packaging | FastAPI agent built with **PyInstaller** into `automata-agent.exe`, launched by Tauri as a **sidecar** | One app to install and start; backend restarts if it crashes |
| Local memory | **SQLite** (FTS5) + **sqlite-vec** in `%LOCALAPPDATA%\AUTOMATA\memory.db` | Zero-setup, offline, fast; same machine as the agent |
| Cloud memory | CockroachDB as **optional sync** target | Keeps current data; no longer a single point of failure |
| Embeddings | **fastembed** (ONNX) `bge-small-en-v1.5`, 384-dim, ~130 MB, CPU | Works with no internet, no Ollama, no key |
| Local LLM | **Ollama** — `qwen2.5-coder:3b` default (fits 4 GB VRAM), `qwen2.5-coder:7b` optional (4.7 GB, partial offload) | Best small coding models for this GPU; disk is tight, so 3b first |
| Cloud LLM | Existing router (Groq → OpenRouter → Gemini …) | Keep; add per-task routing and health |
| Desktop control | **pywinauto** (UI Automation) + ctypes Win32; **comtypes** | Verifiable actions instead of blind keystrokes |
| OCR | **winrt** projection of `Windows.Media.Ocr` (built-in, English installed) + optional **RapidOCR** (ONNX) | Already on the machine; in-process; no Tesseract install |
| Screen capture | **mss** with per-monitor DPI awareness | Correct resolution, fast |
| Browser tabs | Chrome/Edge **DevTools protocol** (opt-in) → UI Automation fallback | Exact tab list/switch; fallback when debugging port is off |
| External agents | Claude Code CLI (`claude -p`), Antigravity/VS Code `chat` CLI, Cursor agent CLI; UI adapters as fallback | CLI is scriptable and verifiable |
| Secrets | **keyring** → Windows Credential Manager (already a dependency) | Secrets never in DB, logs or prompts |
| Task engine | Extend existing `workflow_engine` (checkpoints, gates) | Already has persistence + approvals |
| Frontend | React 19 + Vite + Framer Motion (keep), lazy screens (done) | No rewrite needed |

---

## 4. Machine notes (this laptop)

- **Disk is the blocker**: 8 GB free on C:. fastembed (~0.2 GB) + Ollama + `qwen2.5-coder:3b` (~1.9 GB) fits; the 7b model (4.7 GB) does not leave safe headroom. Free space first or put Ollama models on another drive (`OLLAMA_MODELS`).
- GPU: RTX 3050 4 GB — 3b models run fully on GPU; 7b runs split CPU/GPU (slower).
- Windows OCR languages installed: en-US, en-GB.
- Installed agents: Antigravity, Antigravity IDE (`antigravity-ide.cmd`), Cursor, VS Code, Claude desktop. Not installed: Claude Code CLI, Ollama, Tesseract.

---

## 5. Phased plan

Each phase ships something usable and ends with its own acceptance checks.
Estimates are focused-work days for one developer.

### Phase 0 — Make automation honest (1–2 days) · ✅ done 2026-10-26

Shipped: `automation/desktop.py` (single verified implementation used by the planner, tools,
agent actions and the bridge), `automation/win32.py` (in-process Win32 focus, keys and
DPI-correct PNG capture), `automation/windows_ocr.ps1` (working Windows OCR). Tests can never
send real input (`AUTOMATA_DISABLE_DESKTOP_INPUT=1`). Live probe passed: verified focus, paste
and submit into a throwaway window, OCR read-back, wrong-target refusal, clipboard restored.
Stop the fake successes found in §1 before building on top of them.
- Verify-after-act for focus/paste/keystroke: check the foreground window; fail loudly if it isn't the target.
- `submit_prompt_to_app` never presses Enter/Ctrl+Enter unless the target window is verified in front.
- OCR returns an error (not text) when no engine is available; stop overwriting the clipboard.
- `verify_result` returns `verified: false` for unknown checks; fix Cursor/Antigravity detection.
- DPI-aware capture, unique screenshot names, working region capture.

**Done when:** the cross-app probe (throwaway window) passes end-to-end, and every failure is reported as a failure.

### Phase 1 — Always-on app + offline memory (5–7 days)
- Tauri tray, close-to-tray, single instance, autostart plugin, notifications.
- Backend sidecar (PyInstaller) supervised by Tauri.
- Local SQLite memory + sqlite-vec + fastembed; migrate/sync from CockroachDB.
- Model router with offline detection; guided Ollama setup (3b model).
- Session snapshot + resume on login; capture follows active project.

**Done when:** pull the network cable → app still starts at login, shows yesterday's brief, answers memory questions with the local model, and "Continue" reopens the workspace.

### Phase 2 — Project intelligence (4–5 days)
- Profile detector (stack, services, tests, env vars, ports) with confidence + evidence.
- Dynamic module cards and health scores per project; run book detection.
- Profile + memory injected into every prompt.

**Done when:** three different repos (e.g. this one, a Next.js app, a plain Python script) each show their own modules, required env vars and run commands — no AUTOMATA-specific labels.

### Phase 3 — Reliable desktop control (5–7 days)
- pywinauto/UIA engine, window + browser tab control, text entry, element clicks.
- In-process Windows OCR + window/region capture; optional RapidOCR.
- App adapters: Claude desktop, Antigravity, Cursor, VS Code, Chrome/Edge, Terminal.
- Clipboard save/restore.

**Done when:** scripted tests switch to a named Chrome tab, type into Claude desktop, read the reply back via UIA/OCR, and restore the clipboard — each step verified.

### Phase 4 — Agent tasks + "Needs from you" (6–8 days)
- Task engine on top of `workflow_engine` with live step view.
- Prompt builder; handoff via CLI first, UI adapter second.
- Requirement extraction → Inbox with instructions; secrets to Credential Manager.
- Verification step (build/tests/server/screenshot).

**Done when:** "Using Antigravity, create a landing page for this project" opens Antigravity in the project, sends a context-rich prompt, watches until files change, runs the build, and leaves an Inbox item like "Add `STRIPE_SECRET_KEY` — here's where to get it".

### Phase 5 — Polish (3–4 days)
- Mica window, task board, inbox, project switcher with stack icons, agent strip.
- Self-check screen with one-click fixes; onboarding.

---

## 6. Order of work and what I need from you

1. Phase 0 now — small, removes real risk (blind Ctrl+Enter into the wrong app).
2. Free disk space on C: (or choose a drive for models) before Phase 1.
3. Decide: keep CockroachDB as sync, or go local-only?
4. Install Claude Code CLI if you want Claude as a scriptable handoff target (`npm i -g @anthropic-ai/claude-code`).
5. For browser-tab control, allow starting Chrome/Edge with remote debugging (opt-in), or accept UI-Automation-only tab switching.
