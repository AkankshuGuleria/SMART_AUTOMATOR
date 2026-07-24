# AGENTS.md — Operating Rules for AI Coding Agents

This file is specifically for AI agents (Claude Code, Cursor, Copilot
Workspace, etc.) working autonomously or semi-autonomously in this repo.

## 1. Before doing anything

1. Read `README.md`, then `PROJECT.md`, `ARCHITECTURE.md`,
   `DATABASE_SCHEMA.md`, `CONVENTIONS.md`, `SKILLS.md`, `ROADMAP.md` — in
   that order — if you have not already loaded them this session.
2. Check `ROADMAP.md` → "Current Phase" to understand what's in scope
   right now. Don't jump ahead to a later phase's features unless asked.
3. If a request conflicts with `PROJECT.md` §6 (Non-goals) or the module
   boundaries in `CONVENTIONS.md` §3, flag the conflict to the user before
   proceeding rather than silently expanding scope.

## 2. While working

- Follow the relevant playbook in `SKILLS.md` for the type of work
  (testing, bug-fixing, frontend, backend, prompt quality, output
  naturalness, demo prep) rather than improvising a process.
- Keep changes scoped to one module at a time where possible
  (Frontend / Persistent Memory Engine / Reasoning Engine / Automation Layer / DB schema).
- Any schema change → update `DATABASE_SCHEMA.md` in the same change.
- Any architectural change (new component, changed data flow, changed OS
  strategy) → update `ARCHITECTURE.md` in the same change.
- Any new/changed dependency or version pin → update `TECH_STACK.md`.
- When generating user-facing text (briefs, summaries, commit messages),
  apply `SKILLS.md` §6 (Removing AI Presence & Output Naturalness) —
  no chatbot filler, no fabricated specificity, no hedging by default.

## 3. Testing discipline

- Don't mark a task complete without following `SKILLS.md` §1 (Testing
  Skill) checklist for the relevant area.
- Never point tests at a real/production CockroachDB instance or burn
  real Bedrock API calls in automated test runs — use mocks/fixtures/local
  test DB per the checklist.

## 4. Secrets & data hygiene

- Never write real credentials into any file in this repo, including
  `.md` files, code comments, or example configs. Use placeholder names
  as shown in `TECH_STACK.md` §"Environment variables".
- Apply secret redaction (`SKILLS.md` §6) to any captured terminal
  command, diff, or log before it's persisted or displayed.

## 5. When you're unsure

- If a design decision isn't resolved in the docs (look for `____` blanks
  or "Open" items in `ROADMAP.md`'s risk log / `TECH_STACK.md`), ask the
  user rather than guessing and silently picking a default that could
  conflict with later work.
- If you do have to make a reasonable assumption to keep moving, state
  the assumption explicitly in your response and note it in the relevant
  doc file so it isn't lost.

## 6. After finishing a unit of work

- Update `ROADMAP.md` checkboxes for whatever was actually completed.
- Note any new risk discovered in `ROADMAP.md`'s risk log.
- Confirm docs still match the shipped code (README's golden rule #3).
