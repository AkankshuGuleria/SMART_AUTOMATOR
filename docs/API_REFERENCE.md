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

## Smart workspace (`backend/api/workspace_routes.py`)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/system/self-check` | Every dependency with status + fix hint |
| `GET` | `/ai/status` | Online/offline, configured cloud providers, Ollama status, offline embeddings, last answering provider |
| `GET` | `/ai/local/recommendation` | Local model sized to this GPU/disk, catalog |
| `POST` / `GET` | `/ai/local/pull` | `{model}` start an Ollama pull / poll progress |
| `POST` | `/ai/local/select` | `{chat_model}` choose the local chat model |
| `POST` | `/ai/local/install-ollama` | Open the official winget installer in a visible window |
| `POST` | `/ai/local/offline-embeddings` | `{enabled}` toggle fastembed (needs `uv sync --extra local-ai`) |
| `GET` | `/memory/search?q=&project_id=` | Local memory search (offline); "No memory found for that query" when empty |
| `GET` | `/memory/stats` | Memory counts per kind, store path |
| `POST` | `/projects/{id}/activate` | Capture follows this project |
| `GET` | `/workspace/capture` | Capture status |
| `POST` / `GET` | `/projects/{id}/snapshot` | Save / read the latest session snapshot |
| `POST` | `/workspace/snapshot-active` | Snapshot the active project (tray menu) |
| `POST` | `/projects/{id}/resume` | `{open_editor, open_terminal, start_servers}` reopen the workspace; per-step results |
| `GET` | `/projects/{id}/profile?refresh=` | Detected stack, run book, env requirements, scored modules |
| `GET` | `/desktop/windows` | Visible app windows (excluding AUTOMATA) |
| `GET` | `/desktop/tabs` | Browser tabs per window (UI Automation) |
| `POST` | `/desktop/tabs/switch` | `{title, app?}` switch tab, verified by window title |
| `POST` | `/desktop/focus` | `{app, title_hint?}` verified focus |
| `POST` | `/desktop/type` | `{text, app?}` type/paste with read-back |
| `POST` | `/desktop/read` | `{app?, region?, expected_text?}` capture + OCR |
| `POST` | `/tasks` | `{request, agent, project_id}` create a delegation task |
| `GET` | `/tasks`, `/tasks/{id}` | List / detail (steps, outputs, needs) |
| `POST` | `/tasks/{id}/answer` | `{answers: {folder, stack, features, style, extra, q1...}}` answer the clarify questions; `{}` = defaults; 422 for a relative path or missing drive |
| `POST` | `/tasks/{id}/approve`, `/tasks/{id}/cancel` | Release the waiting step / cancel |
| `GET` | `/permissions` | Per category (`app_control`, `media`, `launch`, `screen`, `workspace`, `system`): `ask` or `allow`, with label and help |
| `POST` | `/permissions` | `{category, mode: ask\|allow}` |
| `POST` | `/assist` | `{text, project_id?}` work bar: quick command (media, Spotify, search, screen) or falls back to `/chat`; returns `{handled_by, intent, reply, success}` |
| `GET` | `/assist/now-playing` | Current media session `{title, artist, app, status, playing}` |
| `POST` | `/assist/media` | `{action: play_pause\|next\|previous\|volume_up\|volume_down\|mute}` system media keys |
| `POST` | `/assist/screen` | `{question?, app?}` OCR the window behind AUTOMATA and answer (only when called) |
| `GET` | `/needs?project_id=&refresh=` | Open Inbox items (reconciled with the project profile) |
| `POST` | `/needs/{id}/resolve` | `{save_to: keyring\|env_file\|both\|done\|dismiss, value?}` |

WebSocket `/ws` also emits `task_update` and `task_needs_input` events. Task
status `waiting_input` means the task waits for answers to its questions.

`/chat` runs quick commands first (intent `assist_<name>`, no project needed):
`assist_pause`, `assist_resume`, `assist_next`, `assist_previous`,
`assist_volume_up/down`, `assist_mute`, `assist_now_playing`,
`assist_spotify_play`, `assist_search`, `assist_screen`.

New chat intents: `delegate_task` ("using antigravity build …"), `switch_tab`,
`type_text` ("type 'x' into notepad"), `list_windows`.


## Permissions on actions that control the PC

Routes that act on the PC (`/assist`, `/assist/media`, `/assist/screen`,
`/desktop/focus|type|read|tabs/switch`, `/projects/{id}/resume`,
`/projects/{id}/start-dev-environment`, `/execute/open_browser`,
`/external-agents/{tool}/prompt`, `/cross-app/tasks`, `/commands/execute` with
`allow_execute`, and quick commands in `/chat`) first answer
`{"needs_permission": {id, category, label, help, action}}` unless the category
is always allowed. Send the same request again with `"permission_id": "<id>"`
after the user approves; an id works once, for that exact action, within 5
minutes. Chat planner actions in these categories return `policy: confirm_once`
plus `permission` / `permission_category`, executed via `/chat/approve-action`.

All requests must come from `127.0.0.1`/`localhost` and, when a browser sends
an `Origin`, from the AUTOMATA UI (see SECURITY.md → Local API guard).
