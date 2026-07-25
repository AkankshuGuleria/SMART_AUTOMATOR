# AUTOMATA (formerly "DevOS AI")

> Persistent Memory Operating Layer for Developers — an autonomous agent that
> remembers your project across sessions, restores your workspace, and
> automates repetitive engineering work using CockroachDB as long-term memory
> and Ollama (free, local) as its reasoning engine.
>
> Amazon Bedrock support is included as a commented-out alternative — uncomment
> the Bedrock section in `backend/ai/bedrock_client.py` when API keys are available.

## Start here (for humans and agents)

Read these files **in this order** before writing or changing any code:

| # | File | Purpose |
|---|------|---------|
| 1 | `PROJECT.md` | What this product is, why it exists, the demo story |
| 2 | `ARCHITECTURE.md` | System components, data flow, how pieces talk to each other |
| 3 | `TECH_STACK.md` | Exact languages, frameworks, libraries, and versions in use |
| 4 | `DATABASE_SCHEMA.md` | CockroachDB tables, vector indexes, memory model |
| 5 | `CONVENTIONS.md` | Folder structure, naming, code style, commit rules |
| 6 | `SKILLS.md` | Required skills/playbooks — frontend, backend, testing, bug-fixing, de-AI-ifying output, prompt quality |
| 7 | `ROADMAP.md` | The 20-day build plan, current phase, what's done/pending |
| 8 | `AGENTS.md` | Operating rules specifically for AI coding agents working in this repo |
| 9 | `SETUP.md` | How to get a dev environment running locally |

## Golden rules for any agent working in this repo

1. **Memory is the product.** Every feature should reinforce the idea that
   this agent has real persistent memory, not chat-history tricks. If a
   design choice makes the memory layer feel like a gimmick, reject it.
2. **Never invent scope.** If a task isn't in `ROADMAP.md`, check
   `PROJECT.md` before adding it — don't silently expand the MVP.
3. **Always update docs alongside code.** If you change the schema, update
   `DATABASE_SCHEMA.md` in the same change. If you change architecture,
   update `ARCHITECTURE.md`. Stale docs are treated as bugs.
4. **Follow `SKILLS.md` playbooks** for testing, debugging, and code review
   instead of improvising ad hoc processes.
5. **Prefer a working narrow feature over a broken wide one.** This is a
   hackathon submission with a hard deadline — see `ROADMAP.md`.

## Current status

See `ROADMAP.md` → "Current Phase" for the live status. Update it whenever a
phase is completed.
