# Engineering playbooks

Use these checklists when changing the product. They define safe defaults;
they do not claim that an unverified integration works.

## 1. Testing

- Backend unit/API tests: `cd backend; uv run pytest tests/ -v --tb=short`.
- Frontend tests: `cd frontend; npm test`.
- Frontend type-check/build: `cd frontend; npm run build`.
- Keep automated tests off production CockroachDB and live model APIs.
- Mock external providers and OS effects. Use a disposable local database for
  database integration checks.
- Assert the returned content, state transitions, and failure behavior.
- After schema/embedding changes, recheck retrieval dimensions and results.

## 2. Bug fixing

1. Reproduce the exact visible failure before changing code.
2. Locate it within the boundaries in `CONVENTIONS.md`.
3. Add a regression test or document a manual reproduction when automation
   cannot safely exercise the behavior.
4. Fix the cause, then verify the affected user flow.
5. Do not turn errors into silent success-shaped fallbacks.

## 3. Frontend

- Keep data access in the typed API client and business decisions on the
  backend.
- Every asynchronous action needs loading, success, and failure feedback.
- Show stepwise progress for restore and workflows.
- Keep approval actions explicit and keyboard navigation usable.
- Avoid exposing raw database field names as user-facing language.

## 4. Backend

- CockroachDB access goes through `backend/db/client.py`.
- Reasoning and embedding provider calls go through
  `backend/ai/bedrock_client.py`.
- Capture runs in background threads and must not block FastAPI request
  handling.
- Redact secrets before storing captured data or sending it to a provider.
- Make writes idempotent where the event identity permits it.
- Surface degraded service state and automation errors to logs/API/UI.

## 5. Prompt and retrieval quality

- Ground factual answers only in retrieved project evidence.
- Preserve source type, timestamps, and project scope in reasoning context.
- Separate recalled facts from generated suggestions.
- If there is no evidence, report that no memory was found.
- Test several phrasings for a retrieval intent; do not tune only to a demo
  prompt.
- Avoid logging raw prompts or retrieved project context unless data is
  redacted and the local-only development purpose is clear.

## 6. User-facing output

- Be concise, factual, and action-oriented.
- Avoid generic chatbot filler and fabricated details.
- Clearly state uncertainty and distinguish suggestions from completed work.
- Redact secret-shaped strings in captured commands, logs, and summaries.

## 7. Preference memory

- Treat learned style preferences as soft guidance, not correctness rules.
- Give explicit current user instructions precedence.
- Keep confidence and evidence; do not infer a durable preference from one
  observation.
- Do not send preference data to an external provider without the same
  privacy controls as other project context.

## 8. Credentials and privacy

- Never commit real keys, tokens, passwords, or connection strings.
- Store local secrets in `backend/.env` or an OS credential manager.
- CockroachDB may store a credential reference label, never its value.
- Redact captured terminal commands and OCR text before persistence or model
  use.
- Treat screenshots, repository context, file paths, and commands as
  potentially sensitive data.
- Keep the local API bound to loopback; do not expose it to an untrusted network.

## 9. Decision rationale

For non-trivial changes to schema, architecture, provider behavior, or
approval policy, record the decision and reason in the relevant project
documentation or pull request. Prefer an explicit trade-off over an
undocumented default.

## 10. Mistakes and regressions

When a costly or recurring defect is fixed, record its symptom, cause, and
prevention in the issue or change record. Do not turn the database mistake
log into a record of trivial typos.

## 11. Demo and release

- Follow `docs/QA_CHECKLIST.md` using a disposable repository and test data.
- Rehearse on the actual Windows machine intended for the demo.
- Keep a recorded fallback when live OS/provider behavior is part of a
  presentation.
- Do not describe an implementation as verified until the corresponding
  automated or manual evidence exists.
