# PROJECT.md — AUTOMATA: A Persistent Memory Developer Agent

> Internal codename: DevOS AI. Use **AUTOMATA** as the project's public
> name everywhere else (submission title, UI, docs) — it's shorter,
> memorable, and signals "autonomous agent" rather than "assistant tool,"
> which matches an Agentic Applications hackathon theme better.

## 1. One-line pitch

An autonomous developer agent that observes, remembers, reasons, plans,
and acts on a developer's workflow — using **CockroachDB as persistent
memory** and **Amazon Bedrock as its reasoning engine** — so context
survives sessions, restarts, and time, not just the current chat window.

## 2. Why this matters

Today's coding assistants remember only the current conversation. Close
the tab, and the context is gone.

AUTOMATA remembers projects — weeks later, months later, across sessions,
across machines, across workflows. That's a fundamentally different
product category from a chatbot with a longer context window: it's an
agent with real, structured, queryable memory that persists independent
of any single conversation.

## 3. Problem

Every dev tool with "AI assistance" today forgets you the moment you close
the tab. Developers re-explain project context every session: what they were
doing, what's pending, what broke, what the architecture looks like. This
is wasted cognitive overhead that compounds across weeks of a project.

## 4. Solution — the agent loop

AUTOMATA isn't a chatbot with a database attached. It runs a continuous
agent loop:

```
Observe → Store Memory → Reason → Plan → Execute → Update Memory → Repeat
```

- **Observe** — watches git activity, file edits, terminal commands, TODOs.
- **Store Memory** — persists structured facts + embeddings to CockroachDB.
- **Reason** — cloud APIs such as Groq and Gemini are attempted first to avoid
   local model downloads and RAM usage. AWS Bedrock is used next when configured,
   and Ollama is only used as a last-resort local fallback when the cloud providers
   and Bedrock are unavailable or fail (see `backend/ai/bedrock_client.py`).
- **Plan** — decides what the developer probably needs next (not just
  what they asked for).
- **Execute** — takes action: restores a workspace, drafts a commit
  message, surfaces a next task.
- **Update Memory** — writes the outcome of that action back into memory
  so the next cycle has it too.

See `ARCHITECTURE.md` §"Agent Loop" for the full technical version of this
cycle, and §"Memory Lifecycle" for how a single piece of developer activity
flows all the way from capture to action.

## 5. Agent capabilities

Seven capabilities define AUTOMATA as an agent, not a tool:

**Observe · Remember · Retrieve · Reason · Plan · Act · Learn**

- *Observe* — continuous capture of real developer activity.
- *Remember* — persistent, structured storage in CockroachDB.
- *Retrieve* — semantic vector search over that memory.
- *Reason* — Bedrock grounds answers and decisions in retrieved memory.
- *Plan* — proposes a next step, not just an answer to the literal question.
- *Act* — executes real workspace/workflow actions, not just chat replies.
- *Learn* — taste memory, decision rationale, and mistake memory (see
  `SKILLS.md` §§7, 9, 10) mean the agent's behavior improves over time,
  not just its dataset.

## 6. Non-goals (explicitly out of scope for MVP)

- Not a general-purpose assistant / "Jarvis" — scope is developer workflow
  memory and agentic action only.
- Not a replacement for the developer's IDE or terminal — it orchestrates
  them, it doesn't replace them.
- Not multi-user / team features in the MVP — single developer, single
  machine, one or more local projects.
- Not guaranteeing cross-OS parity in the MVP — pick ONE primary OS for the
  automation layer (see `ARCHITECTURE.md` §6) and make that flawless.
- Autonomous proactive actions (see §9, Autonomous Decision Engine) stay
  narrow and reversible in the MVP — the agent proposes/acts on a small,
  well-tested set of triggers, it does not attempt general-purpose
  unsupervised decision-making.

## 7. The demo story (what judges/users should feel)

**Day 1** — Developer works on a project ("Eco-DPI"). In the background,
AUTOMATA silently observes and logs: project name, git branch, commits,
README, folder structure, TODOs, edited files, terminal commands, and an
architecture summary, plus an end-of-day summary.

**Day 2** — Developer opens their laptop. AUTOMATA doesn't just recall —
it reasons and plans:

```
Good Morning!
Yesterday you solved JWT authentication.
Today I found two related TODOs.

• 3 commits
• Authentication module completed
• Dashboard API pending
• Last edited: authController.js

Would you like me to restore the project and continue?
```

One click triggers **Autonomous Workspace Recovery**: git branch, terminal,
backend/frontend dev servers, and (if feasible) editor/browser.

Developer then says: **"Continue dashboard development."**
AUTOMATA retrieves relevant memories from CockroachDB (via vector search),
reasons over them with Bedrock, and picks the thread back up with real,
specific context — not generic chatbot filler, and not just an answer, but
a proposed next step.

## 8. Core features (priority order — see ROADMAP.md for sequencing)

1. **Persistent Developer Memory** (⭐ centerpiece) — project metadata, git
   history, TODOs, conversations, terminal history, session summaries,
   embeddings, architecture summaries — all in CockroachDB.
2. **Agent Memory Retrieval** — natural-language questions answered from
   real stored memory via CockroachDB vector search + Bedrock reasoning.
3. **Autonomous Workspace Recovery** — reopen project, restore git branch,
   start dev servers, restore terminal state, optionally open editor/
   browser — triggered by the agent's own plan, not just a manual command.
4. **Agent Actions** — commands like "resume project", "generate commit
   message", "explain repository", "find authentication code", "start dev
   environment".
