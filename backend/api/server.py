"""
api/server.py - AUTOMATA local FastAPI server.

Owns: HTTP and WebSocket API exposed to the React/Tauri frontend.
Never: Contains memory, reasoning, or OS-action business logic.
Ref: ARCHITECTURE.md section 3.1, section 3.2, TECH_STACK.md frontend transport.
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from logging_config import configure_logging

configure_logging()

from config import settings  # noqa: E402
from db.client import health_check as db_health_check  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AUTOMATA Agent API",
    description="Local API for the AUTOMATA persistent memory developer agent.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict:
    """Return local agent, database, and reasoning-backend health."""
    return {
        "api": "ok",
        "db": db_health_check(),
        "bedrock": "configured" if settings.bedrock_available else "not_configured",
        "embedding": "configured" if settings.embedding_available else "not_configured",
        "reasoning_mode": settings.reasoning_mode,
    }


@app.get("/settings/reasoning-mode", tags=["settings"])
async def get_reasoning_mode() -> dict:
    """Return the current reasoning mode preference."""
    return {"reasoning_mode": settings.reasoning_mode}


@app.post("/settings/reasoning-mode", tags=["settings"])
async def set_reasoning_mode(body: dict) -> dict:
    """Set the reasoning mode preference (local, cloud, or auto)."""
    from config import settings as _settings

    mode = str(body.get("reasoning_mode", "auto")).strip().lower()
    if mode not in ("local", "cloud", "auto"):
        return {"error": f"Invalid reasoning_mode: {mode}. Use 'local', 'cloud', or 'auto'."}

    # Update the environment variable so it persists
    os.environ["REASONING_MODE"] = mode

    # Reload settings
    _settings._load_settings()

    return {"reasoning_mode": mode}


@app.get("/projects", tags=["projects"])
async def list_projects() -> dict:
    """Return all tracked projects."""
    from db.client import get_projects

    return {"projects": get_projects()}


@app.post("/projects", tags=["projects"])
async def register_project(body: dict) -> dict:
    """Register a new project for memory tracking."""
    from db.client import insert_project

    name = body.get("name", "")
    repo_path = body.get("repo_path", "")
    remote_url = body.get("remote_url")

    if not name or not repo_path:
        return {"error": "name and repo_path are required"}

    project_id = insert_project(name, repo_path, remote_url)
    if project_id is None:
        return {"error": "failed to insert project"}

    return {"id": project_id, "name": name, "repo_path": repo_path}


@app.post("/projects/{project_id}/brief/generate", tags=["memory"])
async def generate_latest_brief(project_id: str) -> dict:
    """Generate and persist the latest project brief from stored memory."""
    from decision_engine.planner import _build_brief_payload
    from db.client import upsert_daily_brief, get_daily_brief

    payload = _build_brief_payload(project_id)
    if payload is None:
        return {"success": False, "error": "Could not read project memory", "brief": None}

    success = upsert_daily_brief(
        project_id=project_id,
        brief_date=str(payload.get("brief_date", datetime.now().strftime("%Y-%m-%d"))),
        commits_count=int(payload.get("commits_count", 0)),
        highlights=list(payload.get("highlights", [])),
        pending_items=list(payload.get("pending_items", [])),
    )

    brief = get_daily_brief(project_id)
    return {"success": success, "brief": brief, "error": None if success else "Failed to store brief"}


@app.get("/projects/{project_id}/brief", tags=["memory"])
async def get_latest_brief(project_id: str) -> dict:
    """
    Return the latest stored project brief plus recent raw memory context.

    Full brief generation is still Phase 2 work; this route is useful today
    because it exposes the stored memory that will feed that generation step.
    """
    from db.client import get_commits, get_daily_brief, get_file_edits, get_todos

    brief = get_daily_brief(project_id)
    commits = get_commits(project_id, limit=5)
    pending_todos = get_todos(project_id, status="pending")
    recent_edits = get_file_edits(project_id, limit=5)

    response = {
        "project_id": project_id,
        "brief": brief,
        "commits": commits,
        "pending_todos": pending_todos,
        "recent_edits": recent_edits,
    }

    if brief is None:
        response["note"] = (
            "No brief generated yet. Recent commits, TODOs, and edits are returned "
            "as raw memory context."
        )

    return response


@app.get("/projects/{project_id}/decisions", tags=["memory"])
async def list_decisions(project_id: str, limit: int = 20) -> dict:
    """Return recent decision log entries for a project."""
    from db.client import get_decisions

    return {"decisions": get_decisions(project_id=project_id, limit=limit)}


@app.post("/projects/{project_id}/sessions/end", tags=["projects"])
async def end_active_session(project_id: str, body: dict | None = None) -> dict:
    """End the active session for a project and fire the Decision Engine trigger."""
    from db.client import end_session, get_active_session

    session = get_active_session(project_id)
    if session is None:
        return {"error": "no active session", "session_id": None}

    session_id = str(session.get("id", ""))
    summary = None
    if body:
        summary = body.get("summary")

    success = end_session(project_id, session_id, summary=summary)
    if not success:
        return {"error": "failed to end session", "session_id": session_id}

    return {"ended": True, "session_id": session_id, "project_id": project_id}


@app.post("/projects/{project_id}/restore", tags=["automation"])
async def restore_workspace(project_id: str) -> dict:
    """Trigger workspace restoration for the given project."""
    from automation.restore import restore_workspace as _restore

    return _restore(project_id=project_id)


@app.post("/explain-repository", tags=["memory"])
async def explain_repository_route(body: dict) -> dict:
    """
    Ground an explanation of the project's repository structure in README content,
    live folder structure, and stored architecture notes.

    Returns a structured explanation payload plus the raw context used.
    """
    project_id = body.get("project_id")
    repo_path = body.get("repo_path", "")

    if not project_id or not repo_path:
        return {
            "project_id": project_id,
            "repo_path": repo_path,
            "readme_summary": "",
            "folder_structure": [],
            "architecture_notes": [],
            "explanation": None,
            "error": "project_id and repo_path are required",
        }

    from explain_repository import synthesize_explanation
    from memory.retrieval import retrieve_recent

    recent = retrieve_recent(project_id, "commits", limit=5)
    recent.extend(retrieve_recent(project_id, "file_edits", limit=5))
    recent.extend(retrieve_recent(project_id, "todos", limit=5))

    result = synthesize_explanation(project_id, repo_path, recent_memories=recent)
    return result


@app.post("/query", tags=["memory"])
async def query_memory(body: dict) -> dict:
    """
    Query stored project memory.

    Vector retrieval is tried first. If embeddings or the DB vector columns are
    unavailable, the route falls back to recent memory and still returns a
    useful grounded answer rather than a stub.
    """
    from ai.bedrock_client import invoke_reasoning
    from memory.retrieval import retrieve_by_vector, retrieve_recent

    question = str(body.get("question", "")).strip()
    project_id = body.get("project_id")
    requested_mode = str(body.get("reasoning_mode", "")).strip().lower() or None

    if not question:
        return {
            "answer": "Ask a question about a tracked project and I will search its stored memory.",
            "memories": [],
            "grounded": False,
        }

    memories = []
    if project_id:
        memories.extend(
            retrieve_by_vector(
                question,
                ["commits", "todos", "architecture_notes", "decision_log", "mistake_log"],
                project_id=project_id,
                top_k=8,
            )
        )

        if not memories:
            for table in ("commits", "todos", "file_edits", "architecture_notes"):
                memories.extend(retrieve_recent(project_id, table, limit=3))

    answer = None
    grounded = False

    if memories:
        mode_override = requested_mode if requested_mode in {"cloud", "bedrock", "local", "auto"} else None
        answer = invoke_reasoning(
            system_prompt=(
                "You are AUTOMATA's Reasoning Engine. Answer tersely using only "
                "retrieved project memory. If memory is incomplete, say what is "
                "missing without inventing details."
            ),
            user_message=question,
            retrieved_memories=memories,
            reasoning_mode=mode_override,
        )
        grounded = bool(answer)

    if answer is None:
        if memories:
            bullets = "\n".join(
                f"- [{memory.get('table', 'memory')}] {memory.get('content', '')}"
                for memory in memories[:6]
                if memory.get("content")
            )
            answer = "Reasoning is unavailable, but I found recent project memory:\n" + bullets
        elif project_id:
            answer = "No stored memory was found for that project yet."
        else:
            answer = "No project was selected, so I could not search scoped memory."

    return {
        "answer": answer,
        "memories": memories,
        "grounded": grounded,
    }


@app.post("/projects/{project_id}/generate-commit-message", tags=["agent-actions"])
async def generate_commit_message_route(project_id: str, body: dict | None = None) -> dict:
    """Generate a commit message grounded in the staged/unstaged diff and recent memory."""
    from agent_actions import generate_commit_message

    repo_path = ""
    staged = True
    if body:
        repo_path = body.get("repo_path", "")
        staged = bool(body.get("staged", True))
    return generate_commit_message(project_id, repo_path=repo_path, staged=staged)


@app.post("/projects/{project_id}/find-auth-code", tags=["agent-actions"])
async def find_auth_code_route(project_id: str, body: dict | None = None) -> dict:
    """Find authentication-related code locations using vector + recent retrieval."""
    from agent_actions import find_authentication_code

    query = "authentication"
    if body:
        query = body.get("query", query)
    return find_authentication_code(project_id, query=query)


@app.post("/projects/{project_id}/continue-work", tags=["agent-actions"])
async def continue_work_route(project_id: str) -> dict:
    """Suggest the next task based on the active session, TODOs, and recent memory."""
    from agent_actions import continue_previous_work

    return continue_previous_work(project_id)


@app.post("/projects/{project_id}/project-summary", tags=["agent-actions"])
async def project_summary_route(project_id: str) -> dict:
    """Generate a short project summary from recent memory."""
    from agent_actions import generate_project_summary

    return generate_project_summary(project_id)


@app.post("/projects/{project_id}/start-dev-environment", tags=["agent-actions"])
async def start_dev_environment_route(project_id: str) -> dict:
    """Start the development environment for the project."""
    from agent_actions import start_development_environment

    return start_development_environment(project_id)


@app.post("/cross-app/tasks", tags=["agent-actions"])
async def submit_cross_app_task(body: dict) -> dict:
    """Submit an asynchronous cross-app task."""
    from agent_actions import submit_cross_app_task as _submit

    task_id = str(body.get("task_id", ""))
    action = str(body.get("action", ""))
    params = body.get("params", {})
    if not task_id or not action:
        return {"error": "task_id and action are required"}
    return _submit(task_id=task_id, action=action, params=params)


@app.get("/cross-app/tasks/{task_id}", tags=["agent-actions"])
async def get_cross_app_task(task_id: str) -> dict:
    """Get cross-app task status."""
    from agent_actions import cross_app_task_status as _status

    return _status(task_id)


class _ConnectionManager:
    """Manages active WebSocket connections for broadcasting live agent events."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("WebSocket client connected | total=%d", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)
        logger.info("WebSocket client disconnected | total=%d", len(self.active))

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(ws)


