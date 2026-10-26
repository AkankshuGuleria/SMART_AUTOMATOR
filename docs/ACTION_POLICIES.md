# Action policies and permissions

How AUTOMATA decides whether an action runs on its own, needs a click, or
needs the user's permission. Implementation: `backend/decision_engine/planner.py`
(`ACTION_POLICY`), `backend/security/permissions.py`, `backend/tasks/engine.py`
and `backend/workflow_engine/`.

## 1. Policy tiers

| Policy | Used for | Behaviour |
| --- | --- | --- |
| `auto_execute` | Passive, reversible work: summaries, briefs, memory queries, listing windows | Runs without a prompt |
| `suggest` | Changes the user should decide on: commit messages, test runs, shell commands | Shown as a card; nothing runs until the user approves it |
| `confirm_once` | Controlling the PC (see §2) | An approval card / permission prompt before it runs |
| `require_approval` | Sending a prompt into another app | Explicit approval every time |

Do not infer that an action is safe from its name — classify it in
`ACTION_POLICY` and, if it touches the PC, map it to a permission category.

## 2. Permission categories

Every action that controls the PC belongs to a category. Each category is
**Ask every time** by default; the user can switch it to **Always allow** in
Settings → Permissions.

| Category | Examples |
| --- | --- |
| `app_control` | Focus a window, switch a browser tab, type, paste, press keys, use the clipboard, cross-app tasks, prompts to other apps |
| `media` | Play / pause / next / previous, volume, play a song on Spotify |
| `launch` | Open an app, a website or a web search |
| `screen` | Screenshot a window and read its text (OCR) |
| `workspace` | Resume (editor, terminal, dev servers), start dev servers |
| `system` | Run a shell command |

When a category is set to *ask*, the API returns `needs_permission` with a
single-use id; the UI shows **Allow once / Always allow / Deny** and resends the
call with that id. Chat actions in these categories become `confirm_once`
approval cards. Approvals expire after 5 minutes and work for one exact action.

## 3. Delegation tasks

| Step | Policy | Notes |
| --- | --- | --- |
| Ask what's needed | input | Folder / save location, stack, features, design; the task waits for answers |
| Context, prompt | auto | Prompt is visible in the task before anything is sent |
| Hand-off to the agent | approval | Paste confirmed by read-back; sent only after approval |
| Watch for changes | auto | Keeps waiting while the agent reports it is busy |
| Build / tests | approval | Runs the project's own run-book commands |
| Needs, report | auto | Keys still needed go to the Needs inbox |

## 4. Workflows

Workflow definitions are versioned YAML under
`backend/workflow_engine/definitions/`. Steps call registered tools and inherit
their policies; contiguous gated steps are grouped into one approval. See
[WORKFLOW_ENGINE.md](WORKFLOW_ENGINE.md).

## 5. Rules that never change

- Nothing that changes the PC runs because a caller *says* it was approved.
- A failed or unverified action is never reported as done.
- External hand-offs redact secrets first and show the prompt before sending.
- Every autonomous decision is logged with provenance (`decision_log`).
