# Contributing to AUTOMATA

Thanks for helping. This guide covers the workflow; the technical orientation
(repository map, module rules, where to start) is in [docs/AGENTS.md](docs/AGENTS.md).

## Set up

```powershell
cd backend;  uv sync --extra dev;  cd ..
cd frontend; npm ci;               cd ..
.\scripts\dev.ps1                  # agent + UI
```

Optional: `cd backend; uv run pre-commit install` to run secret scanning and
ruff before every commit. Full guide: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Workflow

1. Branch from `main`: `feature/<short-name>` or `fix/<short-name>`.
2. Keep changes focused; follow the module boundaries in
   [docs/AGENTS.md §4](docs/AGENTS.md#4-rules-that-matter-here).
3. Add tests that assert real outputs and failure states.
4. Update the docs your change touches (API, schema, architecture, status) and
   add a line to [CHANGELOG.md](CHANGELOG.md) under *Unreleased*.
5. Run the checks below, then open a pull request using the template.

## Checks (CI runs the same)

```powershell
cd backend
uv run pytest tests/ -q
uv run ruff check .              # includes the bandit security rules

cd ../frontend
npx oxlint src
npm test
npm run build                    # type-check + production build
```

CI also audits Python, npm and Rust dependencies for known vulnerabilities.

## Rules that keep the project safe

- **Never commit secrets.** Use `backend/.env` (git-ignored). Test fixtures use
  obviously fake values.
- **Tests never touch the real world** — no real database, model provider,
  keyboard or screen. `backend/tests/conftest.py` enforces this.
- **Anything that controls the PC** goes through `security/permissions.check()`
  and verifies its effect; never report success you did not see.
- **Untrusted text** (memory, OCR, model replies) is rendered as text, never HTML.
- Security fixes come with a regression test in `backend/tests/test_permissions.py`.

## Commit messages

Imperative mood, one subject line under ~72 characters, a body that explains
*why* when it is not obvious:

```
Add verified Kilo Code hand-off

Kilo's chat box is found by its accessible name and opened via its
activity-bar tab, so delivery works whatever has keyboard focus.
```

## Reporting security issues

Do not open a public issue for a vulnerability — see [SECURITY.md](SECURITY.md).
