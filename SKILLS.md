# SKILLS.md — Required Playbooks for Agents Working on AUTOMATA

> Any agent (human or AI) working on this project should follow these
> playbooks instead of improvising. Each skill states: when to use it,
> the checklist to follow, and common failure modes to avoid.

---

## 1. Testing Skill

**When to use:** before marking any feature "done"; before every commit
touching `backend/` or `frontend/`.

**Checklist:**
- [ ] Unit tests for pure logic (embedding formatting, query construction,
      memory-row parsing) — no live DB or Bedrock calls in unit tests.
- [ ] Integration tests for Persistent Memory Engine ↔ CockroachDB using a local/test
      CockroachDB instance or container — never point tests at
      production-like data.
- [ ] Mock Bedrock responses for Reasoning Engine tests — don't burn real API
      calls in CI; keep one small "live smoke test" separate and manual.
- [ ] Automation Layer tests use a stubbed OS interface (see
      `ARCHITECTURE.md` §3.2c) — never actually launch apps/servers in CI.
- [ ] At least one end-to-end test per demo step in `PROJECT.md` §13, run
      manually before each milestone.
- [ ] Regression check: after any schema change, re-run retrieval tests
      to confirm vector search still returns expected top-k results.

**Common failure modes to avoid:**
- Tests that only check "no exception thrown" instead of checking the
  actual returned content is correct.
- Flaky tests due to real network calls (Bedrock/CockroachDB) — isolate
  with mocks/fixtures.
- Skipping retrieval-quality testing — a vector search that returns
  plausible-but-wrong memories is worse than one that visibly fails.

---

## 2. Bug-Fixing Skill

**When to use:** whenever something breaks, whether reported by a user or
found while building.

**Checklist:**
1. Reproduce first. Don't patch based on a guess — confirm the exact
   failure (error message, stack trace, or wrong output) before touching
   code.
2. Localize the failure to one module (Frontend / Persistent Memory Engine / AI
   Engine / Automation Layer / CockroachDB) using the module boundaries in
   `CONVENTIONS.md` §3 — don't shotgun-edit across modules.
3. Check for the class of bug before assuming it's novel:
   - Embedding dimension mismatch between write-time and query-time model.
   - Timezone/UTC handling bugs in `TIMESTAMPTZ` columns.
   - Race conditions between file watcher events and git hook events firing
     near-simultaneously.
   - OS automation failing silently (wrap and log per `ARCHITECTURE.md` §10).
4. Write a regression test that would have caught the bug, before or
   alongside the fix.
5. Update `ROADMAP.md`/`ARCHITECTURE.md` if the bug revealed a design gap,
   not just a code gap.

**Common failure modes to avoid:**
- "Fixing" a symptom (e.g., wrapping a crash in try/except with no
  logging) instead of the root cause.
- Silent failures in the Automation Layer — always surface a clear status
  to the UI, even if degraded.

---

## 3. Frontend Skill (React + Tauri)

**When to use:** building or modifying any UI screen.

**Checklist:**
- [ ] Frontend stays a thin layer — no memory logic, no direct DB/Bedrock
      calls (see `CONVENTIONS.md` §3).
- [ ] Loading and error states are explicit for every async action
      (morning brief loading, restore-in-progress, query-in-flight) — a
      hackathon demo with a silent frozen screen reads as broken.
- [ ] The "Restore workspace?" flow shows real-time progress per step
      (git checkout → terminal → servers → editor/browser) rather than a
      single opaque spinner — this materially improves the demo's
      perceived reliability.
- [ ] Consistent, distinctive visual identity — avoid generic
      "AI-startup-template" look (see `frontend-design` guidance if
      available); this is a judged product, first impressions matter.
- [ ] Accessibility basics: readable contrast, keyboard-navigable primary
      actions.

**Common failure modes to avoid:**
- Overloading the UI with every possible memory field — the morning brief
  should show a curated, human-readable summary, not a raw data dump.
- Coupling UI copy directly to raw DB field names.

---

## 4. Backend Skill (Python agent)

**When to use:** building or modifying Persistent Memory Engine, Reasoning Engine, or
Automation Layer code.

