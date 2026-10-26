# Changelog

All notable changes to AUTOMATA. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow the
desktop app version in `frontend/src-tauri/tauri.conf.json`.

## [Unreleased]

### Added
- **Permissions:** every action that controls the PC (apps, typing, clipboard,
  music, screen reading, Resume, commands) asks first — Allow once / Always
  allow / Deny — with per-category settings in Settings → Permissions.
- **Local-only API guard:** refuses DNS rebinding, requests from other
  websites, foreign WebSocket origins and oversized bodies.
- **Kilo Code** as a delegation agent inside Antigravity IDE.
- Work bar shortcut settings (record, reset, open now) and a sidebar button.
- Resume reopens the editor you last used for the project (from app-usage history).
- Windows Defender "Controlled folder access" blocks are explained (never changed).
- Security audit report, CI workflow, contributing guide, editor and git attributes.

### Changed
- Messages like "open antigravity and use kilo code to …" become delegation tasks.
- Apps open from their real executable; success is reported only when a window appears.
- Dev servers on Resume use the project's run book instead of a stored command line.
- Documentation reorganised: current reference docs in `docs/`, dated reports in `docs/history/`.
- One development launcher, `scripts/dev.ps1`; utility scripts moved to `scripts/`.

### Fixed
- Work bar text box did not receive keyboard focus; it could also vanish right after opening.
- `.env` values with line breaks could inject extra variables.
- Workflow checkpoints used `pickle` and unsanitised file names.
- Chat rendered replies through `innerHTML` (now plain React text).

### Security
- Upgraded GitPython 3.2.1, urllib3 2.8.0, certifi, cryptography, filelock,
  virtualenv, werkzeug, vite 8.3.5, vitest 4.1.12, tokio — 0 known vulnerabilities.
- Strict Content Security Policy for the desktop app.

## [0.1.0] — 2026-10-26

### Added
- AI work bar (Alt+Space): questions, Spotify and media control, web search,
  reading the screen on request.
- Verified hand-off into AI apps' chat boxes (Antigravity IDE and app), with
  clarifying questions before delegation and approval gates for hand-off and build.
- Always-on Tauri tray app with agent supervisor, single instance and start at sign-in.
- Local offline memory (SQLite FTS5) with CockroachDB sync, session snapshots and Resume.
- Project profiles: project type, stack, run book, env vars and modules per project.
- Needs inbox writing to Windows Credential Manager or the project's `.env`.
- System resources (CPU/GPU/RAM/disk) and app-usage analytics.
- Offline model routing to Ollama with a guided setup.

### Fixed
- Console windows flashing whenever the agent ran a background command.
- Duplicate memory rows and noisy search results; file reads counted as edits.
- Desktop actions that reported success without verifying the result.

## Earlier — 2026-07 to 2026-08

Initial scaffold, Tauri shell, grounded queries and repository explanation,
multi-provider reasoning with fallbacks, cross-app tools, visual feedback,
the workflow engine and the chat-first UI.
