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

⬜ Pending

### Depends On

TASK-004

### Acceptance Criteria

* Database connection established
* Connection retry implemented
* Health check endpoint available

---

## TASK-006

Create database schema

Depends On

TASK-005

Acceptance

* Tables created
* Indexes created
* Matches DATABASE_SCHEMA.md

---

## TASK-007

Implement database client

Depends On

TASK-006

Acceptance

* CRUD methods
* Transactions
* Error handling

---

## TASK-008

Implement project tracking

Depends On

TASK-007

Acceptance

* Projects stored
* Existing projects detected
* Metadata retrieved

---

## TASK-009

Implement session tracking

Depends On

TASK-008

Acceptance

* Session start
* Session end
* Duration recorded

---

## TASK-010

Implement file watcher

Depends On

TASK-009

Acceptance

* File changes detected
* Duplicate events filtered
* Events stored

---

## TASK-011

Implement Git monitoring

Depends On

TASK-010

Acceptance

* Branch detected
* Commits captured
* Commit metadata stored

---

## TASK-012

Implement terminal capture

Depends On

TASK-011

Acceptance

* Commands captured
* Sensitive data redacted
* Commands stored

---

## TASK-013

Implement TODO extraction

Depends On

TASK-012

Acceptance

* TODO comments detected
* Manual TODO creation
* Stored in database

---

## TASK-014

Implement architecture notes

Depends On

TASK-013

Acceptance

* Architecture notes stored
* Retrieval works

---

# Phase 2 — Vector Memory

---

## TASK-015

Embedding generation pipeline

---

## TASK-016

Vector storage

---

## TASK-017

Vector retrieval

---

## TASK-018

Semantic search

---

## TASK-019

Memory ranking

---

## TASK-020

Natural language memory queries

---

# Phase 3 — Reasoning Engine

---

## TASK-021

Amazon Bedrock integration

---

## TASK-022

Prompt management

---

## TASK-023

Grounded response generation

---

## TASK-024

Morning Brief generation

---

## TASK-025

Next-task suggestion

---

# Phase 4 — Automation Layer

---

## TASK-026

Workspace detection

---

## TASK-027

Git restoration

---

## TASK-028

Terminal restoration

---

## TASK-029

Development server startup

---

## TASK-030

Editor launch

---

## TASK-031

Browser launch

---

## TASK-032

Complete workspace recovery

---

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
