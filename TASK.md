# TASK.md - AUTOMATA Implementation Tasks

> This document is the execution plan for AUTOMATA.
>
> Unlike `ROADMAP.md`, which describes the project timeline and milestones,
> `TASKS.md` contains implementation-level tasks that AI coding agents and
> developers should complete one at a time.
>
> **Rules**
>
> * Complete tasks in numerical order unless dependencies specify otherwise.
> * Do **not** skip tasks.
> * Update the status after completion.
> * If implementation changes architecture, database schema, or tech stack,
>   update the relevant documentation in the same commit.
> * Every completed task must satisfy its acceptance criteria.
> * If a task cannot be completed because of a blocker, mark it as **Blocked**
>   and describe why.

---

# Status Legend

| Status         | Meaning                                      |
| -------------- | -------------------------------------------- |
| ⬜ Pending      | Not started                                  |
| 🟨 In Progress | Currently being implemented                  |
| ✅ Completed    | Finished and verified                        |
| 🚫 Blocked     | Cannot continue until dependency is resolved |

---

# Phase 0 — Repository Foundation

---

## TASK-001

### Title

Create project folder structure

### Status

Completed

### Depends On

None

### Files

* frontend/
* backend/
* scripts/
* demo/

### Acceptance Criteria

* Folder structure matches `CONVENTIONS.md`
* Repository builds without missing directories

---

## TASK-002

### Title

Initialize frontend

### Status

In Progress

### Depends On

TASK-001

### Files

frontend/

### Acceptance Criteria

* React project created
* Tauri integrated (`frontend/src-tauri/` is not present yet)
* Tailwind configured
* Development server starts successfully

---

## TASK-003

### Title

Initialize backend

### Status

Completed

### Depends On

TASK-001

### Files

backend/

### Acceptance Criteria

* Python project initialized
* Virtual environment configured
* FastAPI starts successfully
* Logging configured

---

## TASK-004

### Title

Create configuration system

### Status

Completed

### Depends On

TASK-003

### Files

backend/config.py

### Acceptance Criteria

* Environment variables loaded
* Missing variables handled gracefully
* Configuration available globally

---

# Phase 1 — Persistent Memory Engine

---

## TASK-005

### Title

Connect CockroachDB

### Status

✅ Completed

### Depends On

TASK-004

### Acceptance Criteria

* Database connection established
* Connection retry implemented
* Health check endpoint available

---

## TASK-006

Create database schema

Status

✅ Completed

Depends On

TASK-005

Files

backend/db/schema.sql

Acceptance

* Tables created
* Indexes created
* Matches DATABASE_SCHEMA.md

---

## TASK-007

Implement database client

Status

✅ Completed

Depends On

TASK-006

Files

backend/db/client.py

Acceptance

* CRUD methods
* Transactions
* Error handling

---

## TASK-008

Implement project tracking

Status

✅ Completed

Depends On

TASK-007

Files

backend/db/client.py, backend/api/server.py

Acceptance

* Projects stored
* Existing projects detected
* Metadata retrieved

---

## TASK-009

Implement session tracking

Status

✅ Completed

Depends On

TASK-008

Files

backend/db/client.py

Acceptance

* Session start
* Session end
* Duration recorded

---

## TASK-010

Implement file watcher

Status

✅ Completed

Depends On

TASK-009

Files

backend/memory/capture.py

Acceptance

* File changes detected
* Duplicate events filtered
* Events stored

---

## TASK-011

Implement Git monitoring

Status

✅ Completed

Depends On

TASK-010

Files

backend/memory/capture.py

Acceptance

* Branch detected
* Commits captured
* Commit metadata stored

---

## TASK-012

Implement terminal capture

Status

✅ Completed

Depends On

TASK-011

Files

backend/memory/capture.py

Acceptance

* Commands captured
* Sensitive data redacted (`redact_secrets()` implemented; capture path still pending)
* Commands stored

---

## TASK-013

Implement TODO extraction

Status

✅ Completed

Depends On

TASK-012

Files

backend/db/client.py

Acceptance

* TODO comments detected
* Manual TODO creation
* Stored in database

---

## TASK-014

Implement architecture notes

Status

✅ Completed

Depends On

TASK-013

Files

backend/db/client.py

Acceptance

* Architecture notes stored
* Retrieval works

---

# Phase 2 — Vector Memory

---

## TASK-015

Embedding generation pipeline

### Status

✅ Completed

### Files

backend/ai/bedrock_client.py

### Acceptance Criteria

* Embedding calls wired through invoke_embedding() (Done)
* Multiple provider support (Groq, Gemini, NVIDIA, Minimax, Ollama) (Done)
* Fallback chain implemented (Done)

---

## TASK-016

Vector storage

### Status

✅ Completed

### Files

backend/db/client.py, backend/db/schema.sql

### Acceptance Criteria

* All tables have *_embedding columns (Done)
* Embedding generation called on insert (Done)

---

## TASK-017

Vector retrieval

### Status

✅ Completed

### Files

backend/memory/retrieval.py

### Acceptance Criteria

* retrieve_by_vector() implemented (Done)
* CockroachDB ANN search working (Done)

---

## TASK-018

