# AUTOMATA — security and output

Details: `docs/SECURITY.md`, `docs/SECURITY_AUDIT.md`.

## Security
- Keep secret values in `backend/.env` (git-ignored) or Windows Credential Manager via
  `keyring`. The cloud DB stores only `credential_refs` labels.
- Run `memory.capture.redact_secrets()` on captured text before storing it or
  sending it to a model; never log secret values.
- PC control (apps, keys, clipboard, media, screen, workspace, commands) asks
  the user first via `security/permissions`; approvals are single-use.
- The API accepts requests only from this PC and the AUTOMATA UI
  (`security/http_guard.py`). Do not loosen CORS or the guard.
- No `pickle`, `eval` or `shell=True` on stored or remote data.

## Output style
- Short, factual, no chatbot filler ("Certainly!", "As an AI…").
- Ground answers in retrieved memory; when nothing matches say
  **"No memory found for that query"** — never invent details.
- Commit messages in imperative mood.