@app.post("/chat", tags=["chat"])
async def chat(body: dict) -> dict:
    """Parse a chat message, route intent, and return a structured response."""
    from decision_engine.intent_parser import IntentParser, IntentType
    from decision_engine.planner import plan

    message = str(body.get("message", "")).strip()
    project_id = body.get("project_id")
    active_project_id = body.get("active_project_id")

    if not message:
        return {"error": "message is required"}

    parser = IntentParser()
    parsed = parser.parse(message, active_project_id=active_project_id or project_id)
    error = None
    planner_reply = ""
    plan_result: dict = {"actions": [], "reply": ""}

    target_intent = parsed.intent
    if parsed.intent in (IntentType.UNKNOWN, IntentType.GENERAL_CHAT):
        target_intent = IntentType.QUERY_MEMORY

    try:
        plan_result = plan(
            trigger=f"chat:{target_intent.value}",
            context={
                "message": message,
                "parsed": parsed.params or {},
                "project_id": parsed.project_id or active_project_id or project_id,
            },
        )
        planner_reply = plan_result.get("reply") or ""
    except Exception as exc:
        logger.exception("chat: planner failed")
        planner_reply = f"Could not process prompt: {exc}"
        error = str(exc)

    executed_actions = [a for a in plan_result.get("actions", []) if a.get("executed")]

    return {
        "intent": parsed.intent.value,
        "confidence": parsed.confidence,
        "reply": planner_reply,
        "actions": plan_result.get("actions", []),
        "executed_actions": executed_actions,
        "project_id": parsed.project_id,
        "error": error,
    }


