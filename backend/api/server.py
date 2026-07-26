"""
api/server.py - AUTOMATA local FastAPI server.

Owns: HTTP and WebSocket API exposed to the React/Tauri frontend.
Never: Contains memory, reasoning, or OS-action business logic.
Ref: ARCHITECTURE.md section 3.1, section 3.2, TECH_STACK.md frontend transport.
"""

import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from logging_config import configure_logging

configure_logging()

from config import settings
from db.client import health_check as db_health_check

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
    allow_origins=["http://localhost:1420", "http://localhost:5173", "tauri://localhost"],
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
