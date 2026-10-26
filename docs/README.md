# Documentation

Start with the [project README](../README.md). Contributors and AI coding agents:
read [AGENTS.md](AGENTS.md) first.

## Using AUTOMATA

| Document | What it covers |
| --- | --- |
| [User guide](USER_GUIDE.md) | Setup, projects, memory, Resume, delegation, the work bar, permissions |
| [Product brief](PROJECT.md) | Problem, user, capabilities, boundaries, success criteria |
| [Project status](PROJECT_STATUS.md) | What is verified, with evidence, and known limits |
| [Roadmap](ROADMAP.md) | What comes next |

## Building on it

| Document | What it covers |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Start here: repo map, commands, rules, where to start for common changes |
| [Development guide](DEVELOPMENT.md) | Prerequisites, running, configuration, tests, desktop build, troubleshooting |
| [Architecture](ARCHITECTURE.md) | Components, data flows, trust boundaries |
| [Repository structure](STRUCTURE.md) | Where every part of the code lives |
| [Coding conventions](CONVENTIONS.md) | Naming, placement, boundaries, definition of done |
| [Engineering playbooks](SKILLS.md) | Checklists for testing, bug fixing, frontend, backend, prompts |
| [Technology stack](TECH_STACK.md) | Libraries, versions, configuration variables |
| [API reference](API_REFERENCE.md) | HTTP and WebSocket endpoints, permission flow |
| [Data model](DATABASE_SCHEMA.md) | Local SQLite stores and the optional CockroachDB schema |
| [Action policies](ACTION_POLICIES.md) | Auto / suggest / confirm / approval tiers and permission categories |
| [Workflow engine](WORKFLOW_ENGINE.md) | Versioned workflows, gates, checkpoints |
| [QA checklist](QA_CHECKLIST.md) | Manual verification before a release |

## Security

| Document | What it covers |
| --- | --- |
| [Security guide](SECURITY.md) | Secrets, permissions, local-only API, data handling |
| [Security audit](SECURITY_AUDIT.md) | Threat model, findings and fixes, scanner results, how to re-run them |

## History

| Document | What it covers |
| --- | --- |
| [Smart-workspace plan](history/smart-workspace-plan.md) | The original phased plan and the live test findings behind it |
| [Project audit, 2026-10-26](history/2026-10-26-project-audit.md) | Audit against the problem statement and its fixes |
