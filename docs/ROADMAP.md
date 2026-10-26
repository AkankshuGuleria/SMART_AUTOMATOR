# Roadmap

## Done (2026-10-26)

- Project review, cleanup, monitoring and app usage.
- Smart-workspace Phases 0–5 (see `SMART_WORKSPACE_PLAN.md`): honest desktop
  automation, always-on tray app with backend supervisor, offline local memory,
  model router with Ollama setup, session snapshots/resume, project profiles,
  window/tab control with read-back, delegation tasks with approval gates, Needs
  inbox, Tasks/Inbox/Setup screens, AI work bar.
- Work bar (Alt+Space / Ctrl+Alt+A): media + Spotify, web search, read screen on
  request; clarifying questions before delegation; verified Antigravity chat-box
  hand-off; no console popups.

Evidence and remaining limits: `PROJECT_STATUS.md`.

## Next

1. Packaging: PyInstaller sidecar for the backend + Tauri installer (NSIS/MSI).
2. Live-verify the Antigravity / VS Code / ChatGPT hand-off end to end and tune
   prompts from real runs.
3. Workflow screen (approve/reject workflow gates in the UI).
4. Cursor via `cursor-agent`; Claude Code CLI as the preferred Claude path.
5. Browser-tab restore during resume; per-app adapters for more apps.
6. Optional API token for the local API.
