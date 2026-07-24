# CONVENTIONS.md — Folder Structure & Code Style

## 1. Recommended repo layout

```
D:\AUTOMATA
├── README.md
├── PROJECT.md
├── ARCHITECTURE.md
├── TECH_STACK.md
├── DATABASE_SCHEMA.md
├── CONVENTIONS.md
├── SKILLS.md
├── ROADMAP.md
├── AGENTS.md
├── SETUP.md
│
├── frontend/                  # React + Tauri desktop app
│   ├── src/
│   │   ├── components/
│   │   ├── screens/           # MorningBrief, RestoreWorkspace, QueryChat
│   │   ├── lib/                # API client to Python agent
│   │   └── styles/
│   ├── src-tauri/              # Tauri Rust shell
│   └── package.json
│
├── backend/                    # Python background agent
│   ├── memory/                 # Persistent Memory Engine module
│   │   ├── capture.py          # file watcher, git hooks, terminal capture
│   │   ├── embeddings.py
│   │   └── retrieval.py        # vector search queries
│   ├── ai/                      # Reasoning Engine module
│   │   ├── bedrock_client.py
│   │   └── prompts/
│   ├── automation/               # Automation Layer (OS-specific)
│   │   ├── restore.py
│   │   ├── dev_servers.py
│   │   └── os_windows.py       # (or os_mac.py / os_linux.py)
│   ├── decision_engine/          # Autonomous, unsolicited action (triggers)
│   │   ├── triggers.py          # e.g. on_commit, on_session_end
│   │   └── planner.py           # decides suggest-vs-execute per action
│   ├── db/
│   │   ├── schema.sql           # matches DATABASE_SCHEMA.md exactly
│   │   └── client.py
│   ├── api/                      # local API exposed to frontend
│   │   └── server.py
│   ├── tests/
│   └── main.py                   # background agent entrypoint
│
├── scripts/                     # setup/dev scripts
└── demo/                        # recorded fallback demo assets
```

## 2. Naming conventions

- Python: `snake_case` for files/functions/vars, `PascalCase` for classes.
- React: `PascalCase` component files, `camelCase` functions/vars.
- CockroachDB tables/columns: `snake_case`, plural table names (matches
  `DATABASE_SCHEMA.md`).
- Branch names: `feature/<short-desc>`, `fix/<short-desc>`.
- Commit messages: imperative mood, present tense — "Add vector retrieval
  for TODOs" not "Added" or "Adding".

## 3. Module boundaries (do not violate)

- Frontend never talks to CockroachDB or Bedrock directly — always through
  the Python Agent's local API.
- Automation Layer never writes directly to CockroachDB — it reports
  status back to the Persistent Memory Engine, which writes.
- Reasoning Engine never executes OS actions — only Automation Layer does.
- Decision Engine never bypasses the Agent Loop — it triggers the same
  Observe → Reason → Plan → Execute → Update Memory cycle as a
  user-initiated query, just without a user prompt starting it. It never
  calls Bedrock or CockroachDB directly on its own path.

## 4. Documentation-in-code

- Every module in `backend/` starts with a short docstring describing:
  what it owns, what it must never do, and which doc file (`ARCHITECTURE.md`
  section, `DATABASE_SCHEMA.md` table) it corresponds to.

## 5. Definition of done for a feature

A feature isn't done until:
- [ ] Code is written and follows the module boundaries above.
- [ ] Relevant doc file(s) updated in the same change.
- [ ] Tests exist per `SKILLS.md` → Testing Skill.
- [ ] Manually run through the exact demo flow step it supports
      (see `PROJECT.md` §13) and confirmed working.
