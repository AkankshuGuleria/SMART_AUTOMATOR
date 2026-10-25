# Repository conventions

## 1. Project layout

```text
backend/
  ai/                 model and embedding provider integrations
  api/                FastAPI routes and WebSocket
  automation/         OS, process, command, OCR, and external-app actions
  db/                 shared database client and schema.sql
  decision_engine/    intent parsing, planning, tools, and triggers
  memory/             capture, embedding, and retrieval
  workflow_engine/    workflow definitions, execution, and checkpoints
  tests/              backend unit and API tests
  main.py             API and watcher startup
  config.py           backend settings and feature flags
frontend/
  src/components/     reusable components and layout
  src/lib/             API and WebSocket client
  src/screens/         screen-level UI
  src/styles/          global styles
  src-tauri/           desktop shell
docs/                  product and operational documentation
scripts/               local development helpers
```

Keep code in its current bounded module unless a change requires a deliberate
restructure. Before moving a file, identify imports, tests, packaging,
Tauri/Vite configuration, and scripts that depend on its location.

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

- Frontend talks to the backend API; it never connects directly to CockroachDB
  or model providers.
- Database connections and writes go through `backend/db/client.py`.
- Model calls go through `backend/ai/bedrock_client.py`.
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

## 5. Definition of done

- The change is scoped and follows module boundaries.
- Relevant tests assert outputs and failure states, not only absence of
  exceptions.
- Documentation matches the shipped behavior.
- User-facing actions surface progress, approval, and failures explicitly.
- Any OS/provider/database integration is tested with safe local fixtures or
  explicit manual verification; no production service is used for tests.
