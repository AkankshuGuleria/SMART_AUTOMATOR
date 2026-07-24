# AUTOMATA — Code Conventions

## Naming
- Python: `snake_case` files/functions/vars, `PascalCase` classes
- TypeScript/React: `PascalCase` component files, `camelCase` functions/vars
- CockroachDB: `snake_case` columns, plural table names
- Branch names: `feature/<short-desc>` or `fix/<short-desc>`
- Commits: imperative mood — "Add vector retrieval" not "Added" or "Adding"

## Package manager
- Backend: **uv** (never pip). Commands: `uv sync`, `uv run python ...`, `uv run pytest`
- Frontend: **npm** (never yarn or pnpm for this project)

## Python module docstrings (required on every backend module)
Every file in `backend/` must start with:
```python
"""
<module>/<file>.py — AUTOMATA <Component Name>.

Owns:    <what this module is responsible for>
Never:   <what this module must never do — module boundary>
Ref:     <ARCHITECTURE.md section>, <DATABASE_SCHEMA.md table if applicable>
"""
```

## DB writes
- ALL CockroachDB writes go through `backend/db/client.py` → `get_session()` context manager.
- No `create_engine()` calls anywhere except `db/client.py`.

## Definition of done for any feature
- [ ] Code follows module boundaries (see `CONVENTIONS.md §3`)
- [ ] Relevant doc updated in the same change
- [ ] Tests written per the Testing Skill (`SKILLS.md §1`)
- [ ] Manually run through the demo flow step it supports (`PROJECT.md §13`)

## What NOT to do
- Never `import psycopg2` or `create_engine()` outside `db/client.py`
- Never `import boto3` outside `ai/bedrock_client.py`
- Never `subprocess.Popen` outside `automation/os_windows.py`
- Never store secrets in any file — use `backend/.env` (gitignored) only