**Checklist:**
- [ ] Respect module boundaries (`CONVENTIONS.md` §3) strictly.
- [ ] All CockroachDB writes go through a single client module
      (`backend/db/client.py`) — no ad hoc connections scattered around.
- [ ] All Bedrock calls go through `backend/ai/bedrock_client.py` with
      centralized error handling, retries, and timeout limits.
- [ ] Long-running capture (file watcher, git hooks) must not block the
      local API server — run in background threads/processes.
- [ ] Redact obvious secrets (API keys, tokens, passwords) from any
      terminal command or file diff before writing to CockroachDB — see
      §6 below.
- [ ] Idempotent writes where possible — re-running a capture step
      shouldn't create duplicate rows for the same event.

**Common failure modes to avoid:**
- Blocking the whole agent process on a slow Bedrock call — always have a
  timeout and a graceful fallback (raw memories without AI summary).
- Storing full file contents when only a change summary is needed —
  bloats CockroachDB storage without adding retrieval value.

---

## 5. Prompt & Retrieval Quality Skill ("better results")

**When to use:** writing or tuning any Bedrock prompt; improving answer
quality for memory-retrieval queries.

**Checklist:**
- [ ] Ground factual answers strictly in retrieved memory — the prompt
      should explicitly instruct the model not to fabricate commits,
      files, or events not present in the retrieved context.
- [ ] Always pass retrieved memories with structure (which table/type
      each came from, and its timestamp) so the model can reason about
      recency and relevance rather than treating all context as equal.
- [ ] Use few-shot examples in prompts for structured outputs (e.g.
      morning brief bullets, commit message generation) so output format
      stays consistent across calls.
- [ ] For open-ended generation (commit messages, next-task suggestions),
      clearly separate "generated suggestion" from "recalled fact" in the
      UI copy — don't blur the line for the user.
- [ ] Log prompt + retrieved context + response for a sample of calls
      during development so retrieval quality can be manually audited —
      turn this off before the public demo (privacy) or store locally
      only.
