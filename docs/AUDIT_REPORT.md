# AUTOMATA — audit and status report

Date: 2026-10-26 · Branch `chore/project-review-monitoring` (last commit `36c7e05`) ·
Machine: Windows 11, 16 GB RAM, RTX 3050 4 GB · App under test: the built `app.exe`
with its supervised backend, plus the Vite UI.

## 1. Verdict

> **Update (same day): H1 and H2 are fixed.** The failed question now returns
> the `desktop.py` / `desktop.ts` edits and a correct answer. 9,108 duplicate rows
> were removed from local memory (10,680 → 1,572; backup saved as
> `%LOCALAPPDATA%\AUTOMATA\memory.backup-2026-10-26.db`). Re-activating capture
> adds no rows. Backend tests: 308 passed. Live checks: 22/22 + 23/23. Also fixed
> while verifying: file reads (Windows access-time events) were recorded as edits.

**The project is on track for its MVP goal, but not yet at "done".** Every
capability in the product brief exists and almost every check passes. Three things
stop it from meeting its own success criteria:

1. ~~**Memory answers are unreliable.**~~ *Fixed — see the update above.* The core promise ("stop reconstructing what
   changed") failed a live check. Asked "What did I change in the desktop automation
   code recently?", the app returned five identical copies of an irrelevant terminal
   line and answered "I don't have enough memory". Memory does hold the
   `desktop.py` edits. Two bugs cause this (findings H1, H2).
2. **About 10,500 lines of Phases 0–5 work are not committed.** That is 55 modified
   files (+3,938 / −1,936) and 34 new files (6,532 lines).
3. **The offline promise is unproven.** Ollama is not installed, so "works with no
   internet" has only been tested with mocks.

| Area | Status |
| --- | --- |
| Problem → product fit | ✅ Capabilities match the brief; the smart-workspace plan extends it sensibly |
| Automated tests | ✅ 293 backend + 5 frontend pass; ⚠️ 45 % backend line coverage |
| Live API checks | ✅ 45 / 45 calls behave as specified; ❌ one answer-quality failure |
| UI | ✅ All 12 screens render against the real backend |
| Security | ✅ No secrets leaked, loopback only, CORS tight; ⚠️ vulnerable GitPython, no Tauri CSP, no API auth |
| Plan phases 0–5 | Phase 0 ✅ · Phases 1–5 ⚠️ built, each with an unmet "Done when" item |

## 2. Problem statement (from the project's documents)

**Product problem** (`docs/PROJECT.md` §2): *project context is fragmented across
files, git history, terminal sessions and chat; developers repeatedly reconstruct
what changed, why it changed, and what remains to be done.*

**Intended user** (§3): one developer, one Windows machine, one or more local repos.

**Extended goal** (`docs/SMART_WORKSPACE_PLAN.md`): an AI development workspace
that:

- starts with Windows and remembers every project;
- understands each project's own stack;
- runs multi-step tasks across other apps;
- tells you what it still needs from you;
- keeps working offline on a local model.

**Final deliverables** used as the yardstick:

- the 5 success criteria in `PROJECT.md` §10;
- the 8-step manual acceptance flow in `PROJECT.md` §13;
- the "Done when" line of each plan phase (0–5).

## 3. Deliverables scorecard

### 3.1 Success criteria (`PROJECT.md` §10)

| Criterion | Status | Evidence |
| --- | --- | --- |
| Fresh setup works without machine-specific paths | ⚠️ | Docs use generic commands. The desktop app still runs the backend from the repo's `backend/.venv`, and there is no installer or PyInstaller sidecar. Not tested from a fresh clone in this audit |
| Health and setup expose missing services clearly | ✅ | Self-check gives 10 checks, each with a fix hint (Ollama missing, keyword-only search, autostart off). A bad folder gets 422 "Folder not found"; a broken stored path gets 404 "Project folder not found" |
| Memory capture, retrieval, brief, chat and restore pass tests and manual checks | ⚠️ | All automated tests pass. Capture, brief and chat pass live. **Retrieval failed live** (H1, H2). Restore was not re-run live, because it launches apps |
| OS and provider failures stay visible, never fake success | ✅ | Desktop actions verify their target. Commands come back as `suggested`, not executed. Empty search says "No memory found for that query". Delegation stops at the approval step |
| No real credentials committed, stored or sent to a model | ✅ | 8 real `.env` secret values searched across 7 AUTOMATA data and log files: 0 hits. Token patterns (`ghp_`, `AKIA`, `sk-`): 0 hits. `backend/.env` is git-ignored and no `.env` is tracked. Redaction before model calls is covered by unit tests only |

### 3.2 Manual acceptance flow (`PROJECT.md` §13)

| # | Step | Result |
| --- | --- | --- |
| 1 | Start API + UI; backend and DB status visible | ✅ Health: api ok, db connected; status shown in the UI |
| 2 | Register and select a project | ✅ Missing folders are rejected. ⚠️ "SAM MOTO FINAL" is stored with a relative path and cannot be scanned |
| 3 | Captured commits and edits found in activity and memory | ✅ Feed has 50 items; memory holds 20 commits and 1,882 file edits; search finds `desktop.py` |
| 4 | Factual question answered from captured data, with sources | ❌ Sources were 5 copies of `# Change to project folder`; answer "I don't have enough memory to answer that." |
| 5 | Brief reflects stored activity | ✅ 10 commits and real highlights; persisted |
| 6 | Restore a disposable workspace; inspect each step | ⬜ Not re-run (launches editors and servers); tests and the earlier pass cover it |
| 7 | Approval-gated action waits for approval | ✅ Task held at `handoff: waiting_approval`; command returned `executed: false` |
| 8 | Stop optional services; UI/API report degraded state | ⚠️ Missing Ollama is reported correctly. Cutting the internet and the DB was not repeated live; tests cover it |

### 3.3 Smart-workspace plan — "Done when" per phase

| Phase | Built | "Done when" met? | Gap |
| --- | --- | --- | --- |
| 0 Honest automation | ✅ | ✅ | — |
| 1 Always-on + offline memory | ✅ tray, single instance, supervisor, local SQLite memory, snapshots, router | ⚠️ | Not tested offline (Ollama not installed); no sidecar exe; vector search is keyword-only |
| 2 Project intelligence | ✅ profile, type with reasons, run book, env vars, modules | ⚠️ | Live on 1 repo only; second project's path is broken. 3+ repo types covered by tests |
| 3 Desktop control | ✅ verified focus/type/paste, UIA tabs, Windows OCR | ⚠️ | No live tab switch this audit (no browser open). DevTools-protocol tabs and RapidOCR not built |
| 4 Agent tasks + Needs | ✅ 7-step tasks, approval gates, Needs inbox, keyring | ⚠️ | Full live Antigravity run not done (stops at approval by design); Cursor not supported |
| 5 Polish | ✅ Tasks, Inbox, Setup, Alt+Space companion | ⚠️ | Mica window, stack icons in the project switcher and the "agent strip" are not built |

## 4. Test results (this audit)

| Check | Result |
| --- | --- |
| Backend `pytest tests/` | ✅ **293 passed** in 8.6 s (1 Starlette deprecation warning) |
| Backend coverage | ⚠️ **45 %** (9,468 statements). 0 % in `workflow_engine/executor.py`, `registry.py`, `checkpoint_store.py`, `context.py`, `triggers.py`, `memory/sync.py`, `memory/embeddings.py`, `decision_engine/triggers.py`, `automation/screen_capture.py`. Strong: `memory/local_store.py` 93 %, `tasks/store.py` 96 %, `intelligence/profile.py` 86 %, `tasks/engine.py` 85 % |
| Backend `ruff --select F,E9,B` | ⚠️ 2 issues, both in tests: unused variable in `test_orchestrator.py:154`, unused import in `test_reasoning_provider_order.py:8` |
| Frontend `tsc -b` / `oxlint` | ✅ clean / clean |
| Frontend `vitest` | ✅ 5 / 5 (3 files). Thin coverage for 12 screens |
| Frontend `vite build` | ✅ startup bundle 281 KB (85 KB gzip); `AnimatedChart` chunk 426 KB |
| Desktop `tauri build --no-bundle` | ✅ `app.exe` built and running; supervisor started the backend |
| Live API script (base) | ✅ 22 / 22 |
| Live API script (audit extras) | ✅ 23 / 23 calls correct; ❌ answer quality on step 4 above |
| UI click-through | ✅ Dashboard, Chat, Tasks, Inbox, Memory, Activity, Resources, Projects, Restore, Setup, Settings, Insights all render; WebSocket connects |
| Python dependency audit (`pip-audit`) | ⚠️ `gitpython 3.1.55`: 23 advisories (fixed ≥ 3.2.1); `urllib3 2.7.0`: 3 (fixed 2.8.0); `certifi 2026.7.22`: 1 |
| npm audit | ⚠️ 8 advisories (4 high), all in build/dev tools: `vite` 8.0–8.1.5, `vitest`, `undici`, `nanoid`, `postcss`, `source-map-js`. None ship in the built app |

Slow endpoints observed:

| Endpoint | Time |
| --- | --- |
| `/query` | 9.1 s (LLM) |
| brief generate | 4.4 s |
| commit-error diagnostics | 3.2 s |
| live metrics | 2.3 s |
| tools status | 2.0 s |

## 5. Findings

### High

**H1 — Terminal capture is not idempotent.** ✅ *Fixed*
- Where: `memory/capture.py`, `TerminalCaptureThread._poll`.
- Cause: `_seen_commands` lives only in memory. Every time capture starts (app
  start, project switch, activate), it re-reads the whole PowerShell history and
  writes every line again, both to local memory and to CockroachDB
  `terminal_commands`.
- Evidence: since 03:46 today, 6,679 locally written terminal rows hold only 1,215
  distinct commands. Old commands from any folder are also attributed to whichever
  project is active.
- This breaks the backend rule "re-running capture must not create duplicate rows".
- Fix: on the first poll, take the current history as a baseline and store only
  lines added after it. Add a unique key (project + content hash + day) in
  `local_store.remember` and in the cloud insert.

**H2 — Memory answers pick noise over relevant rows.** ✅ *Fixed*
- Where: `memory/local_store.py`, `search` and `fts_query`; `api/server.py`,
  `_grounded_query`.
- Cause: the question's words are ORed together. Short rows like
  `# Change to project folder` win on BM25 for the word "change". Results are not
  de-duplicated, so the model gets the same row five times and correctly says it
  has no answer.
- Duplication elsewhere: file edits are 78 % duplicates, decisions 90 %.
- Fix:
  - de-duplicate results by content;
  - weight kinds for the question (edits and commits above terminal);
  - drop very short rows;
  - prefer AND-matching before OR;
  - add a retrieval-quality test using a real question.

**What changed for H1/H2:**
- `memory/capture.py`: terminal capture saves its read position in local memory
  (`terminal_history:<file>`). It never re-imports old history, survives
  PSReadLine trimming the file, and skips shell comments.
- `memory/capture.py`: the file watcher ignores "modified" events whose content
  did not change in the last 60 s.
- `memory/local_store.py`:
  - writes are de-duplicated through a `dedup_key` column: terminal, todo,
    architecture and commit rows always; file edits and decisions once per day;
  - local and cloud copies of a commit merge by hash;
  - a one-time migration removed existing duplicates;
  - search ranks by query-term coverage, relative BM25, kind weight and recency,
    and never returns the same memory twice.
- `memory/sync.py`: commits mirrored from the cloud use the same wording as local
  capture.
- `api/server.py`: cloud results can't re-add a row already found locally.
- Tests: `tests/test_memory_quality.py` (16 tests, including the exact failed
  question) and an access-time case in `test_capture_filters.py`.
- Left as is: duplicate rows already in CockroachDB `terminal_commands`. They no
  longer reach local memory or answers.

**H3 — Uncommitted work.**
- About 10,500 lines across 89 files exist only in the working copy. Nothing since
  `36c7e05` is committed or pushed.
- The plan is to commit after user testing. Until then, a disk failure or a wrong
  `git checkout` loses Phases 0–5.

### Medium

| # | Finding | Fix |
| --- | --- | --- |
| M1 | `gitpython 3.1.55` has 23 known advisories and runs against user repos (git poller) | `uv add "gitpython>=3.2.1"`; also bump `urllib3`, `certifi` |
| M2 | Tauri `csp` is `null` (`tauri.conf.json:40`): script injected into the webview could reach Tauri APIs | Set a CSP allowing `self`, `http://127.0.0.1:8000`, `ws://127.0.0.1:8000` |
| M3 | 45 % coverage; workflow engine (has approval gates) and cloud→local sync are untested; 5 frontend tests | Add tests for `workflow_engine/executor.py`, `memory/sync.py`, and the main screens |
| M4 | Offline mode unproven: Ollama not installed; semantic search is keyword-only | Install Ollama + `qwen2.5-coder:3b` + `nomic-embed-text`, then run the "pull the network" check |
| M5 | Local API has no auth; any local process can call `/desktop/type`, `/desktop/focus` | Optional per-install token, passed by the Tauri shell |
| M6 | GPU utilisation shows "—" intermittently (NVML on the laptop GPU) | Show the last good value with its age |

### Low

| # | Finding |
| --- | --- |
| L1 | Fonts load from Google (`globals.css:8`): fails offline and leaks requests. Bundle Inter / JetBrains Mono / Outfit locally |
| L2 | Sidebar icon buttons have no accessible name (screen readers say "button"). Add `aria-label` |
| L3 | Doc drift: `PROJECT.md` §6 still calls CockroachDB *the* persistent store (now local-first SQLite); `AGENTS.md` and `PROJECT_STATUS.md` say 287 tests (now 293) |
| L4 | "SAM MOTO FINAL" is stored as `SAM_MOTO_FINAL` (relative path). Re-register with the full folder path |
| L5 | 2 ruff issues in tests; Starlette asks for `httpx2` in the test client |
| L6 | C: is 97 % full (7 GB free); the recommended local model needs ≈3.2 GB |
| L7 | Every file triggers an LF→CRLF warning. Add a `.gitattributes` |
| L8 | `.kilo/worktrees/` holds two extra git worktrees. Review before deleting |

## 6. Status summary

**Done and verified:**
- per-project memory (local SQLite plus cloud sync);
- background tray app with backend supervisor;
- per-project profile with project type and reasons;
- honest desktop control with OCR read-back;
- delegation tasks with approval gates;
- Needs inbox with Credential Manager;
- system monitoring and app-usage analytics;
- morning brief;
- self-check;
- Alt+Space companion.

**Built but not proven end to end:**
- offline AI (needs Ollama);
- a full Antigravity / Claude / ChatGPT hand-off run;
- start at sign-in after a real sign-out;
- live workspace restore in this audit.

**Not built:**
- installer and backend sidecar exe;
- workflow screen;
- Cursor support;
- browser-tab restore;
- Mica window, stack icons, agent strip;
- API auth.

**Recommended order:**
1. ~~Fix H1 and H2, with a retrieval-quality regression test.~~ Done.
2. Test the app yourself, then commit (H3).
3. Upgrade GitPython, urllib3 and certifi; set a Tauri CSP (M1, M2).
4. Install Ollama and run the offline acceptance check (M4).
5. Run one real delegation end to end.
6. Packaging: sidecar + installer.
7. Raise test coverage for the workflow engine, sync and screens.
