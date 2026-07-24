# ARCHITECTURE.md

> **Naming note:** AUTOMATA is an *agent*, not an assistant with a
> database bolted on. Components are named to reflect that:
> - "Memory Manager" → **Persistent Memory Engine**
> - "AI Engine" → **Reasoning Engine**
> - New: **Decision Engine** (drives autonomous, unsolicited action)
>
> Underlying code folders keep their original short names for stability
> (`backend/memory/`, `backend/ai/`, `backend/automation/` — see
> `CONVENTIONS.md` §1). Docs and UI/demo language use the renamed terms
> above; comments in code should reference both on first use so agents
> reading the repo don't get confused by the naming shift.

## 1. High-level diagram

```
                     React + Tauri Desktop (UI)
                              │
                              ▼
                 Python Background Agent (core)
        ┌───────────────────┼───────────────────────┐
        ▼                   ▼                       ▼
  Automation Layer   Persistent Memory Engine   Reasoning Engine
  (OS orchestration)   (CockroachDB client)     (Bedrock client)
        │                   │                       │
   OS-native APIs     CockroachDB                Amazon Bedrock
   (chosen primary OS) (tables + vector index)   (LLM reasoning)
        │                   │
        └────── Managed MCP Server + Vector Search ─┘
                              │
                              ▼
                       Decision Engine
              (Observe → Reason → Plan → Act loop —
               see §2 "Agent Loop")
```

## 2. Agent Loop

This is the section that makes AUTOMATA an agent rather than a chatbot
with a database. Every meaningful interaction — whether user-triggered or
autonomously triggered by the Decision Engine — runs this cycle:

```
        ┌─────────────────────────────────────────────┐
        │                                               │
        ▼                                               │
   1. Observe  ──▶  2. Store Memory  ──▶  3. Reason      │
   (capture real     (CockroachDB,        (Bedrock,      │
    dev activity)     structured +        grounded in    │
                       embeddings)         retrieved       │
                                            memory)         │
                              │                             │
                              ▼                             │
                        4. Plan                             │
                   (decide next step —                      │
                    answer, suggestion,                     │
                    or autonomous action)                   │
                              │                              │
                              ▼                              │
                        5. Execute                           │
                  (answer the user, restore                  │
                   a workspace, draft a commit                │
                   message, run an Agent Action)               │
                              │                                 │
                              ▼                                 │
                    6. Update Memory  ─────────────────────────┘
                (log the outcome of the action —
                 e.g. "restored workspace at 9:03am" —
                 so the next cycle has it too)
                              │
                              ▼
                         7. Repeat
```

- **Observe** — file watcher, git hooks, terminal capture (Persistent
  Memory Engine, §3 below).
- **Store Memory** — structured rows + embeddings written to CockroachDB.
- **Reason** — Reasoning Engine (Bedrock) reasons over retrieved memory,
  never inventing facts for factual questions (`SKILLS.md` §5).
- **Plan** — decide what happens next: this is what separates AUTOMATA
  from pure retrieval — a plan can be "answer the question" or it can be
  "also flag two related TODOs and suggest continuing them," even
  unprompted (see Decision Engine, §2.3).
- **Execute** — the Automation Layer or a direct response carries the
  plan out.
- **Update Memory** — every action's outcome becomes new memory, closing
  the loop.

### 2.1 Memory Lifecycle

A single piece of developer activity flows through this pipeline from
raw event to acted-upon knowledge:

```
Developer Activity
      │
      ▼
Memory Capture           (Persistent Memory Engine observes)
      │
      ▼
Embedding Generation      (semantically rich content only)
      │
      ▼
CockroachDB Storage       (structured row + vector column)
      │
      ▼
Vector Index              (CockroachDB Distributed Vector Indexing)
      │
      ▼
Retrieval                 (query-time vector search + filters)
      │
      ▼
Reasoning (Bedrock)       (Reasoning Engine grounds an answer/plan)
      │
      ▼
Action                    (Execute step of the Agent Loop)
      │
      ▼
Memory Updated            (outcome logged — loop closes)
```

### 2.2 Memory types

AUTOMATA's memory isn't monolithic — different kinds of memory serve
different purposes in the loop:

```
Short-term Memory   → current session, in-process/RAM state
                       (active file watcher state, in-flight query context)

Long-term Memory    → CockroachDB structured tables
                       (projects, sessions, commits, TODOs, credential_refs)

Semantic Memory     → CockroachDB Vector Index
                       (embeddings over README, commit messages, TODOs,
                        architecture notes, taste/decision/mistake logs)

Reasoning           → Amazon Bedrock
                       (composes retrieved short/long/semantic memory
                        into a grounded answer or plan)
```

Short-term memory never persists past process restart by design — if it
needs to survive a restart, it belongs in CockroachDB, not RAM.

### 2.3 Decision Engine — autonomous, unsolicited action

See `PROJECT.md` §9 for the full feature description and guardrails. In
architectural terms: the Decision Engine subscribes to a small, explicit
set of triggers (e.g. "on commit," "on session end") and runs the Agent
Loop *without* a user prompt initiating it. It reuses the same Persistent
Memory Engine and Reasoning Engine as user-triggered queries — it is not
a separate reasoning path, just a different entry point into the same
loop, so behavior stays consistent and auditable.

## 3. Components

### 3.1 Frontend — React + Tauri desktop app
- Renders the morning brief, chat/query interface, restore button, and
  status indicators.
- Talks to the Python Background Agent over a local IPC/HTTP channel
  (Tauri sidecar process or localhost API — decide and record the choice
  in `TECH_STACK.md`).
