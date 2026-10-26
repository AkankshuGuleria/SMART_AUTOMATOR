# Secrets & security skill — AUTOMATA

Full guide: `docs/SECURITY.md`; latest audit and how to re-run the scanners:
`docs/SECURITY_AUDIT.md`.

## Where secrets live
| Secret | Correct location | Never |
|---|---|---|
| Provider keys, DB connection string | `backend/.env` (git-ignored) | Code, docs, DB rows, logs, prompts |
| Values entered in the Needs inbox | Windows Credential Manager (`keyring`) and/or the project's `.env` | AUTOMATA's own databases |
| Credential label | `credential_refs` table | The value itself |

## Rules
- Redact with `memory.capture.redact_secrets(text)` before storing text or sending it to a model.
- Controlling the PC asks first: `security/permissions.check(category, action, permission_id)`.
  Approvals are server-issued and single-use; never accept a caller's "approved" flag.
- The API serves only this PC and the AUTOMATA UI (`security/http_guard.py`) — keep it that way.
- No `pickle`, `eval` or `shell=True` on stored/remote data; validate ids used in file paths.
- `.env` writes refuse line breaks (variable injection) — keep `tasks/needs._write_env` strict.

## Before committing
```powershell
cd backend; uv run ruff check .   # S rules on; reviewed ignores in pyproject.toml
git check-ignore backend/.env   # must print the path
```
