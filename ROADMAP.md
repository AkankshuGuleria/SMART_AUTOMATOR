# ROADMAP.md — 20-Day Build Plan

## Current Phase
> **Update this line as you progress:** `Phase 5 - Chat-first UI redesign: Complete. All screens polished and verified.`

---

## Phase 0 (Day 0): Setup & decisions
- [x] Pick primary OS for Automation Layer → **Windows** (`ARCHITECTURE.md` §6 — filled in).
- [x] Pin exact versions in `TECH_STACK.md` (decided items filled; Bedrock/embedding model TBD pending AWS provisioning).
- [x] Provision CockroachDB instance (local or cloud).
- [ ] Provision AWS Bedrock access + confirm model access in target region.
- [x] MCP model decided: AUTOMATA consumes CockroachDB's Managed MCP
      Server (`ARCHITECTURE.md` §7) — no further decision needed here.
- [x] Scaffold repo per `CONVENTIONS.md` §1, including `decision_engine/`.
- [ ] Finish Tauri desktop shell (`frontend/src-tauri/` is not present yet).

## Phase 1 (Days 1–5): Memory capture
- [x] Implement `projects`, `sessions`, `commits`, `file_edits`,
      `terminal_commands`, `todos` tables (`DATABASE_SCHEMA.md`).
- [x] File watcher capturing edits → `file_edits` (`memory/capture.py` — `FileWatcherThread`).
- [x] Git hook / polling capturing commits → `commits` (`memory/capture.py` — `GitPollerThread`).
- [x] Terminal command capture → `terminal_commands` (`memory/capture.py` — `TerminalCaptureThread`).
- [x] Manual + code-comment TODO capture → `todos` (DB CRUD in `db/client.py`).
- [x] Basic session start/end tracking (`db/client.py` — `insert_session`, `end_session`).
- [x] `credential_refs` table + OS-native vault integration (never store
      real secrets in CockroachDB) — see `SKILLS.md` §8.
- [x] Secret redaction pass applied to all capture paths before writes.
- [x] Secret redaction utility implemented and covered by unit tests.
- [x] DB client (`db/client.py`) — full CRUD for all tables.
- [x] API routes for projects (`/projects` GET/POST) — Phase 1 implemented.
- [x] Automation Layer — real Windows OS calls (`os_windows.py`).
- [x] Workspace restore (`restore.py`) — real implementation.
- [x] Dev server management (`dev_servers.py`) — real implementation.
- [x] Decision Engine triggers (`triggers.py`) — `on_commit` and `on_session_end` wired.
- [x] Decision Engine planner (`planner.py`) — action classification and routing.
- [x] Background watcher threads wired in `main.py`.
- **Milestone check:** can you query CockroachDB directly and see real
  captured activity from a real coding session?

## Phase 2 (Days 6–10): Retrieval & reasoning
- [x] Embedding generation pipeline wired to all `*_embedding` columns.
- [x] Vector search query layer (`retrieval.py`).
- [x] Bedrock client + grounded-answer prompt (`SKILLS.md` `§5`).
- [x] "What was I working on yesterday?" working end-to-end from a real
      question to a real grounded answer.
- [x] `daily_briefs` generation job/endpoint.
- [x] `taste_preferences` inference pipeline: derive naming/style/library
      signals from the developer's own commit history — see
      `SKILLS.md` `§7`.
- [x] `decision_log` and `mistake_log` tables wired up and populated as
      real decisions/bugs happen during the build itself (dogfood the
      product on its own development).
- **Milestone check:** ask 5 differently-phrased questions about the same
  underlying activity and confirm retrieval + answers stay correct.

## Phase 3 (Days 11–14): Autonomous Workspace Recovery
- [x] Automation Layer interface + stub implementation for tests.
- [x] Real implementation for chosen primary OS: git branch checkout,
      terminal restore, dev server start/stop.
- [ ] Stretch: editor auto-launch, browser auto-launch.
- [x] Frontend "Restore workspace?" flow with step-by-step progress UI.
- [ ] Record the first full backup demo video as soon as this milestone
      works once, even roughly.
- **Milestone check:** one-click restore works reliably 5 times in a row
  on the actual demo machine.

## Phase 4 (Days 15–17): Agent Actions
- [x] "Generate commit message" (grounded in actual diff/staged changes).
- [x] "Explain repository" (grounded in README + architecture notes +
      folder structure).
- [x] "Find authentication code" (or equivalent semantic code-location
      query) — grounded in file/commit memory, not live code search,
      unless code search is explicitly added as a supplementary source.