- [ ] Iterate retrieval quality by testing at least 5 distinct query
      phrasings per intent (e.g. "what did I do yesterday", "recap
      yesterday's work", "summarize my last session") to make sure vector
      search generalizes, not just exact phrase matches from the demo
      script.

**Common failure modes to avoid:**
- Prompts that let the model "fill in" plausible-sounding details when
  retrieval returns nothing — should instead say "no memory found for
  that" rather than inventing content.
- Over-fitting prompts/retrieval tuning to the exact demo script phrases,
  which then breaks under any real judge question.

---

## 6. Removing AI Presence & Output Naturalness Skill

**When to use:** anywhere AUTOMATA produces user-facing text — morning
briefs, generated commit messages, summaries, chat answers — and
anywhere logs/commits/config are written that a judge or teammate might
read.

**Goal:** the product should feel like a sharp, quiet engineering tool,
not a chatbot performing "AI-ness."

**Checklist:**
- [ ] Strip generic chatbot filler from generated text: no "Certainly!",
      "I'd be happy to help!", "As an AI...", excessive exclamation
      points, or emoji-heavy output unless the product's UI voice
      explicitly calls for it.
- [ ] Morning briefs and summaries should read like a terse human
      standup update, not a model showing its reasoning — short, factual
      bullet points (see the format in `PROJECT.md` §7).
- [ ] Generated commit messages should follow normal human commit-message
      conventions (imperative mood, concise, no meta-commentary about
      being AI-generated) unless the user explicitly wants an
      "AI-generated" tag for transparency/audit purposes — that's a
      product decision, not a default.
- [ ] Avoid telltale over-hedging language ("It's important to note that
      ...", "It seems like ...") in factual memory answers — state what
      was retrieved plainly, and clearly flag genuine uncertainty instead
      of hedging by default.
- [ ] Data hygiene: redact secrets/tokens/passwords from any captured
      terminal command, diff, or log before it's stored or surfaced —
      this is both a security practice and prevents leaking sensitive
      data through generated summaries.
- [ ] Don't fabricate specificity to sound more "human" or more
      "confident" — naturalness is about tone and brevity, never about
      inventing details that weren't actually retrieved.

**Common failure modes to avoid:**
- Swinging too far and stripping useful nuance/uncertainty flags just to
  sound terse — clarity and honesty always outrank "sounding natural."
- Treating this skill as a green light to misrepresent AI involvement to
  end users in contexts where transparency is expected (e.g. don't claim
  a human wrote something a model generated, if the user's own product
  policy requires disclosure).

---

## 7. Taste Memory Skill (developer preference learning)

**When to use:** any time the agent generates code, suggests a next step,
or formats output for the developer. This is what makes AUTOMATA feel
like *your* agent rather than a generic one.

**What it is:** a distinct memory track from project memory. Project
memory answers "what happened." Taste memory answers "how does this
specific developer like things done." It should get its own table(s) —
see schema note below — not be mixed into `architecture_notes` or
`sessions`.

**What to capture:**
- Naming conventions actually used across the developer's own commits
  (e.g. consistently `camelCase` vs `snake_case`, verb-first function
  names, preferred file/folder naming).
- Commit message style (length, tense, whether they include ticket
  numbers, emoji use or lack thereof).
- Code structure preferences (early returns vs nested conditionals,
  comment density, preferred error-handling patterns) inferred from
  their own diffs — never from generic "best practice" defaults.
- Tool/library preferences when there's a real choice (e.g. always
  reaches for `date-fns` over `moment`, prefers `pytest` over
  `unittest`).
- Review/fix patterns: if the developer repeatedly edits the agent's
  suggestions the same way, that's a signal to update taste memory, not
  just a one-off correction.

**Checklist:**
- [ ] Derive taste signals from the developer's *own* historical commits/
      edits, not from asking them to fill out a preferences form up
      front — passive learning is the point.
- [ ] Weight recent behavior more than old behavior — taste drifts over
      time (a new project, a new team standard).
- [ ] Before applying a taste inference to generated output, keep the
      confidence bar reasonably high — one instance is a coincidence,
      a consistent pattern across many commits is a preference.
- [ ] Never let taste memory override explicit instructions in the
      moment — if the developer explicitly asks for something different
      this time, that wins over inferred preference.
- [ ] Surface *what* preference was applied when it materially changed
      output (e.g. a small "matched your usual commit style" note),
      so it doesn't feel like invisible magic that's hard to trust or
      debug.

**Common failure modes to avoid:**
- Treating a single stylistic choice as a fixed rule forever — allow it
  to update as new evidence comes in.
- Conflating "taste" with "correctness" — a taste preference should never
  cause the agent to skip an actual bug fix or best practice it disagrees
  with; flag the tension instead of silently picking one.

---

## 8. Credentials & Secrets Handling Skill

**When to use:** any time AUTOMATA needs to store, retrieve, or use a
credential — API keys, DB connection strings, git tokens, cloud creds —
to support workspace restoration or automation.

**Core rule: CockroachDB never stores secret material.** CockroachDB is
for memory (facts, embeddings, summaries), not for the vault. Credentials
belong in the OS-native secure store.

**Checklist:**
- [ ] Store actual secrets in the OS-native credential manager: Windows
      Credential Manager (primary OS per `ARCHITECTURE.md` §6), macOS
      Keychain, or a local encrypted vault (e.g. `keyring` Python library)
      — never in a CockroachDB row, a `.md` file, a log, or plain JSON on
      disk.
- [ ] What CockroachDB *is* allowed to store: a reference/label only —
      e.g. `credential_ref: "eco-dpi-github-token"` — never the value
      itself. The Automation Layer resolves the reference to a real
      secret at the moment it's needed, in memory only.
- [ ] Redact secret-shaped strings (tokens, keys, passwords) out of
      captured `terminal_commands`, `file_edits` diffs, and any Bedrock
      prompt/logging before persistence — pattern-match common formats
      (e.g. `ghp_`, `AKIA`, `sk-`, generic `key=`/`token=` patterns) and
      mask them, per the data hygiene note in the Output Naturalness
      skill.
- [ ] Never send raw credential values to Bedrock as part of a prompt —
      if a captured command happens to contain one, it must already be
      redacted before it ever reaches the Reasoning Engine.
- [ ] Workspace restoration that needs a credential (e.g. starting a dev
      server that needs an API key) should resolve it just-in-time from
      the OS vault and never write it into a restored terminal's scrollback
      or a log file.
- [ ] Rotation/expiry awareness: if a stored credential reference has a
      known expiry (e.g. a short-lived token), surface that status in the
      restore flow ("this token may be expired — re-authenticate?")
      rather than failing silently mid-restore.
- [ ] `.env` files and any local secret files stay out of git — confirm
      `.gitignore` covers them (see `SETUP.md` §3) and never let an agent
      commit one, even accidentally, during automated changes.

**Common failure modes to avoid:**
- "Just for the demo" shortcuts that put a real key in a config file,
  a doc, or a commit — this is exactly the kind of thing that gets
  forgotten and shipped.
- Logging full request/response payloads for debugging without checking
  they don't contain secret values first.

---

## 9. Decision Rationale Memory Skill

**When to use:** whenever a non-trivial technical decision is made
(schema change, library choice, architecture trade-off) — capture the
*why*, not just the *what*.

**Why this matters:** project memory already captures commits and file
changes (the "what"). Without this skill, "why did we choose CockroachDB
vector search over a separate vector DB" or "why did we reject
auto-launching the browser" becomes tribal knowledge that's easy to lose
— and is exactly the kind of question judges/teammates ask.

**Checklist:**
- [ ] When a decision is made that closes an "Open" item in `ROADMAP.md`
      or changes something in `ARCHITECTURE.md`/`TECH_STACK.md`, add a
      short rationale entry: the decision, the alternatives considered,
      and why this one won.
- [ ] Store rationale entries with an embedding so they're retrievable by
      meaning later ("why did we pick this embedding model?") the same
      way `architecture_notes` are.
- [ ] Keep entries short (2–5 sentences) — this is a decision log, not a
      design essay.
- [ ] When Reasoning Engine answers a question that touches a past decision,
      prefer citing the actual stored rationale over generating a
      plausible-sounding justification from scratch.

**Common failure modes to avoid:**
- Only logging decisions after something goes wrong — log at decision
  time, when the reasoning is freshest and cheapest to capture.

---

## 10. Mistake & Anti-Pattern Memory Skill

**When to use:** after any bug fix, failed approach, or dead-end
investigation — the goal is to stop paying for the same mistake twice.

**Checklist:**
- [ ] When a bug is fixed (per the Bug-Fixing Skill), store a short
      record: symptom, root cause, fix, and the file/module it occurred
      in — separate from the generic `todos`/`commits` tables so it can
      be queried specifically ("have we hit this kind of error before?").
- [ ] Before starting a fresh debugging session on a recurring area
      (e.g. auth, embedding pipeline), have the Reasoning Engine check mistake
      memory first and surface anything relevant up front.
- [ ] Same applies to abandoned approaches — if a design direction was
      tried and dropped (e.g. "tried polling instead of file watcher, too
      slow"), record that so it isn't silently retried later.
- [ ] Keep entries factual and specific — vague entries like "fixed a bug
      in auth" have no retrieval value; "JWT expiry check used local time
      instead of UTC, causing false 401s" does.

**Common failure modes to avoid:**
- Letting this table become a dumping ground of every minor typo fix —
  reserve it for mistakes worth not repeating (design-level or
  time-costly ones), not every trivial correction.

---

## 11. Demo & Presentation Skill

**When to use:** preparing the final hackathon submission and live demo.

**Checklist:**
- [ ] Record a full backup demo video early (by ~day 15) in case live
      automation fails on stage — never rely solely on a live run for a
      timed judged demo.
- [ ] Script the 3-minute demo flow from `PROJECT.md` §13 and rehearse it
      at least 3 times end-to-end.
- [ ] Prepare a one-paragraph answer for "is this an MCP server or an MCP
      client?" and "why CockroachDB specifically over a generic vector
      DB?" — judges will ask.
- [ ] Have the architecture diagram (`ARCHITECTURE.md` §1) ready to show
      or screen-share.
- [ ] Test the demo on the actual machine/network that will be used for
      judging, not just a dev machine, at least once beforehand.

**Common failure modes to avoid:**
- Demoing on an unfamiliar machine/network for the first time live.
- Over-promising cross-platform support if only one OS was actually
  tested.