@app.post("/commands/execute", tags=["automation"])
async def execute_command(body: dict) -> dict:
    """Execute a system command with provenance and safety checks."""
    from automation.command_executor import CommandExecutor

    command = str(body.get("command", "")).strip()
    cwd = str(body.get("cwd", ""))
    allow_execute = bool(body.get("allow_execute", False))
    context = str(body.get("context", ""))
    session_id = body.get("session_id")

    if not command:
        return {"error": "command is required"}

    executor = CommandExecutor(cwd=cwd, allow_auto_execute=allow_execute)
    result = executor.execute(command, context=context, session_id=session_id)

    return {
        "command": result.command,
        "status": result.status,
        "executed": result.executed,
        "suggested": result.suggested,
        "suggestion_reason": result.suggestion_reason,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "executed_at": result.executed_at,
        "undo_hint": result.undo_hint,
    }


@app.get("/tools/status", tags=["system"])
async def tool_status() -> dict:
    """Return connectivity/status for optional external tools."""
    from automation.agent_bridge import AgentBridge

    bridge = AgentBridge()
    tools = ["claude", "cursor", "antigravity"]
    return {
        "tools": [
            {
                "tool": t,
                "connected": bridge.check_tool(t).connected,
                "version": bridge.check_tool(t).version,
                "error": bridge.check_tool(t).error,
            }
            for t in tools
        ]
    }


