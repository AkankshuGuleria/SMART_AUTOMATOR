-- backend/db/schema.sql — AUTOMATA CockroachDB Schema
--
-- This file is the canonical DDL for all AUTOMATA tables.
-- It must stay in sync with DATABASE_SCHEMA.md at all times.
-- Run against a fresh CockroachDB cluster to initialize:
--
--   cockroach sql --url "$COCKROACHDB_CONNECTION_STRING" < backend/db/schema.sql
--
-- Notes:
--   • VECTOR(n) columns require CockroachDB with Distributed Vector Indexing.
--     Replace n with the exact embedding dimension from TECH_STACK.md once decided.
--     Placeholder: 1024 (Amazon Titan Embeddings v2 default) — CHANGE if model differs.
--   • All timestamps are TIMESTAMPTZ (timezone-aware) — never store naive datetimes.
--   • UUIDs use gen_random_uuid() as the default PK generator.

-- ─── Extensions ───────────────────────────────────────────────────────────────

-- Enable pgcrypto for gen_random_uuid() if not available natively
-- (CockroachDB has this built in; line is a no-op on modern versions)
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── projects ─────────────────────────────────────────────────────────────────
-- One row per software project the developer works on.
CREATE TABLE IF NOT EXISTS projects (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    repo_path   TEXT        NOT NULL,       -- absolute local filesystem path
    remote_url  TEXT,                        -- nullable git remote URL
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── sessions ─────────────────────────────────────────────────────────────────
-- One row per continuous work session on a project.
CREATE TABLE IF NOT EXISTS sessions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,                            -- NULL until session closes
    summary             TEXT,                                   -- generated end-of-session summary
    summary_embedding   VECTOR(1024)                            -- embedding of summary (dim TBD)
);

CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions (project_id);

-- ─── commits ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS commits (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id          UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    commit_hash         TEXT        NOT NULL,
    message             TEXT        NOT NULL,
    message_embedding   VECTOR(1024),
    author              TEXT        NOT NULL,
    committed_at        TIMESTAMPTZ NOT NULL,
    UNIQUE (project_id, commit_hash)            -- idempotent inserts
);

CREATE INDEX IF NOT EXISTS idx_commits_project_id ON commits (project_id);
CREATE INDEX IF NOT EXISTS idx_commits_committed_at ON commits (committed_at DESC);

-- ─── file_edits ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS file_edits (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id      UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    file_path       TEXT        NOT NULL,
    edited_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_summary  TEXT                                -- short description if generated
);

CREATE INDEX IF NOT EXISTS idx_file_edits_project_id ON file_edits (project_id);
CREATE INDEX IF NOT EXISTS idx_file_edits_edited_at  ON file_edits (edited_at DESC);

-- ─── terminal_commands ────────────────────────────────────────────────────────
-- IMPORTANT: commands must pass through secret redaction before INSERT.
-- See SKILLS.md §6, §8.
-- Consider a rolling retention policy (e.g. DELETE WHERE run_at < now() - INTERVAL '90 days')
-- to prevent unbounded growth — see DATABASE_SCHEMA.md §4.
CREATE TABLE IF NOT EXISTS terminal_commands (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_id  UUID        REFERENCES sessions(id) ON DELETE SET NULL,
    command     TEXT        NOT NULL,           -- redacted before storage
    cwd         TEXT        NOT NULL,
    exit_code   INT,                            -- nullable if capture missed it
    run_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_terminal_commands_project_id ON terminal_commands (project_id);

-- ─── todos ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS todos (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    description             TEXT        NOT NULL,
    description_embedding   VECTOR(1024),
    status                  TEXT        NOT NULL DEFAULT 'pending'
                                        CHECK (status IN ('pending', 'in_progress', 'done')),
    source                  TEXT        NOT NULL
                                        CHECK (source IN ('code_comment', 'manual', 'agent_generated')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at             TIMESTAMPTZ                         -- NULL until resolved
);

CREATE INDEX IF NOT EXISTS idx_todos_project_id ON todos (project_id);
CREATE INDEX IF NOT EXISTS idx_todos_status     ON todos (status);

-- ─── architecture_notes ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS architecture_notes (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title               TEXT        NOT NULL,
    content             TEXT        NOT NULL,
    content_embedding   VECTOR(1024),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_arch_notes_project_id ON architecture_notes (project_id);

-- ─── daily_briefs ─────────────────────────────────────────────────────────────
-- One row per project per day — powers the "Good Morning" screen.
CREATE TABLE IF NOT EXISTS daily_briefs (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    brief_date        DATE        NOT NULL,
    commits_count     INT         NOT NULL DEFAULT 0,
    highlights        TEXT[],                         -- short bullet list
    pending_items     TEXT[],
    last_edited_file  TEXT,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, brief_date)                   -- one brief per project per day
);

-- ─── taste_preferences ────────────────────────────────────────────────────────
-- Developer preference learning — scoped to DEVELOPER, not project.
-- See SKILLS.md §7, ARCHITECTURE.md §9.
CREATE TABLE IF NOT EXISTS taste_preferences (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id            UUID        NOT NULL,   -- scope: developer across all projects
    category                TEXT        NOT NULL,   -- e.g. 'naming_convention', 'commit_style'
    description             TEXT        NOT NULL,
    description_embedding   VECTOR(1024),
    confidence              FLOAT       NOT NULL DEFAULT 0.0
                                        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    evidence_count          INT         NOT NULL DEFAULT 1,
    last_observed_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_taste_developer_id ON taste_preferences (developer_id);

-- ─── credential_refs ──────────────────────────────────────────────────────────
-- NEVER stores secret values — only OS credential manager lookup keys.
-- See SKILLS.md §8, ARCHITECTURE.md §8.
CREATE TABLE IF NOT EXISTS credential_refs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID        REFERENCES projects(id) ON DELETE CASCADE, -- nullable (global creds)
    ref_name        TEXT        NOT NULL,   -- lookup key in OS credential manager
    purpose         TEXT        NOT NULL,   -- e.g. 'GitHub PAT', 'Bedrock-adjacent service key'
    expires_at      TIMESTAMPTZ,            -- nullable, only if known
    last_used_at    TIMESTAMPTZ
);

-- ─── decision_log ─────────────────────────────────────────────────────────────
-- Why decisions were made, not just what was decided. See SKILLS.md §9.
CREATE TABLE IF NOT EXISTS decision_log (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID        REFERENCES projects(id) ON DELETE SET NULL, -- nullable
    decision                TEXT        NOT NULL,
    rationale               TEXT        NOT NULL,   -- 2–5 sentences: alternatives + reasoning
    rationale_embedding     VECTOR(1024),
    decided_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── mistake_log ──────────────────────────────────────────────────────────────
-- Recurring-mistake prevention. See SKILLS.md §10.
CREATE TABLE IF NOT EXISTS mistake_log (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID        REFERENCES projects(id) ON DELETE SET NULL,
    symptom                 TEXT        NOT NULL,
    root_cause              TEXT        NOT NULL,
    fix                     TEXT        NOT NULL,
    root_cause_embedding    VECTOR(1024),
    module                  TEXT,           -- e.g. 'memory_manager', 'automation_layer'
    occurred_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
