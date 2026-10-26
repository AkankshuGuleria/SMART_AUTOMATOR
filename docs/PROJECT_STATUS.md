# Project status

Last full verification: **2026-10-26** on Windows 11 (16 GB RAM, RTX 3050 4 GB).
"Verified" means an automated test asserts it **and/or** it was exercised in
the running app. Nothing is marked verified because a screen or route exists.

Legend: ✅ verified · ⚠️ works with a caveat · ❌ missing

## Quality gates

| Check | Result |
| --- | --- |
| Backend tests (`uv run pytest tests/`) | ✅ 395 passed — isolated from real DB, providers, keyboard and screen |
| Backend lint + security lint (ruff, bandit) | ✅ clean; 0 high-severity findings |
| Frontend type-check / lint / tests / build | ✅ clean / clean / 6 passed / built |
| Dependency audits (pip-audit, npm audit, cargo audit) | ✅ 0 known vulnerabilities |
| Secrets in git history | ✅ none (fake test keys only) |
| Desktop app build (`tauri build`) | ✅ `app.exe` runs under a strict CSP |
| Live API end-to-end checks | ✅ 22/22 core + 23/23 audit checks |

Details: [SECURITY_AUDIT.md](SECURITY_AUDIT.md).

## Features

### Workspace and desktop app

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Tray app, close-to-tray, single instance, start hidden at sign-in | ✅ | Live |
| Agent supervisor (starts/restarts the Python agent, no console) | ✅ | Live |
| AI work bar — shortcut (default Alt+Space, changeable), keyboard focus, click-away hide | ✅ | Live: 6/6 opens kept focus; shortcut change/reset via Settings |
| No console windows from background processes | ✅ | Live probe |
| Setup & health (12 checks with fix hints, incl. Defender blocks, permissions) | ✅ | Live |
| Native notifications | ⚠️ | Wired; not observed on screen |

### Memory

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Local offline memory (SQLite FTS5) with cloud sync | ✅ | Tests + live |
| Duplicate-free capture (terminal, edits, commits) | ✅ | Live: 9,108 duplicates removed; re-activation adds none |
| Answers grounded in memory, ranked and de-duplicated | ✅ | `test_memory_quality.py` + live |
| Snapshots (10 min, idle, shutdown, manual) | ✅ | Live |
| Resume — reopens the editor you last used (usage history), recent files, terminal, servers | ✅ | Live: AUTOMATA → Antigravity IDE; REACT → VS Code |
| Semantic (vector) search offline | ⚠️ | Needs Ollama `nomic-embed-text` or the `local-ai` extra; keyword search always works |

### Projects and AI

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Project profile: type, stack, run book, env vars, modules | ✅ | Tests + live on several repos |
| Cloud models online, Ollama offline, "which model answered" | ✅ | Tests + live |
| Local model recommendation, install and download | ⚠️ | Tested with mocks; Ollama not installed on the test PC |

### Delegation to AI apps

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| "using / open X and …" → task with questions, prompt, approval gates | ✅ | Live via chat |
| Antigravity IDE agent panel | ✅ | Live end to end: `hello.html` created |
| Kilo Code in Antigravity IDE | ✅ | Live end to end: Valorant portfolio built, build passed |
| Watch waits while the agent is busy | ✅ | Kilo ◔/✓ state; test |
| Needs inbox → Credential Manager / `.env` (injection-safe) | ✅ | Tests |
| VS Code (`code chat`) | ⚠️ | Delivery reported as unconfirmed (no identifiable chat box) |
| Claude app, ChatGPT, Cursor | ⚠️ | Adapters implemented; not run live |

### Desktop control and work bar

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Verified focus, type, paste, browser tabs, window list | ✅ | Live + tests |
| OCR (Windows engine), DPI-correct capture, read the window behind AUTOMATA | ✅ | Live |
| Media keys, now playing, "play X on Spotify" | ✅ | Live |
| Web search, open apps by name (window confirmed) | ✅ | Tests + live |
| Unicode-safe clipboard | ✅ | Live |

### Security

| Feature | Status | Evidence / notes |
| --- | --- | --- |
| Ask before controlling the PC (Allow once / Always / Deny) | ✅ | Tests on every gated route; live prompts |
| Local-only API (Host, Origin, WebSocket, size checks) | ✅ | Live attack probes refused |
| No unsafe deserialisation, injection-safe `.env` and SQL | ✅ | Tests |
| Desktop CSP | ✅ | Live |

## Known limits and next steps

1. **Ollama** is not installed on the test PC: install it from Setup & health
   for full offline AI and semantic search (the C: drive is ~97 % full — set
   `OLLAMA_MODELS` to a folder on D:).
2. **Packaging:** no installer yet; the desktop app runs the agent from
   `backend\.venv` (no bundled agent executable).
3. **Workflow engine** has no screen; **Cursor** needs `cursor-agent` for its
   CLI path; browser tabs are not restored on Resume.
4. Older duplicate terminal rows remain in the optional CockroachDB copy (they
   no longer reach local memory or answers).
5. One registered project (`SAM MOTO FINAL`) has a relative path — re-add it
   with its full folder path.

Roadmap: [ROADMAP.md](ROADMAP.md).