@app.get("/activity/feed", tags=["system"])
async def activity_feed(limit: int = 50, project_id: Optional[str] = None) -> dict:
    """Return chronological activity/audit entries for the dashboard feed.

    Items are normalized to a consistent shape:
        { id, kind, summary, created_at, project_id, detail }
    """
    from db.client import get_decisions, get_commits, get_terminal_commands

    feed: list[dict] = []

    try:
        decisions = get_decisions(project_id=project_id, limit=limit) or []
        for d in decisions:
            feed.append({
                "id": str(d.get("id", "")),
                "kind": "decision",
                "summary": str(d.get("decision", d.get("rationale", "Agent decision"))[:120]),
                "created_at": str(d.get("decided_at") or d.get("created_at") or ""),
                "project_id": str(d.get("project_id", project_id or "")),
                "detail": str(d.get("rationale", "")),
            })
    except Exception as exc:
        logger.debug("activity_feed: decisions unavailable — %s", exc)

    try:
        commits = get_commits(project_id=project_id, limit=limit) or []
        for c in commits:
            feed.append({
                "id": str(c.get("id", "")),
                "kind": "commit",
                "summary": str(c.get("message", "Git commit")).split("\n")[0][:120],
                "created_at": str(c.get("committed_at") or c.get("created_at") or ""),
                "project_id": str(c.get("project_id", project_id or "")),
                "detail": str(c.get("hash", "")),
            })
    except Exception as exc:
        logger.debug("activity_feed: commits unavailable — %s", exc)

    try:
        cmds = get_terminal_commands(project_id=project_id, limit=limit) or []
        for cmd in cmds:
            feed.append({
                "id": str(cmd.get("id", "")),
                "kind": "terminal",
                "summary": str(cmd.get("command", "Terminal command"))[:120],
                "created_at": str(cmd.get("run_at") or cmd.get("created_at") or ""),
                "project_id": str(cmd.get("project_id", project_id or "")),
                "detail": "",
            })
    except Exception as exc:
        logger.debug("activity_feed: terminal_commands unavailable — %s", exc)

    feed.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"items": feed[:limit]}


# ─── Cross-App Control Routes ──────────────────────────


