# AUTOMATA — conventions and testing

Details: `docs/CONVENTIONS.md`, `docs/DEVELOPMENT.md`, `CONTRIBUTING.md`.

## Code
- Python: `snake_case`, type hints, module docstring with **Owns / Never**.
  Package manager **uv** only (`uv sync`, `uv run ...`).
- TypeScript/React: `PascalCase` components, `camelCase` functions, npm only.
- Commits: imperative mood ("Add vector retrieval"); branches `feature/…`, `fix/…`.
- Keep comments short and useful to the next reader.

## Tests (required before calling anything done)
- Backend: `cd backend; uv run pytest tests/ -q` — tests never touch the real
  DB, providers, keyboard or screen (`tests/conftest.py` enforces this; mock
  `automation.win32` / `desktop.capture` in new tests).
- Frontend: `npx tsc -b`, `npx oxlint src`, `npm test`.
- Assert real outputs and failure states, not just "no exception".
- Security changes need a regression test (`backend/tests/test_permissions.py`).

## Definition of done
- [ ] Module boundaries respected
- [ ] Tests added and green; lint clean (`uv run ruff check .`)
- [ ] Docs updated in the same change (API, schema, architecture, status)