5. **Autonomous Decision Engine** — see §9. The agent notices activity
   (e.g. a commit) and proactively acts without being asked: updates the
   project summary, regenerates the daily brief, flags related unfinished
   TODOs, stores the resulting memory, and surfaces a suggested next task.
   This is what makes AUTOMATA autonomous rather than reactive-only.
6. **Global Floating Companion & Cross-App Autonomous Execution** — system-wide overlay companion window accessible over any application via hotkey (e.g. `Alt+Space`). Capable of executing multi-step tasks across other desktop applications (IDE, browser, terminal, external tools, web creation) in the background while the developer works elsewhere.


## 9. Autonomous Decision Engine (the one feature that makes this "autonomous")

This is the feature that separates AUTOMATA from a smart retrieval tool:
the agent acts on its own initiative, not only on request.

**Example trigger:** the developer commits code. Nobody asks the agent to
do anything. The agent still:
1. Updates the project/architecture summary if the commit touched
   structure.
2. Regenerates the daily brief.
3. Detects unfinished TODOs related to what just changed (via vector
   search against `todos`).
4. Stores the resulting memory (per the Agent Loop).
5. Surfaces a suggested next task — surfaced passively (e.g. in the next
   brief), not as an interruptive popup.

**Guardrails (important — this is real scope, treat it carefully):**
- Triggers are a small, explicit, well-tested set for the MVP (e.g. "on
  commit," "on session end") — not a general-purpose autonomous loop
  reacting to arbitrary events.
- Every autonomous action is logged with provenance (`SKILLS.md` §10 —
  Provenance & Explainability Skill) so the developer can always see
  *why* the agent did something.
- Autonomous actions default to **suggest, not silently execute** for
  anything irreversible or environment-changing (e.g. it suggests
  restoring the workspace; it doesn't restore it unasked). Passive,
  reversible actions (updating a summary, flagging a TODO) can run fully
  autonomously.
- This is its own roadmap phase (`ROADMAP.md` — Autonomous Decision
  Engine), not something to bolt on in the last two days.

## 10. Hackathon technologies (explicit, not implied)

| Technology | Role in AUTOMATA |
|---|---|
| **CockroachDB** — Persistent Memory | System of record for all agent memory: project metadata, git history, TODOs, sessions, taste/decision/mistake memory. |
| **CockroachDB** — Distributed Vector Indexing | Powers semantic retrieval — the agent's ability to find relevant memory by meaning, not keyword. |
| **CockroachDB** — Managed MCP Server | AUTOMATA **consumes** the CockroachDB Managed MCP Server to securely retrieve and manage persistent developer memory. (Decided — see `ARCHITECTURE.md` §7.) |
| **Amazon Bedrock** | The agent's reasoning engine — grounds answers in retrieved memory and powers planning/generation. |
| **Amazon S3** (optional) | Stores screenshots/logs if the stretch scope needs binary artifact storage. |

**Why CockroachDB specifically:** a traditional database simply stores
data. CockroachDB becomes the long-term memory system for an autonomous
AI agent — ensuring context survives sessions, failures, and future
interactions, which is exactly what an agent needs to be trustworthy
across time rather than just within one conversation.

## 11. Why this fits the Agentic Applications hackathon theme

| Theme concept | AUTOMATA's answer |
|---|---|
| Agent | AUTOMATA's continuous Observe → Reason → Plan → Act loop (`ARCHITECTURE.md` §"Agent Loop") |
| Persistent Memory | CockroachDB (tables + distributed vector indexing) |
| Semantic Retrieval | CockroachDB vector search over embeddings |
| Production-grade memory infra | CockroachDB Managed MCP Server |
| Reasoning | Amazon Bedrock |
| Autonomous action | Autonomous Workspace Recovery + the Autonomous Decision Engine (§9) |

The story is: **memory is what makes an autonomous dev agent trustworthy
and useful across time** — not a bigger context window, not more chat
history, but real structured, queryable memory feeding a real agent loop.

## 12. Why AUTOMATA is an agent, not a chatbot

AUTOMATA continuously observes developer activity, stores it as
persistent memory in CockroachDB, retrieves relevant memories through
semantic search, reasons over them using Amazon Bedrock, plans the next
action, executes developer workflows, and updates its memory after every
interaction.

This Observe → Remember → Reason → Plan → Act → Learn cycle is what lets
AUTOMATA function as a true autonomous developer agent, rather than a
traditional AI chatbot with a database attached.

## 13. Demo flow for submission (target: ~3 minutes)

1. Start a project; AUTOMATA silently captures context live.
2. Close the app — simulate end of workday.
3. Reopen the app the next "day".
4. Show the morning brief pulling real memory from CockroachDB.
5. One-click restore of the dev environment.
6. Ask: "What did I finish yesterday?", "Find where JWT auth was
   implemented", "Generate my next task based on pending work."
7. Explicitly call out: this is **not** chat history — it's structured,
   persistent memory that survives sessions, machines, and time.

## 14. Success criteria for the MVP

- [ ] Memory capture pipeline reliably logs real project activity.
- [ ] Vector search retrieval returns correct, specific memories (not
      generic/hallucinated answers) for at least 5 distinct query types.
- [ ] Morning brief generates from real stored data, not hardcoded strings,
      and includes a proposed next step, not just a recap.
- [ ] Autonomous Workspace Recovery works reliably on the chosen primary OS.
- [ ] At least 3 Agent Actions work end-to-end.
- [ ] At least one Autonomous Decision Engine trigger (e.g. "on commit")
      works end-to-end with visible provenance for its action.
- [ ] A recorded fallback demo exists in case live automation fails.
