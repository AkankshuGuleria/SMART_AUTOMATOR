# Security and data handling

## Scope

The current application is a local, single-user MVP. The backend is intended
to bind to loopback and is not documented as a hardened or authenticated
public service. Do not expose it to an untrusted network.

## Sensitive data

Captured activity can include repository names and paths, commit messages,
terminal commands, TODOs, OCR text, and snippets of project context. Treat
these as user data:

- Redact secret-shaped values before captured text is persisted or sent to a
  reasoning provider.
- Do not store secret values in CockroachDB. `credential_refs` contains
  lookup labels only.
- Keep local provider keys and database connection strings in
  `backend/.env` or an OS credential manager; `.env` files must remain
  ignored by Git.
- Do not persist raw screenshots by default or forward OCR-derived context
  externally without user approval.
- Apply an explicit retention policy before storing real terminal history
  over long periods.

## External providers and app handoffs

When cloud reasoning, embedding services, or external coding tools are used,
selected prompts and retrieved context may leave the machine. Configure only
providers approved for the data being processed. Approval gates must remain
in place for external submission.

## OS actions

Workspace restore, command execution, app focus, clipboard paste, keystrokes,
and browser/app operations can change local state. Keep actions routed through
the planner/tool policy. Require explicit approval for external submission
and other high-impact actions. Never make a failed action appear successful.

## API and desktop boundaries

- Bind local development to `127.0.0.1`.
- The existence of an `API_KEY` configuration value does not establish that
  all routes enforce authentication. Confirm route-level enforcement before
  any network exposure.
- Do not put credentials in URLs, command output, screenshots, issue reports,
  or documentation.
- Use a disposable repository and database for demos and tests.

## Reporting

Do not include live credentials, personal project data, or unredacted logs in
bug reports. Report suspected vulnerabilities through the repository's
private disclosure process if one is established; do not publish exploit
details for an exposed deployment.

This document describes current handling expectations. It is not a security
certification or production deployment approval.

## Smart-workspace safeguards

- **Secrets from the Needs inbox** are written only to Windows Credential
  Manager (`keyring`, service `AUTOMATA:<project_id>`) and/or the project's
  `.env` (with a warning when git does not ignore it). Values are never stored
  in `memory.db`, `tasks.db`, CockroachDB, logs, or prompts.
- **Project profiles** read env variable names and whether a value exists —
  never the values.
- **Synthetic input** is only delivered to a window Windows confirms is the
  target; AUTOMATA's own window is never typed into; prompt hand-offs press
  Enter only after the pasted text is read back (UIA or OCR). Tests run with
  `AUTOMATA_DISABLE_DESKTOP_INPUT=1`.
- **Agent tasks** pause for approval before sending a prompt to another app and
  before running build/test commands. The prompt is visible in the task first.
- **Local data** (memory, tasks, usage, screenshots under `%TEMP%\automata_screens`)
  stays on the machine. Window titles and captured text are redacted.
- **Autostart** uses the per-user Run key (desktop app) or a Startup-folder
  launcher (backend only) — removable from Settings.
