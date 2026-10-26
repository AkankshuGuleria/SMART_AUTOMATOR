# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Report it
privately through GitHub's
[private vulnerability reporting](https://github.com/AkankshuGuleria/SMART_AUTOMATOR/security/advisories/new)
with the steps to reproduce, the affected version or commit, and the impact.
Never include real credentials or personal data in a report.

You can expect an acknowledgement within a few days and a fix or mitigation
plan once the issue is confirmed.

## Supported versions

Only the latest commit on `main` is supported.

## Security model

AUTOMATA is a single-user desktop app whose agent listens on `127.0.0.1` only.
How secrets, permissions and the local API are protected:
[docs/SECURITY.md](docs/SECURITY.md). Latest audit, scanner results and how to
re-run them: [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md).
