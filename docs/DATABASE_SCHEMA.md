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

## Local stores (SQLite, `%LOCALAPPDATA%\AUTOMATA\`)

These files are created on first use (override the folder with
`AUTOMATA_DATA_DIR`). They are per-user and never leave the machine.

| File / table | Owner module | Purpose |
| --- | --- | --- |
| `memory.db` · `projects` | `memory/local_store.py` | Mirror of cloud projects + local-only projects (`source = cloud\|local`), `last_active_at` |
| `memory.db` · `memories` | `memory/local_store.py` | `kind` (commit, file_edit, terminal, todo, decision, note, chat, brief, task, architecture, mistake), redacted `content`, `ref` (unique per project+kind, e.g. commit hash or `db:<table>:<id>`), `meta` JSON, `created_at`, optional `embedding` (float32 blob) + `embedding_model`, `dedup_key` (content hash, + day for `file_edit`/`decision`; see `DEDUP_SCOPE` — a repeat only moves `created_at` forward) |
| `memory.db` · `memories_fts` | `memory/local_store.py` | FTS5 index (porter tokenizer) kept in sync by triggers |
| `memory.db` · `snapshots` | `workspace/snapshot.py` | Session snapshots (JSON), last 50 per project |
| `memory.db` · `kv` | various | Settings and caches: `active_project_id`, `ollama_chat_model`, `fastembed_enabled`, `brief:<project>`, `profile:<ver>:<project>`, `terminal_history:<file>` (read position in the PowerShell history), `migration:dedup_v1` (one-time duplicate clean-up result) |
| `tasks.db` · `tasks`, `task_steps` | `tasks/store.py` | Delegation tasks, step status/policy/output |
| `tasks.db` · `needs` | `tasks/store.py` | Inbox items: variable name, kind, provider, instructions, target `.env`, status/resolution. **Never a value.** |
| `usage.db` · `usage_segments` | `monitoring/app_usage.py` | One row per foreground-app focus segment (90-day retention) |
| `task_baselines/<task>.json` | `tasks/engine.py` | File mtimes captured at hand-off, used to detect the agent's changes |
