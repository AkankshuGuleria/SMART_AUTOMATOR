# AGENTS.md — Operating Rules for AI Coding Agents

This file is specifically for AI agents (Claude Code, Cursor, Copilot
Workspace, etc.) working autonomously or semi-autonomously in this repo.

## 1. Before doing anything

1. Read `docs/README.md`, then `docs/PROJECT.md`, `docs/ARCHITECTURE.md`,
   `docs/DATABASE_SCHEMA.md`, `docs/CONVENTIONS.md`, `docs/SKILLS.md`,
   `docs/ROADMAP.md` — in that order — if you have not already loaded them
   this session.
2. Check `docs/ROADMAP.md` → "Current Phase" to understand what's in scope
   right now. Don't jump ahead to a later phase's features unless asked.
3. If a request conflicts with `docs/PROJECT.md` §6 (MVP boundaries) or the
   module boundaries in `docs/CONVENTIONS.md` §3, flag the conflict to the
   user before proceeding rather than silently expanding scope.

## 2. While working

- Follow the relevant playbook in `docs/SKILLS.md` for the type of work
  (testing, bug-fixing, frontend, backend, prompt quality, output
  naturalness, demo prep) rather than improvising a process.
- Keep changes scoped to one module at a time where possible
  (Frontend / Persistent Memory Engine / Reasoning Engine / Automation Layer / DB schema).
- Any schema change → update `docs/DATABASE_SCHEMA.md` in the same change.
- Any architectural change (new component, changed data flow, changed OS
  strategy) → update `docs/ARCHITECTURE.md` in the same change.
- Any new/changed dependency or version pin → update `docs/TECH_STACK.md`.
- When generating user-facing text (briefs, summaries, commit messages),
  apply `docs/SKILLS.md` §6 (Removing AI Presence & Output Naturalness) —
  no chatbot filler, no fabricated specificity, no hedging by default.

## 3. Testing discipline

- Don't mark a task complete without following `docs/SKILLS.md` §1 (Testing
  Skill) checklist for the relevant area.
- Never point tests at a real/production CockroachDB instance or burn
  real Bedrock API calls in automated test runs — use mocks/fixtures/local
  test DB per the checklist.

## 4. Secrets & data hygiene

- Never write real credentials into any file in this repo, including
  `.md` files, code comments, or example configs. Use placeholder names
  as shown in `docs/TECH_STACK.md` §"Environment variables".
- Apply secret redaction (`docs/SKILLS.md` §6) to any captured terminal
  command, diff, or log before it's persisted or displayed.

## 5. When you're unsure

- If a design decision isn't resolved in the docs (look for `____` blanks
  or "Open" items in `docs/ROADMAP.md`'s risk log / `docs/TECH_STACK.md`),
  ask the user rather than guessing and silently picking a default that could
  conflict with later work.
- If you do have to make a reasonable assumption to keep moving, state
  the assumption explicitly in your response and note it in the relevant
  doc file so it isn't lost.

## 6. After finishing a unit of work

- Update `docs/ROADMAP.md` checkboxes for whatever was actually completed.
- Note any new risk discovered in `docs/ROADMAP.md`'s risk log.
- Confirm docs still match the shipped code (README's golden rule #3).
