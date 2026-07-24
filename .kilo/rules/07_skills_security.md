# AUTOMATA — Credentials & Secrets Skill (SKILLS.md §8)

**Apply any time AUTOMATA needs to store, retrieve, or use a credential.**

## Core rule
> CockroachDB NEVER stores secret values. Only `credential_refs` labels.
> Real secrets live in the OS-native credential store (Windows Credential Manager).
> The `keyring` Python library is the interface — already a dependency.

## What goes WHERE
| Item | Location | Never |
|---|---|---|
| Real secrets (API keys, DB passwords) | `backend/.env` (gitignored) | In code, docs, or DB |
| Credential references/labels | `credential_refs` table in CockroachDB | Actual values |
| Secret resolution at runtime | `keyring` → OS vault, in-memory only | Written to logs or DB |

## Redaction patterns to apply BEFORE any CockroachDB write or Bedrock call
Apply `memory/capture.redact_secrets()` to all captured terminal commands and file diffs.
Patterns to redact: `ghp_`, `AKIA`, `sk-`, `key=<value>`, `token=<value>`, `password=<value>`, `Bearer <token>`

## .env file
- Template: `backend/.env.example` (safe to commit)
- Real values: `backend/.env` (gitignored — NEVER commit)
- Copy: `Copy-Item backend/.env.example backend/.env` then fill in values

## Common failure modes to AVOID
- "Just for the demo" shortcuts — a real key in a config file gets forgotten and shipped
- Logging full Bedrock request/response payloads without checking for secrets first