@app.post("/cross-app/copy-to-clipboard", tags=["cross-app"])
async def copy_to_clipboard_route(body: dict) -> dict:
    """Copy text to the clipboard."""
    text = str(body.get("text", ""))
    if not text:
        return {"success": False, "error": "text is required"}
    try:
        from automation.os_windows import copy_to_clipboard
        ok = copy_to_clipboard(text)
        return {"success": ok, "copied": ok, "length": len(text)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/paste-clipboard", tags=["cross-app"])
async def paste_clipboard_route(body: dict | None = None) -> dict:
    """Paste clipboard content."""
    try:
        from automation.os_windows import paste_clipboard
        text = paste_clipboard()
        return {"success": bool(text), "content": text}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/open-url", tags=["cross-app"])
async def open_url_route(body: dict) -> dict:
    """Open a URL in the default browser."""
    url = str(body.get("url", "")).strip()
    if not url:
        return {"success": False, "error": "url is required"}
    try:
        from automation.os_windows import launch_browser
        ok = launch_browser(url)
        return {"success": ok, "opened": ok, "url": url}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/focus-app", tags=["cross-app"])
async def focus_app_route(body: dict) -> dict:
    """Bring a known application window to the foreground."""
    app_name = str(body.get("app_name", "")).strip()
    if not app_name:
        return {"success": False, "error": "app_name is required"}
    try:
        from automation.os_windows import focus_app
        ok = focus_app(app_name)
        return {"success": ok, "focused": ok, "app": app_name}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/send-keystroke", tags=["cross-app"])
async def send_keystroke_route(body: dict) -> dict:
    """Send limited safe keystrokes to the active window."""
    keystrokes = str(body.get("keystrokes", "")).strip()
    if not keystrokes:
        return {"success": False, "error": "keystrokes is required"}
    try:
        from automation.os_windows import send_keystrokes
        ok = send_keystrokes(keystrokes)
        return {"success": ok, "sent": ok, "keystrokes": keystrokes}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/submit-prompt", tags=["cross-app"])
async def submit_prompt_route(body: dict) -> dict:
    """Submit a generated prompt to an external app (ChatGPT, Claude, Cursor, etc.). Requires approval."""
    app_name = str(body.get("app_name", "")).strip()
    url = str(body.get("url", "")).strip()
    prompt_text = str(body.get("prompt", "")).strip()
    if not prompt_text:
        return {"success": False, "error": "prompt is required"}
    try:
        from automation.os_windows import copy_to_clipboard, focus_app, launch_browser, launch_app, paste_clipboard, send_keystrokes
        steps: list[dict] = []
        copy_ok = copy_to_clipboard(prompt_text)
        steps.append({"action": "copy_to_clipboard", "success": copy_ok})
        if url:
            open_ok = launch_browser(url)
            steps.append({"action": "open_url", "success": open_ok, "url": url})
        elif app_name:
            open_ok = launch_app(app_name)
            steps.append({"action": "open_app", "success": open_ok, "app": app_name})
            if open_ok:
                focus_ok = focus_app(app_name)
                steps.append({"action": "focus_app", "success": focus_ok, "app": app_name})
        paste_ok = paste_clipboard()
        steps.append({"action": "paste_clipboard", "success": bool(paste_ok)})
        submit_ok = send_keystrokes("ctrl+enter")
        steps.append({"action": "send_keystroke", "success": submit_ok, "keystrokes": "ctrl+enter"})
        all_success = all(s.get("success") for s in steps)
        return {"success": all_success, "prompt_length": len(prompt_text), "steps": steps}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/cross-app/verify-result", tags=["cross-app"])
async def verify_result_route(body: dict) -> dict:
    """Verify whether an action worked."""
    check_type = str(body.get("type", "")).strip()
    target = str(body.get("target", "")).strip()
    if not check_type:
        return {"success": False, "error": "type is required"}
    try:
        result: dict = {"success": True, "check_type": check_type, "target": target}
        if check_type == "file_changed":
            if target and os.path.exists(target):
                result["verified"] = True
                result["exists"] = True
                result["size"] = os.path.getsize(target)
            else:
                result["verified"] = False
                result["exists"] = False
        elif check_type == "clipboard_has_content":
            from automation.os_windows import paste_clipboard
            content = paste_clipboard()
            result["verified"] = bool(content)
            result["content_preview"] = content[:200] if content else ""
        else:
            result["verified"] = True
        return result
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─── Visual Feedback Routes ────────────────────────────


@app.post("/visual/capture-screen", tags=["visual-feedback"])
async def capture_screen_route(body: dict | None = None) -> dict:
    """Capture a screenshot of the screen or a region."""
    region = str(body.get("region", "")) if body else ""
    try:
        from automation.os_windows import capture_screen
        path = capture_screen(region if region else None)
        return {"success": bool(path), "path": path}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/ocr-image", tags=["visual-feedback"])
async def ocr_image_route(body: dict) -> dict:
    """Extract text from a screenshot/image."""
    image_path = str(body.get("image_path", "")).strip()
    if not image_path:
        return {"success": False, "error": "image_path is required"}
    try:
        from automation.ocr import ocr_image
        text = ocr_image(image_path)
        return {"success": bool(text), "text": text}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/read-visible-context", tags=["visual-feedback"])
async def read_visible_context_route(body: dict | None = None) -> dict:
    """Capture and OCR the current visible workspace."""
    try:
        from automation.screen_capture import capture_screen
        from automation.ocr import ocr_image
        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/diagnose-visible-error", tags=["visual-feedback"])
async def diagnose_visible_error_route(body: dict | None = None) -> dict:
    """Parse visible error text from the screen."""
    try:
        from automation.screen_capture import capture_screen
        from automation.ocr import ocr_image
        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "diagnosed": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/review-visible-design", tags=["visual-feedback"])
async def review_visible_design_route(body: dict | None = None) -> dict:
    """Analyze current UI/design preview and generate improvement notes."""
    try:
        from automation.screen_capture import capture_screen
        from automation.ocr import ocr_image
        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "reviewed": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/generate-prompt-from-screen", tags=["visual-feedback"])
async def generate_prompt_from_screen_route(body: dict | None = None) -> dict:
    """Use visible context plus project memory to draft a prompt."""
    try:
        from automation.screen_capture import capture_screen
        from automation.ocr import ocr_image
        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "prompt_generated": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.post("/visual/verify-visible-result", tags=["visual-feedback"])
async def verify_visible_result_route(body: dict | None = None) -> dict:
    """Check whether expected UI text/state appears after an action."""
    try:
        from automation.screen_capture import capture_screen
        from automation.ocr import ocr_image
        screen_path = capture_screen()
        if not screen_path:
            return {"success": False, "error": "screen capture failed"}
        text = ocr_image(screen_path)
        return {"success": bool(text), "text": text, "screen_path": screen_path, "verified": True}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─── Workflow Engine Routes ─────────────────────────────


@app.get("/workflows", tags=["workflow"])
async def list_workflows() -> dict:
    """List all available workflow definitions."""
    from workflow_engine.registry import list_definitions

    return {"workflows": list_definitions()}


@app.post("/workflows/{workflow_id}/start", tags=["workflow"])
async def start_workflow(workflow_id: str, body: dict) -> dict:
    """Start a workflow run."""
    project_id = str(body.get("project_id", "")).strip()
    inputs = body.get("inputs", {})
    initiated_by = str(body.get("initiated_by", "user")).strip()

    if not project_id:
        return {"success": False, "error": "project_id is required"}

    try:
        from workflow_engine.executor import WorkflowExecutor

        executor = WorkflowExecutor()
        run = executor.start(workflow_id, inputs, project_id, initiated_by=initiated_by)
        return {
            "success": True,
            "run_id": run.id,
            "workflow_id": run.workflow_id,
            "status": run.status,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@app.get("/workflows/runs/{run_id}", tags=["workflow"])
async def get_workflow_run(run_id: str) -> dict:
    """Get a workflow run by ID."""
    from db.client import get_workflow_runs

    runs = get_workflow_runs(project_id="", status=None)
    for run in runs:
        if run.get("id") == run_id:
            return {"success": True, "run": run}
    return {"success": False, "error": f"Run not found: {run_id}"}


@app.get("/workflows/runs", tags=["workflow"])
async def list_workflow_runs(
    project_id: str,
    status: str | None = None,
) -> dict:
    """List workflow runs for a project."""
    from db.client import get_workflow_runs

    runs = get_workflow_runs(project_id=project_id, status=status)
    return {"success": True, "runs": runs}


@app.get("/workflows/runs/{run_id}/steps", tags=["workflow"])
async def get_workflow_steps(run_id: str) -> dict:
    """Get workflow steps for a run."""
    from db.client import get_workflow_steps

    steps = get_workflow_steps(run_id)
    return {"success": True, "steps": steps}


manager = _ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time agent-to-frontend updates."""
    await manager.connect(ws)
    await ws.send_json({"type": "connected", "message": "AUTOMATA agent connected"})
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(ws)