- No business logic lives here. It is a thin presentation layer.

### 3.2 Python Background Agent — the core
Three responsibilities, three internal modules:

**a) Persistent Memory Engine** (code: `backend/memory/`)
- Watches the active project (file system watcher + git hooks) and writes
  structured events to CockroachDB.
- Generates embeddings for semantically searchable content (README,
  commit messages, TODOs, architecture notes, session summaries) and
  stores them via CockroachDB's vector index.
- Exposes a query interface: given a natural-language question, returns
  the most relevant stored memories (vector search + optional metadata
  filters like project/date range).

**b) Reasoning Engine** (code: `backend/ai/`)
- Wraps Amazon Bedrock calls.
- Takes retrieved memories + the user's question/command and produces:
  answers, summaries, commit messages, next-task suggestions.
- Never invents facts not present in retrieved memory for factual
  questions ("what did I do yesterday") — reasoning is grounded in
  retrieval, not free generation. Free generation is fine for creative
  tasks (e.g., drafting a commit message) but should be clearly labeled
  as generated, not presented as recalled fact.

**c) Automation Layer** (code: `backend/automation/`)
- Executes OS-level actions: launch/close terminal, checkout git branch,
  start/stop dev servers, optionally launch editor/browser.
- Isolated behind a small internal API (e.g. `restore_workspace()`,
  `start_dev_servers()`, `open_editor()`) so it can be mocked/stubbed for
  testing without touching the real OS.
- Built against ONE primary OS first (see §5). Cross-platform support is
  a stretch goal, not a dependency for the core memory story.

### 3.3 CockroachDB — persistent memory store
- System of record for all project memory.
- Stores both structured rows (commits, TODOs, sessions, metadata) and
  vector embeddings for semantic search.
- See `DATABASE_SCHEMA.md` for exact tables.

### 3.4 Amazon Bedrock — reasoning
- Used only for reasoning over retrieved memory and for generation tasks
  (summaries, commit messages, next-step suggestions).
- Model choice, prompt templates, and routing (if using LiteLLM) are
  documented in `TECH_STACK.md`.

### 3.5 Amazon S3 (optional)
- Only if screenshots/logs need persistent binary storage. Not required
  for the core memory/retrieval story — treat as a stretch feature.

## 4. Data flow — capture path

```
Dev activity (git commit, file save, terminal command)
      → File watcher / git hook fires
      → Persistent Memory Engine normalizes event
      → Structured row written to CockroachDB
      → If content is semantically rich (README, commit msg, TODO,
        architecture note) → generate embedding → store in vector index
```

## 5. Data flow — retrieval path

```
User asks a question ("what was I working on yesterday?")
      → Reasoning Engine embeds the query
      → Persistent Memory Engine runs vector search (+ metadata filters:
        project, date range) against CockroachDB
      → Top-k relevant memories returned
      → Reasoning Engine (Bedrock) composes a grounded answer from those
        memories
      → Answer returned to Frontend
```

## 6. OS strategy decision

> **Primary OS for automation/demo: Windows**
> Rationale: The dev and demo machine is Windows. Using Windows-native APIs
> (Windows Credential Manager, PowerShell, Win32 process control) for the
> Automation Layer gives the most reliable, single-OS path to a working demo
> under a hard hackathon deadline. Cross-OS parity is explicitly out of scope
> for the MVP (`PROJECT.md` §6). Code lives in `backend/automation/os_windows.py`.

Automation code should be written behind an interface so a second OS can
be added later without touching Persistent Memory Engine or Reasoning Engine code.

## 7. MCP usage — decided

**AUTOMATA consumes the CockroachDB Managed MCP Server** to securely
retrieve and manage persistent developer memory. AUTOMATA does not expose
its own MCP server in the MVP — it is an MCP *client* of CockroachDB's
managed tooling, not an MCP *server* for third parties.

State this explicitly in the demo narration in these exact terms — judges
familiar with MCP will ask, and "consumes CockroachDB's Managed MCP
Server for secure memory retrieval" is a precise, defensible answer.

(If a future phase adds a use case for exposing AUTOMATA's own memory to
external MCP clients, that would be a deliberate, separate addition —
not an ambiguity to resolve later. Record any such decision here with
rationale, per `SKILLS.md` §9, Decision Rationale Memory Skill.)

## 8. Credentials architecture (see `SKILLS.md` §8 for full playbook)

- CockroachDB stores only `credential_refs` rows (labels/metadata) — never
  secret values.
- Real secrets live in the OS-native credential store (Windows Credential
  Manager / macOS Keychain / equivalent) and are resolved by the
  Automation Layer just-in-time, in memory only.
- Any captured terminal command, diff, or log passes through a redaction
  step before it is written to CockroachDB or sent to Bedrock.

## 9. Taste memory as a distinct track (see `SKILLS.md` §7)

- Taste memory (`taste_preferences`) is scoped to the **developer**, not
  the project — it should generalize across projects the developer works
  on, unlike project event memory which is strictly `project_id`-scoped.
- The Reasoning Engine should treat taste memory as a *soft* input that shapes
  tone/style/structure of generated output, separate from the *grounded*
  factual retrieval used for "what happened" questions. Never let taste
  preference override a correctness concern silently — surface the
  tension instead.

## 10. Failure isolation

- Automation Layer failures (e.g., can't launch VS Code) must never crash
  the Persistent Memory Engine or Reasoning Engine. Wrap OS calls, log failures, degrade
  gracefully with a clear UI message.
- If Bedrock is unreachable, Persistent Memory Engine retrieval should still work
  and return raw memories with a "reasoning unavailable" note rather than
  failing entirely.
