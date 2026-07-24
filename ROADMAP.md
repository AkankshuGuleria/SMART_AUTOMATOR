# ROADMAP.md — 20-Day Build Plan

## Current Phase
> **Update this line as you progress:** `Phase 0 - In Progress | Next: provision CockroachDB, provision Bedrock access, finish Tauri shell`

---

## Phase 0 (Day 0): Setup & decisions
- [x] Pick primary OS for Automation Layer → **Windows** (`ARCHITECTURE.md` §6 — filled in).
- [x] Pin exact versions in `TECH_STACK.md` (decided items filled; Bedrock/embedding model TBD pending AWS provisioning).
- [ ] Provision CockroachDB instance (local or cloud).
- [ ] Provision AWS Bedrock access + confirm model access in target region.
- [x] MCP model decided: AUTOMATA consumes CockroachDB's Managed MCP
      Server (`ARCHITECTURE.md` §7) — no further decision needed here.
- [x] Scaffold repo per `CONVENTIONS.md` §1, including `decision_engine/`.
- [ ] Finish Tauri desktop shell (`frontend/src-tauri/` is not present yet).

## Phase 1 (Days 1–5): Memory capture
- [ ] Implement `projects`, `sessions`, `commits`, `file_edits`,
      `terminal_commands`, `todos` tables (`DATABASE_SCHEMA.md`).
- [ ] File watcher capturing edits → `file_edits`.
- [ ] Git hook / polling capturing commits → `commits`.
- [ ] Terminal command capture → `terminal_commands` (with secret
      redaction per `SKILLS.md` §6).
- [ ] Manual + code-comment TODO capture → `todos`.
- [ ] Basic session start/end tracking.
- [ ] `credential_refs` table + OS-native vault integration (never store
      real secrets in CockroachDB) — see `SKILLS.md` §8.
- [ ] Secret redaction pass applied to all capture paths before writes.
- [x] Secret redaction utility implemented and covered by unit tests.
- **Milestone check:** can you query CockroachDB directly and see real
  captured activity from a real coding session?

## Phase 2 (Days 6–10): Retrieval & reasoning
- [ ] Embedding generation pipeline wired to all `*_embedding` columns.
- [ ] Vector search query layer (`retrieval.py`).
- [ ] Bedrock client + grounded-answer prompt (`SKILLS.md` §5).
- [ ] "What was I working on yesterday?" working end-to-end from a real
      question to a real grounded answer.
- [ ] `daily_briefs` generation job/endpoint.
- [ ] `taste_preferences` inference pipeline: derive naming/style/library
      signals from the developer's own commit history — see
      `SKILLS.md` §7.
- [ ] `decision_log` and `mistake_log` tables wired up and populated as
      real decisions/bugs happen during the build itself (dogfood the
      product on its own development).
- **Milestone check:** ask 5 differently-phrased questions about the same
  underlying activity and confirm retrieval + answers stay correct.

## Phase 3 (Days 11–14): Autonomous Workspace Recovery
- [ ] Automation Layer interface + stub implementation for tests.
- [ ] Real implementation for chosen primary OS: git branch checkout,
      terminal restore, dev server start/stop.
- [ ] Stretch: editor auto-launch, browser auto-launch.
- [ ] Frontend "Restore workspace?" flow with step-by-step progress UI.
- [ ] Record the first full backup demo video as soon as this milestone
      works once, even roughly.
- **Milestone check:** one-click restore works reliably 5 times in a row
  on the actual demo machine.

## Phase 4 (Days 15–17): Agent Actions
- [ ] "Generate commit message" (grounded in actual diff/staged changes).
- [ ] "Explain repository" (grounded in README + architecture notes +
      folder structure).
- [ ] "Find authentication code" (or equivalent semantic code-location
      query) — grounded in file/commit memory, not live code search,
      unless code search is explicitly added as a supplementary source.
- [ ] "Start development environment" command wired to Automation Layer.
- **Milestone check:** each command works from a natural-language phrasing
  a judge might actually use, not just the exact scripted phrase.

## Phase 4.5 (Days 18–19): Autonomous Decision Engine
> This is genuinely new scope, not a renaming exercise — budget real time
> for it and treat it as cuttable if Phases 1–4 ran long. A working
> Phases 1–4 with no Decision Engine is a strong submission; a broken
> Decision Engine bolted on in the last hours is not.
- [ ] Pick 1–2 triggers only for the MVP (recommended: "on commit,"
      "on session end") — see `PROJECT.md` §9 guardrails.
- [ ] `decision_engine/triggers.py` — trigger detection wired to real
      git/session events (reuses Phase 1 capture, doesn't duplicate it).
- [ ] `decision_engine/planner.py` — decides suggest-vs-execute per
      action type; passive/reversible actions (update summary, flag
      TODOs) auto-execute, anything environment-changing only suggests.
- [ ] Provenance surfaced in the UI for every autonomous action taken
      (`SKILLS.md` §10).
- **Milestone check:** commit real code to a test project and confirm
  the agent proactively updates its summary/brief and surfaces a
  relevant TODO — with visible provenance — without being asked.

## Phase 5 (Day 20): Polish & submission
- [ ] Full rehearsal of the 3-minute demo flow (`PROJECT.md` §13), 3+ times.
- [ ] Final backup demo video re-recorded against the finished build.
- [ ] UI pass for consistency, loading/error states (`SKILLS.md` §3).
- [ ] Docs pass — confirm `README.md` → all files are accurate and match
      the shipped build, not the original plan.
- [ ] Submission write-up drafted, referencing `PROJECT.md` §11 (why this
      fits the Agentic Applications theme) explicitly for judges.

---

## Risk log (update as risks are found/resolved)
| Risk | Likelihood | Mitigation | Status |
|---|---|---|---|
| Live OS automation fails during judged demo | Medium | Recorded backup video (Phase 3) | Open |
| Embedding dimension mismatch after model change | Low | Pin model in `TECH_STACK.md`, add regression test | Open |
| Retrieval overfits to demo script phrasing | Medium | Test 5+ phrasings per intent (`SKILLS.md` §5) | Open |
| Bedrock latency slows demo pacing | Medium | Add timeout + fallback raw-memory display | Open |
| Decision Engine scope slips into the last 2 days | Medium | Treat Phase 4.5 as cuttable; Phases 1–4 alone are a complete, demoable submission | Open |
| Autonomous action surprises/annoys the developer in the demo | Low-Medium | Default to suggest-not-execute for anything environment-changing (`PROJECT.md` §9) | Open |