Semantic search

### Status

✅ Completed

### Files

backend/ai/bedrock_client.py, backend/memory/retrieval.py

### Acceptance Criteria

* Natural language queries work (Done)
* Results ranked by similarity (Done)

---

## TASK-019

Memory ranking

### Status

✅ Completed

### Files

backend/memory/retrieval.py

### Acceptance Criteria

* Results sorted by score (Done)

---

## TASK-020

Natural language memory queries

### Status

✅ Completed

### Files

backend/memory/retrieval.py

### Acceptance Criteria

* Query text embedded and searched (Done)

# Phase 3 — Reasoning Engine

---

## TASK-021

Amazon Bedrock integration

### Status

✅ Completed

### Files

backend/ai/bedrock_client.py

### Acceptance Criteria

* _invoke_bedrock_chat implemented (Done)
* invoke_reasoning uses Bedrock as primary (Done)

---

## TASK-022

Prompt management

### Status

✅ Completed

### Files

backend/ai/bedrock_client.py

### Acceptance Criteria

* _build_grounded_prompt implemented (Done)
* Memories included in prompts (Done)

---

## TASK-023

Grounded response generation

### Status

✅ Completed

### Files

backend/ai/bedrock_client.py

### Acceptance Criteria

* invoke_reasoning returns grounded answers (Done)
* Retrieval integrated with reasoning (Done)

---

## TASK-024

Morning Brief generation

### Status

🟨 In Progress

### Files

backend/ai/bedrock_client.py, frontend/src/screens/MorningBrief.tsx

### Acceptance Criteria

* Brief prompt template (pending)
* Frontend displays brief (Done)

---

## TASK-025

Next-task suggestion

### Status

🟨 In Progress

### Files

backend/ai/bedrock_client.py

### Acceptance Criteria

* Next-task prompt template (pending)
* TODO-based suggestions (partially done)

# Phase 4 — Automation Layer

---

## TASK-026

Workspace detection

### Status

✅ Completed

### Files

backend/automation/restore.py

### Acceptance Criteria

* Project info retrieved (Done)
* Repo path determined (Done)

---

## TASK-027

Git restoration

### Status

✅ Completed

### Files

backend/automation/restore.py, backend/automation/os_windows.py

### Acceptance Criteria

* Git branch checkout works (Done)
* Uses GitPython for repo access (Done)

---

## TASK-028

Terminal restoration

### Status

✅ Completed

### Files

backend/automation/restore.py, backend/automation/os_windows.py

### Acceptance Criteria

* Terminal opens to repo path (Done)

---

## TASK-029

Development server startup

### Status

🟨 In Progress

### Files

backend/automation/dev_servers.py

### Acceptance Criteria

* Server config schema ready (Done)
* Start/stop endpoints (pending)

---

## TASK-030

Editor launch

### Status

✅ Completed

### Files

backend/automation/restore.py, backend/automation/os_windows.py

### Acceptance Criteria

* VS Code launch implemented (Done)

---

## TASK-031

Browser launch

### Status

🟨 In Progress

### Files

backend/automation/restore.py, backend/automation/os_windows.py

### Acceptance Criteria

* Launch browser endpoint exists (Done)
* URL configuration (pending)

---

## TASK-032

Complete workspace recovery

### Status

🟨 In Progress

### Files

backend/automation/restore.py

### Acceptance Criteria

* All steps integrated (partially done)

# Phase 5 — Decision Engine

---

## TASK-033

Trigger detection

---

## TASK-034

Planning engine

---

## TASK-035

Decision execution

---

## TASK-036

Memory updates after actions

---

## TASK-037

Provenance logging

---

# Phase 6 — User Interface

---

## TASK-038

Dashboard

---

## TASK-039

Morning Brief UI

---

## TASK-040

Workspace Recovery UI

---

## TASK-041

Agent Chat UI

---

## TASK-042

Memory Timeline UI

---

## TASK-043

Settings UI

---

# Phase 7 — Agent Actions

---

## TASK-044

Explain repository

---

## TASK-045

Generate commit message

---

## TASK-046

Find authentication implementation

---

## TASK-047

Continue previous work

---

## TASK-048

Generate project summary

---

# Phase 8 — Testing

---

## TASK-049

Backend tests

---

## TASK-050

Frontend tests

---

## TASK-051

Integration tests

---

## TASK-052

Automation tests

---

## TASK-053

Memory retrieval tests

---

# Phase 9 — Polish

---

## TASK-054

Performance optimization

---

## TASK-055

Error handling

---

## TASK-056

Loading states

---

## TASK-057

Documentation review

---

## TASK-058

Demo preparation

---

## TASK-059

Hackathon rehearsal

---

## TASK-060

Submission ready

---

# Completion Checklist

Before marking AUTOMATA complete, verify:

* [ ] All tasks completed
* [ ] All acceptance criteria satisfied
* [ ] Documentation updated
* [ ] Demo recorded
* [ ] README reviewed
* [ ] ROADMAP updated
* [ ] PROJECT matches implementation
* [ ] DATABASE_SCHEMA matches implementation
* [ ] ARCHITECTURE matches implementation
* [ ] Final repository review completed
