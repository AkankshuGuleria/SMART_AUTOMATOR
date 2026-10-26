# Coding conventions

## 1. Project layout

See [STRUCTURE.md](STRUCTURE.md). Keep code in its bounded module unless a change
requires a deliberate restructure. Before moving a file, check imports, tests,
packaging, Tauri/Vite configuration and scripts that depend on its location.

## 2. File placement

- Python code: `snake_case.py`; functions and variables use `snake_case`;
  classes use `PascalCase`.
- React components: `PascalCase.tsx`; hooks and values use `camelCase`.
- Tests: `backend/tests/test_*.py` and frontend `*.test.tsx`/`*.test.ts`.
- API calls and shared request/response types belong in
  `frontend/src/lib/api.ts`.
- SQL changes belong in `backend/db/schema.sql` and require a
  `DATABASE_SCHEMA.md` update.
- Use the project package manifests and lock files; do not add unmanaged
  dependency pins.

## 3. Module boundaries

- Frontend talks to the backend API only (all calls in `frontend/src/lib/api.ts`).
- Cloud database access goes through `backend/db/client.py`; local memory
  through `backend/memory/local_store.py`.
- Model calls go through `backend/ai/bedrock_client.py`.
- Anything that controls the PC goes through `security/permissions.check()`.
- Automation reports results; it does not own database persistence.
- Reasoning/planning code describes actions; automation tools perform OS
  effects.
- Workflow steps invoke registered tools and must preserve their approval and
  provenance behavior.

## 4. Documentation

- Update `ARCHITECTURE.md` when module responsibilities or data flow change.
- Update `DATABASE_SCHEMA.md` with every schema change.
- Update `TECH_STACK.md` when dependencies, runtime requirements, or
  configuration change.
- Keep API endpoint behavior documented in `docs/API_REFERENCE.md`.
- Keep setup and test commands current in `docs/DEVELOPMENT.md`.
- Follow `SKILLS.md` for feature testing, safety, and code review.
- Record notable changes in `CHANGELOG.md` (repository root).

## 5. Definition of done

- The change is scoped and follows module boundaries.
- Relevant tests assert outputs and failure states, not only absence of
  exceptions.
- Documentation matches the shipped behavior.
- User-facing actions surface progress, approval, and failures explicitly.
- Any OS/provider/database integration is tested with safe local fixtures or
  explicit manual verification; no production service is used for tests.
