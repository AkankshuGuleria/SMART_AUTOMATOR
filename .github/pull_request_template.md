## What and why

<!-- One or two sentences: what changes and the reason. Link the issue if there is one. -->

## How it was tested

<!-- Tests added or updated, and anything checked by hand in the running app. -->

## Checklist

- [ ] `uv run pytest tests/ -q` and `uv run ruff check .` pass (backend)
- [ ] `npx oxlint src`, `npm test` and `npm run build` pass (frontend)
- [ ] New behaviour has tests that check real output, not just "no exception"
- [ ] Anything that controls the PC goes through the permission check and verifies its effect
- [ ] No secrets, personal paths or real data in code, tests, logs or screenshots
- [ ] Docs updated where behaviour, API or schema changed, plus a `CHANGELOG.md` line
