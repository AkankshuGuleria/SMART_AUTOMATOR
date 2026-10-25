# Database schema

`backend/db/schema.sql` is the canonical CockroachDB DDL. Keep this reference
and the SQL file aligned whenever the schema changes. Automated tests check
important schema/vector-dimension invariants; they do not replace testing
against a disposable CockroachDB instance.

## Conventions

- UUID identifiers are used for project and memory records; workflow run/step
  identifiers are text.
- Project activity is scoped by `project_id`.
- Embedding columns use `VECTOR(1024)`. Embedding generation, query, and
  storage must use compatible dimensions.
- Timestamps are timezone-aware where represented as `TIMESTAMPTZ`.
- Captured secrets must be redacted before persistence. The database stores
  credential reference labels only, never credential values.

## Tables

| Table | Purpose |
| --- | --- |
| `projects` | Registered local repositories |
| `sessions` | Work session boundaries and summaries |
| `commits` | Project commit history |
| `file_edits` | File paths, edit time, and optional change summaries |
| `terminal_commands` | Redacted command history and execution metadata |
| `todos` | Project TODO items and status |
| `architecture_notes` | Project architecture context |
| `daily_briefs` | Per-project daily summary fields |
| `taste_preferences` | Developer-level preference observations |
| `credential_refs` | Labels for secrets held in the OS credential store |
| `decision_log` | Decision provenance and rationale |
| `mistake_log` | Reusable symptom, cause, and fix records |
| `workflow_runs` | Workflow run inputs, status, and lifecycle |
| `workflow_steps` | Per-step policy, state, outputs, and approvals |

## Ownership and retention

`backend/db/client.py` owns application database connections and CRUD. Do not
open ad-hoc CockroachDB connections from API, automation, or UI code.
`terminal_commands` may contain sensitive operational context even after
redaction; define and apply a retention policy before using real user data.

## Schema changes

1. Update `backend/db/schema.sql`.
2. Update this document and affected database-client code.
3. Add/update tests using mocks or an explicitly provisioned local/test DB.
4. Verify vector retrieval after changes to embedding columns or dimensions.

Never point automated tests or schema experiments at production data.
