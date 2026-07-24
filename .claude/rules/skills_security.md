# Secrets & Security Skill — AUTOMATA (SKILLS.md §8)

## Core rule
CockroachDB stores ONLY `credential_refs` labels — NEVER secret values.
Real secrets → `backend/.env` (gitignored) or OS Credential Manager via `keyring`.

## Where each thing lives
| Secret type | Correct location | NEVER here |
|---|---|---|
| DB connection string | `backend/.env` → `COCKROACHDB_CONNECTION_STRING` | Code files, docs, DB rows |
| AWS keys | `backend/.env` → `AWS_ACCESS_KEY_ID` / `SECRET` | Code, committed files |
| Credential label/ref | `credential_refs` CockroachDB table | Secret value — label ONLY |
| Runtime secret resolution | `keyring` Python lib → Windows Credential Manager | Logs, DB, Bedrock prompts |

## Redaction before writes
Call `memory.capture.redact_secrets(text)` before writing to CockroachDB or sending to Bedrock.
Patterns: `ghp_`, `AKIA`, `sk-`, `key=`, `token=`, `password=`, `Bearer `

## Setup
```powershell
Copy-Item backend/.env.example backend/.env   # then fill in real values
# .env is gitignored — confirm before any git commit
```

## Failure modes to avoid
- "Just for the demo" key in a config file — it gets forgotten and shipped
- Logging Bedrock payloads without checking for secrets first
