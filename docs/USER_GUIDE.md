# User guide

## 1. Start AUTOMATA

- **Desktop app (recommended):** run `frontend\src-tauri\target\release\app.exe`
  (build it with `npx tauri build --no-bundle`). It sits in the system tray and
  starts the background agent for you. Closing the window only hides it; use the
  tray menu → *Quit and stop agent* to exit completely.
- **Developer mode:** `cd backend; uv run python main.py` and
  `cd frontend; npm run dev`, then open http://localhost:5173.
- Open **Setup & health** first: it lists what works and how to fix what doesn't.
- To keep it always running: **Settings → Background agent → Start at sign-in**.

## 2. Projects and memory

Add a project with its full folder path (**Projects**). Selecting a project
makes capture follow it: file edits, commits and terminal commands are recorded
(build folders and secrets are skipped). Memory is stored on this PC and synced
from CockroachDB when it is configured, so it also works offline.

Ask in **AI Chat** or the **work bar** (Alt+Space / Ctrl+Alt+A): "what did I work on
yesterday?", "where is authentication handled?". If nothing relevant was
captured, AUTOMATA says so instead of guessing.

## 3. Pick up where you left off

The dashboard card **Where you left off** shows your branch, uncommitted files,
recently edited files, running dev servers, open TODOs and current task. It is
saved every 10 minutes, when you go idle and when AUTOMATA closes.
**Resume workspace** reopens your editor with those files, a terminal in the
project and the dev servers (servers already running are skipped).

## 4. Project profile

The **Project profile** card (dashboard and Projects → insights) is built from
the project's own files: stack, how to run/test/build, ports, env variables that
are not set yet, and module readiness scores with the reason for each score.
Use the refresh icon after big changes.

## 5. Delegate work to other AI apps

In chat: *"using antigravity create a landing page with pricing"*, or use
**Tasks → Delegate a task**. AUTOMATA:

1. **asks you a few questions** first (Tasks shows a form; chat lists them):
   where to work (this project's folder, or where to save a new project,
   suggested under `D:\Projects`), the stack for a new project, what it must
   include, design direction and anything else. *Use defaults* skips them,
2. gathers project context and memory,
3. writes a complete prompt with your answers (you can read it in the task),
4. **waits for your approval**, then opens the folder in **Antigravity IDE**,
   opens its Agent panel (Ctrl+L) if needed, pastes the prompt into the chat
   box, checks the text arrived, and sends it. Cursor and the Claude app work
   the same way; VS Code uses its `code chat` command (delivery can't be
   confirmed there); ChatGPT opens in the browser. If the chat box already has
   your own text, AUTOMATA stops instead of overwriting it. Antigravity then
   shows the agent's edits for you to Accept or Reject. While AUTOMATA reads
   the IDE through accessibility, its status bar may say "Screen Reader
   Optimized"; that is VS Code's automatic mode and changes nothing else,
5. watches the folder for file changes,
6. **waits for approval** again, then runs the build/tests,
7. lists the keys and connection strings still needed, and reports.

## 6. Needs from you

**Needs from you** lists API keys, connection strings and accounts the project
needs, with step-by-step instructions and a link to the provider. Paste the
value and choose *Credential Manager*, *.env* or both. AUTOMATA never stores the
value itself and warns if the `.env` file is not ignored by git.

## 7. AI work bar (Alt+Space or Ctrl+Alt+A)

Press **Alt+Space** (or **Ctrl+Alt+A** if another app owns Alt+Space) from any
app. A bar opens at the top of the screen; **Esc** or clicking elsewhere hides
it. Type anything:

- music: *"play lofi beats on spotify"* (or just *"play arijit singh"*),
  *"pause"*, *"next song"*, *"previous"*, *"volume up"*, *"mute"*,
  *"what's playing?"*. The tile shows the current track with controls.
- search: *"search fastapi websockets"*, *"search react hooks on youtube"*,
  *"search github for tauri tray"* (google, youtube, github, stackoverflow,
  npm, pypi, maps, amazon, wikipedia).
- screen: **Read my screen** (or *"explain the error on my screen"*) reads the
  window behind the bar with OCR and answers. It runs **only when you ask**;
  the screenshot is deleted right after OCR and only redacted text goes to the
  model.
- anything else goes to the normal chat: project questions, *"using antigravity
  build ..."*, *"what windows are open"*.

Quick buttons: search the typed text, resume work, save state, and open Tasks
(it shows how many tasks are waiting for you).

## 8. Desktop control

Chat commands such as *"what windows are open"*, *"switch to the github tab"*,
*"type 'hello' into notepad"*, *"paste it into notepad"*, *"take a screenshot"*.
Actions that change focus or type ask for confirmation first and report exactly
which window received the input. If Windows blocks a switch, you get an error,
not a fake success.

## 9. Resources and app usage

**Resources → System** shows live CPU (per thread), GPU, RAM, disk, network and
top processes. **App usage** shows where your time went today / 7 days / 30
days (idle time excluded; pause any time).

## 10. Local AI and offline

**Setup → Local AI** recommends a model for your GPU, installs Ollama (opens the
official installer) and downloads models with progress. When the internet is
down, AUTOMATA answers with the local model automatically.

## 11. When something is unavailable

The Setup screen shows each dependency with a fix. Failed actions always appear
as errors or partial results with the reason.
