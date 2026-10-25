# API reference

The FastAPI application is defined in `backend/api/server.py`. Open
`http://127.0.0.1:8000/docs` while the local backend is running for generated
request/response schemas and the authoritative OpenAPI document.

Base URL: `http://127.0.0.1:8000`
WebSocket: `ws://127.0.0.1:8000/ws`

## System and settings

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API, database, and provider health |
| `GET` | `/settings/reasoning-mode` | Read current reasoning mode |
| `POST` | `/settings/reasoning-mode` | Change reasoning mode |
| `POST` | `/settings/reset-cooldowns` | Reset provider cooldowns |
| `GET` | `/tools/status` | Report tool availability (cached 5 min) |
| `GET` | `/system/metrics?processes=true` | Live CPU / GPU / RAM / disk / network snapshot, ~6 min history, optional top processes |
| `GET` | `/system/autostart` | Whether the agent starts hidden at Windows sign-in |
| `POST` | `/system/autostart` | Body `{"enabled": bool}` — create/remove the Startup-folder launcher |

## App usage

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/usage/summary?range=today\|week\|month` | Active time per app and category, hourly/daily buckets, focus %, switches |
| `GET` | `/usage/timeline?day=YYYY-MM-DD` | Focus segments for one local day |
| `GET` | `/usage/status` | Tracker state (running, paused, idle, current app) |
| `POST` | `/usage/tracking` | Body `{"enabled": bool}` — pause/resume recording |

## Projects, activity, sessions

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/projects` | List registered projects |
| `POST` | `/projects` | Register a project (422 if the folder does not exist; returns the existing project for a duplicate path) |
| `GET` | `/projects/{project_id}/brief` | Read a project's brief |
| `POST` | `/projects/{project_id}/brief/generate` | Generate/update a brief |
| `POST` | `/projects/{project_id}/restore` | Start workspace restore |
| `GET` | `/projects/{project_id}/decisions` | Read decision provenance |
| `GET` | `/projects/{project_id}/sessions` | List sessions |
| `POST` | `/projects/{project_id}/sessions/end` | End a session |
| `GET` | `/activity/feed` | Read the activity feed |

## Memory and chat

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/query` | Query project memory |
| `POST` | `/chat` | Parse intent and return a reply/actions |
| `POST` | `/chat/approve-action` | Approve a pending chat action |

## Workflows and automation

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/workflows` | List registered workflows |
| `POST` | `/workflows/{workflow_id}/start` | Start a workflow |
| `POST` | `/workflows/{run_id}/approve` | Resolve a workflow approval gate |
| `GET` | `/external-agents/status` | Read external bridge availability |
| `POST` | `/external-agents/{tool}/prompt` | Submit an approved external prompt |
| `POST` | `/commands/execute` | Request/execute a policy-controlled command |
| `POST` | `/execute/open_browser` | Request browser opening |
| `POST` | `/cross-app/tasks` | Start an asynchronous cross-app task |
| `GET` | `/cross-app/tasks/{task_id}` | Read cross-app task status |

## Agent actions and project insight

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/projects/{project_id}/generate-commit-message` | Generate a commit message |
| `POST` | `/projects/{project_id}/find-auth-code` | Find authentication-related code |
| `POST` | `/projects/{project_id}/continue-work` | Suggest or resume project work |
| `POST` | `/projects/{project_id}/project-summary` | Generate a project summary |
| `POST` | `/projects/{project_id}/start-dev-environment` | Start development services |
| `POST` | `/projects/{project_id}/explain-repository` | Explain repository structure/context |
| `GET` | `/projects/{project_id}/analytics` | Read project analytics |
| `GET` | `/projects/{project_id}/metrics/live` | Read live project metrics |
| `GET` | `/projects/{project_id}/diagnostics/commit-error` | Correlate recent failures with changes |
| `GET` | `/projects/{project_id}/memory-graph` | Read memory graph data |

## WebSocket events

Connect to `/ws` for server events. The typed frontend client currently
recognizes connection, restore progress, brief-ready, autonomous-action, and
echo event types. Event payloads may evolve; use the client types and server
implementation as the source of truth.

## Local-only warning

The service is configured for loopback use. Do not expose it to a public or
untrusted network. Current API route definitions do not establish a
multi-user authentication/authorization boundary.