- [x] "Start development environment" command wired to Automation Layer.
- [x] Global Floating Companion Overlay (Tauri global shortcut `Alt+Space` to overlay over VSCode, Browser, Terminal, etc.).
- [x] Cross-App Task Execution Engine (asynchronous background execution for building web apps, executing OS actions, and driving tools across other applications).

- **Milestone check:** each command works from a natural-language phrasing
  a judge might actually use, not just the exact scripted phrase.

## Phase 4.5 (Days 18–19): Autonomous Decision Engine
> This is genuinely new scope, not a renaming exercise — budget real time
> for it and treat it as cuttable if Phases 1–4 ran long. A working
> Phases 1–4 with no Decision Engine is a strong submission; a broken
> Decision Engine bolted on in the last hours is not.
- [x] Pick 1–2 triggers only for the MVP (recommended: "on commit,"
      "on session end") — see `PROJECT.md` §9 guardrails.
- [x] `decision_engine/triggers.py` — trigger detection wired to real
      git/session events (reuses Phase 1 capture, doesn't duplicate it).
- [x] `decision_engine/planner.py` — decides suggest-vs-execute per
      action type; passive/reversible actions (update summary, flag
      TODOs) auto-execute, anything environment-changing only suggests.
- [x] Provenance surfaced in the UI for every autonomous action taken
      (`SKILLS.md` §10).
- **Milestone check:** commit real code to a test project and confirm
  the agent proactively updates its summary/brief and surfaces a
  relevant TODO — with visible provenance — without being asked.

## Phase 5 (Day 20): Polish & submission
- [ ] Feature phase context written for MVP-winning cross-app control
      actions (`FEATURES_PHASE.md`) before implementation.
- [x] Cross-app control actions wired safely: clipboard, open app/URL,
      focus app, paste, limited keystrokes, prompt submission, result
      verification.
- [ ] External prompt handoff policy implemented: copy is safe, paste
      needs confirmation, submit to external AI requires approval.
- [ ] Visual Feedback Layer wired for OCR/screen context: design preview
      review, visible error diagnosis, prompt generation from screen, and
      visible result verification.
- [ ] Workflow Engine MVP slice implemented (`WORKFLOW_ENGINE.md`):
      `chatgpt_prompt_handoff_v1` runs through derived approval gates,
      checkpointing, verification, and decision-log provenance.
- [x] Chat-first UI pass: persistent chat bar, live project cards, inline action cards, command palette (`Cmd/Ctrl+K`), activity feed.
- [ ] Intent routing wired: NLU chat intents route through `decision_engine/intent_parser.py` → planner → execution.
- [ ] System command execution wired with provenance and undo hints.
- [ ] External agent bridge wired (`backend/automation/agent_bridge.py`) with graceful fallback for unavailable tools.
- [ ] New project creation pipeline implemented as multi-step chat flow with optional design/code generation steps.
- [ ] Debugging assistance implemented using terminal capture logs with explicit confirmation before applying changes.
- [ ] Full rehearsal of the 3-minute demo flow (`PROJECT.md` §13), 3+ times.
- [ ] Final backup demo video re-recorded against the finished build.
- [ ] Docs pass — confirm `README.md` → all files are accurate and match
      the shipped build, not the original plan.
- [ ] Submission write-up drafted, referencing `PROJECT.md` §11 (why this
      fits the Agentic Applications theme) explicitly for judges.

---

## Risk log (update as risks are found/resolved)
| Risk | Likelihood | Mitigation | Status |
|---|---|---|---|
| Tauri shell can start without the FastAPI backend | Medium | `npm run tauri dev` now starts FastAPI on `127.0.0.1:8000` before launching Vite/Tauri | Mitigated |
| Live OS automation fails during judged demo | Medium | Recorded backup video (Phase 3) | Open |
| Embedding dimension mismatch after model change | Low | Pin model in `TECH_STACK.md`, add regression test | Open |
| Retrieval overfits to demo script phrasing | Medium | Test 5+ phrasings per intent (`SKILLS.md` §5) | Open |
| Bedrock latency slows demo pacing | Medium | Add timeout + fallback raw-memory display | Open |
| Decision Engine scope slips into the last 2 days | Medium | Treat Phase 4.5 as cuttable; Phases 1–4 alone are a complete, demoable submission | Open |
| Autonomous action surprises/annoys the developer in the demo | Low-Medium | Default to suggest-not-execute for anything environment-changing (`PROJECT.md` §9) | Open |
| Chat-first redesign breaks mobile/small viewport usability | Medium | Keep responsive layout and keyboard-first command palette as fallback | Open |
| Reasoning provider tests leak settings state in full-suite order | Medium | Provider-order tests pass in isolation; isolate `config.settings` mutation or reset module state in test fixtures | Open |
