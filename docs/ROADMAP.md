# Roadmap

Released work is listed in [CHANGELOG.md](../CHANGELOG.md); verification status
in [PROJECT_STATUS.md](PROJECT_STATUS.md).

## Next

1. **Installer:** bundle the agent as a sidecar executable and ship an MSI/NSIS
   installer, so nothing runs from a source checkout.
2. **CI on Windows for the desktop shell:** build `app.exe` in CI and attach it
   to releases.
3. **Workflow screen:** run workflows and approve their gates in the UI.
4. **More verified hand-offs:** live-verify Claude, ChatGPT and Cursor
   (`cursor-agent`) the way Antigravity and Kilo Code are.

## Later

- Restore browser tabs on Resume; per-app adapters for more tools.
- Bundle fonts locally (fully offline UI).
- Optional per-install API token for the local agent.
- Clean historical duplicate rows from the CockroachDB copy.

## History

The original phased plan and the 2026-10-26 project audit are kept in
[docs/history](history/).
