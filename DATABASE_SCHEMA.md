# DATABASE_SCHEMA.md — CockroachDB Memory Model

> This is the source of truth for schema. If you change a table, update
> this file in the same commit/change.

## 1. Design principles

- Structured facts (commits, TODOs, sessions) get normal relational rows
  for exact filtering (by project, date, branch).
- Anything semantically searchable (README text, commit messages, TODO
  descriptions, architecture notes, daily summaries) also gets an
  embedding row so it's retrievable by meaning, not just keyword.
- Every memory row is scoped to a `project_id` — never mix memory across
  projects in a query unless explicitly asked to compare projects.

## 2. Core tables

### `projects`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | e.g. "Eco-DPI" |
| repo_path | TEXT | local filesystem path |
| remote_url | TEXT | nullable |
| created_at | TIMESTAMPTZ | |

### `sessions`
One row per work session (a continuous period of activity on a project).
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| started_at | TIMESTAMPTZ | |
| ended_at | TIMESTAMPTZ | nullable until session closes |
| summary | TEXT | generated end-of-session summary |
| summary_embedding | VECTOR | embedding of `summary` |

### `commits`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| session_id | UUID FK | nullable |
| commit_hash | TEXT | |
| message | TEXT | |
| message_embedding | VECTOR | |
| author | TEXT | |
| committed_at | TIMESTAMPTZ | |

### `file_edits`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| session_id | UUID FK | |
| file_path | TEXT | |
| edited_at | TIMESTAMPTZ | |
| change_summary | TEXT | nullable, short description if generated |

### `terminal_commands`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| session_id | UUID FK | |
| command | TEXT | |
| cwd | TEXT | |
| exit_code | INT | nullable |
| command_embedding | VECTOR(768) | embedding of redacted command |
| run_at | TIMESTAMPTZ | |

### `todos`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| description | TEXT | |
| description_embedding | VECTOR | |
| status | TEXT | enum-like: `pending`, `in_progress`, `done` |
| source | TEXT | e.g. `code_comment`, `manual`, `agent_generated` |
| created_at | TIMESTAMPTZ | |
| resolved_at | TIMESTAMPTZ | nullable |

### `architecture_notes`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| title | TEXT | |
| content | TEXT | |
| content_embedding | VECTOR | |
| updated_at | TIMESTAMPTZ | |

### `daily_briefs`
Generated once per day per project — powers the "Good Morning" screen.
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| brief_date | DATE | |
| commits_count | INT | |
| highlights | TEXT[] | short bullet list, e.g. "Authentication module completed" |
| pending_items | TEXT[] | |
| last_edited_file | TEXT | |
| generated_at | TIMESTAMPTZ | |

### `taste_preferences`
Learned developer preferences — separate from project event memory.
See `SKILLS.md` §7 (Taste Memory Skill).
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| developer_id | UUID | scope to developer, not just project — taste should generalize across projects unless overridden |
| category | TEXT | e.g. `naming_convention`, `commit_style`, `error_handling`, `library_choice` |
| description | TEXT | e.g. "prefers early returns over nested conditionals" |
| description_embedding | VECTOR | |
| confidence | FLOAT | 0–1, rises as more evidence is observed |
| evidence_count | INT | number of observed instances supporting this |
| last_observed_at | TIMESTAMPTZ | used to weight recency, see `SKILLS.md` §7 |

### `credential_refs`
**Never stores secret values.** Only a label/reference the Automation
Layer resolves against the OS-native credential store at runtime. See
`SKILLS.md` §8.
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | nullable — some creds are global (e.g. git host token) |
| ref_name | TEXT | the lookup key in the OS credential manager, e.g. `"eco-dpi-github-token"` |
| purpose | TEXT | e.g. "GitHub PAT", "Bedrock-adjacent service key" |
| expires_at | TIMESTAMPTZ | nullable, only if known |
| last_used_at | TIMESTAMPTZ | |

### `decision_log`
Captures *why*, not just *what*. See `SKILLS.md` §9.
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | nullable — some decisions are project-wide/tooling-wide |
| decision | TEXT | short statement of what was decided |
| rationale | TEXT | 2–5 sentences: alternatives considered, why this won |
| rationale_embedding | VECTOR | |
| decided_at | TIMESTAMPTZ | |

### `mistake_log`
Recurring-mistake prevention. See `SKILLS.md` §10.
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK | |
| symptom | TEXT | what was observed |
| root_cause | TEXT | |
| fix | TEXT | |
| root_cause_embedding | VECTOR | so future similar symptoms can be matched semantically |
| module | TEXT | e.g. `memory_manager`, `automation_layer` |
| occurred_at | TIMESTAMPTZ | |

### `workflow_runs`
Workflow execution instances. See `FEATURES_PHASE.md` (Workflow Engine).
| column | type | notes |
|---|---|---|
| id | TEXT PK | |
| workflow_id | TEXT NOT NULL | |
| workflow_version | INT NOT NULL | |
| status | TEXT NOT NULL | `created`, `running`, `completed`, `failed`, `awaiting_approval`, `paused`, `cancelled` |
| inputs_json | TEXT NOT NULL | |
| started_at | TIMESTAMP NOT NULL | |
| completed_at | TIMESTAMP | |
| initiated_by | TEXT NOT NULL | `user` or `trigger:<trigger_id>` |
| project_id | TEXT NOT NULL | |

### `workflow_steps`
Individual steps within a workflow run. See `FEATURES_PHASE.md` (Workflow Engine).
| column | type | notes |
|---|---|---|
| id | TEXT PK | |
| run_id | TEXT NOT NULL | FK → workflow_runs(id) |
| step_def_id | TEXT NOT NULL | matches the `id` in the workflow definition's steps[] |
| tool | TEXT NOT NULL | references a tool in `decision_engine/tools.py` |
| policy | TEXT NOT NULL | resolved policy at execution time |
| status | TEXT NOT NULL | `pending`, `running`, `succeeded`, `failed`, `waiting_for_approval`, `approved`, `rejected` |
| rendered_inputs_json | TEXT | |
| output_json | TEXT | |
| redactions_json | TEXT | what was stripped before this step ran, if anything |
| started_at | TIMESTAMP | |
| completed_at | TIMESTAMP | |
| approved_by | TEXT | |
| approved_at | TIMESTAMP | |

## 3. Vector search

- Use CockroachDB's distributed vector indexing on the `*_embedding`
  columns above.
- Standard retrieval query shape: embed the user's question → vector
  search against relevant table(s) (filtered by `project_id`, optionally
  a date range) → return top-k rows → pass to Reasoning Engine for grounded
  answer composition.
- Keep embedding model choice consistent across write and query time —
  record the exact model/dimension in `TECH_STACK.md`.

## 4. Retention / hygiene

- `terminal_commands` can grow fast — consider a rolling retention window
  (e.g., 90 days) or summarization-then-prune strategy so the table
  doesn't dominate storage without adding retrieval value.
- Never store secrets/credentials that might appear in terminal commands
  or file edits — redact obvious patterns (API keys, tokens, passwords)
  before writing to CockroachDB. See `SKILLS.md` → "Removing AI Presence
  & Data Hygiene" for redaction guidance.

## 5. Open schema questions (resolved)

- [x] Exact embedding dimension / model → 768 (nomic-embed-text via Ollama, or external APIs)
- [ ] Whether `daily_briefs` is generated on-demand or via a scheduled job.
- [ ] Whether multi-project cross-search is needed for MVP (default: no).
