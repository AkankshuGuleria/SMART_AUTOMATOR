"""
api/server.py - AUTOMATA local FastAPI server.

Owns: HTTP and WebSocket API exposed to the React/Tauri frontend.
Never: Contains memory, reasoning, or OS-action business logic.
Ref: ARCHITECTURE.md section 3.1, section 3.2, TECH_STACK.md frontend transport.
"""

import json
import logging
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
    }


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


@app.get("/projects/{project_id}/brief", tags=["memory"])
async def get_morning_brief(project_id: str) -> dict:
    """
    Return the latest stored morning brief plus recent raw memory context.

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
    if result is None:
        result = synthesize_explanation(project_id, repo_path)
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
        answer = invoke_reasoning(
            system_prompt=(
                "You are AUTOMATA's Reasoning Engine. Answer tersely using only "
                "retrieved project memory. If memory is incomplete, say what is "
                "missing without inventing details."
            ),
            user_message=question,
            retrieved_memories=memories,
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
    from automation.command_executor import CommandExecutor

    message = str(body.get("message", "")).strip()
    project_id = body.get("project_id")
    active_project_id = body.get("active_project_id")
    allow_execute = bool(body.get("allow_execute", False))

    if not message:
        return {"error": "message is required"}

    parser = IntentParser()
    parsed = parser.parse(message, active_project_id=active_project_id or project_id)
    executed_action = None
    error = None

    if parsed.intent == IntentType.UNKNOWN:
        response = {
            "intent": "general_chat",
            "reply": "I can help with projects, restoring workspaces, running commands, or explaining code. Try: \"resume where I left off\" or \"run tests\".",
            "actions": [],
        }
    else:
        try:
            plan_result = plan(
                trigger=f"chat:{parsed.intent}",
                context={"message": message, "parsed": parsed.params or {}, "project_id": parsed.project_id},
            )
            executed_actions = []
            for action in plan_result.get("actions", []):
                if action.get("executed"):
                    executed_actions.append(action)
            response = {
                "intent": parsed.intent.value,
                "reply": f"Intent: {parsed.intent.value}. Executed {len(executed_actions)} action(s).",
                "actions": plan_result.get("actions", []),
                "executed_actions": executed_actions,
            }
        except Exception as exc:
            logger.exception("chat: planner failed")
            response = {
                "intent": parsed.intent.value,
                "reply": f"Intent recognized as {parsed.intent.value}, but planning failed.",
                "actions": [],
                "executed_actions": [],
            }
            error = str(exc)

    return {
        "intent": parsed.intent.value,
        "confidence": parsed.confidence,
        "reply": response.get("reply", ""),
        "actions": response.get("actions", []),
        "executed_actions": response.get("executed_actions", []),
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


@app.get("/activity-feed", tags=["system"])
async def activity_feed(limit: int = 50, project_id: Optional[str] = None) -> dict:
    """Return chronological activity/audit entries for the dashboard/feed."""
    from db.client import get_decisions, get_commits, get_terminal_commands

    feed = []
    try:
        feed.extend(get_decisions(project_id=project_id, limit=limit) or [])
    except Exception:
        pass
    try:
        feed.extend(get_commits(project_id=project_id, limit=limit) or [])
    except Exception:
        pass
    try:
        feed.extend(get_terminal_commands(project_id=project_id, limit=limit) or [])
    except Exception:
        pass
    feed.sort(key=lambda x: x.get("decided_at") or x.get("committed_at") or x.get("run_at") or "", reverse=True)
    return {"items": feed[:limit]}


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
