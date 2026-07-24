"""
api/server.py — AUTOMATA local FastAPI server.

Owns:    The HTTP + WebSocket API exposed to the React/Tauri frontend.
         All business logic is delegated to backend modules — this file
         is thin routing only, per CONVENTIONS.md §3.
Never:   Must not contain memory, reasoning, or OS-action logic.
         Must not talk to CockroachDB or Bedrock directly.
         Frontend is the ONLY caller of this API — no external exposure.
Ref:     ARCHITECTURE.md §3.1, §3.2, TECH_STACK.md "Frontend ↔ Python transport".

Routes (Phase 0 — placeholders; implement in their respective phases):
  GET  /health                  → DB + Bedrock status (Phase 0)
  GET  /projects                → list projects (Phase 1)
  POST /projects                → register a project (Phase 1)
  GET  /projects/{id}/brief     → morning brief for today (Phase 2)
  POST /projects/{id}/restore   → trigger workspace restore (Phase 3)
  POST /query                   → natural-language memory query (Phase 2)
  WS   /ws                      → live updates to frontend (Phase 3+)
"""

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configure logging on import in case server.py is the uvicorn entry point.
from logging_config import configure_logging

configure_logging()

from db.client import health_check as db_health_check
from config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AUTOMATA Agent API",
    description="Local API for the AUTOMATA persistent memory developer agent.",
    version="0.1.0",
    docs_url="/docs",       # Swagger UI available at http://127.0.0.1:8000/docs
    redoc_url="/redoc",
)

# Allow the Tauri WebView and localhost dev server to call this API.
# Restricted to localhost — this API is never exposed externally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://localhost:5173", "tauri://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
async def health() -> dict:
    """
    Returns the current status of all backend services.
    Used by the frontend to show connection indicators.
    """
    db_status = db_health_check()
    return {
        "api": "ok",
        "db": db_status,
        "bedrock": "configured" if settings.bedrock_available else "not_configured",
        "embedding": "configured" if settings.embedding_available else "not_configured",
    }


# ─── Projects (Phase 1 stubs) ─────────────────────────────────────────────────

@app.get("/projects", tags=["projects"])
async def list_projects() -> dict:
    """Phase 1: Returns list of tracked projects from CockroachDB."""
    logger.debug("GET /projects — Phase 0 stub")
    return {"projects": [], "note": "Phase 0 stub — implement in Phase 1"}


@app.post("/projects", tags=["projects"])
async def register_project(body: dict) -> dict:
    """Phase 1: Register a new project for memory tracking."""
    logger.debug("POST /projects — Phase 0 stub | body=%s", body)
    return {"id": None, "note": "Phase 0 stub — implement in Phase 1"}


# ─── Morning Brief (Phase 2 stub) ─────────────────────────────────────────────

@app.get("/projects/{project_id}/brief", tags=["memory"])
async def get_morning_brief(project_id: str) -> dict:
    """
    Phase 2: Retrieves or generates the morning brief for the given project.
    Powered by memory retrieval (recent sessions, commits, todos) + Bedrock reasoning.
    """
    logger.debug("GET /projects/%s/brief — Phase 0 stub", project_id)
    return {
        "project_id": project_id,
        "brief": None,
        "note": "Phase 0 stub — implement in Phase 2",
    }


# ─── Workspace Restore (Phase 3 stub) ────────────────────────────────────────

@app.post("/projects/{project_id}/restore", tags=["automation"])
async def restore_workspace(project_id: str) -> dict:
    """
    Phase 3: Triggers Autonomous Workspace Recovery for the given project.
    Returns per-step status (git checkout, terminal, servers, editor, browser).
    """
    logger.debug("POST /projects/%s/restore — Phase 0 stub", project_id)
    from automation.restore import restore_workspace as _restore
    return _restore(project_id=project_id)


# ─── Memory Query (Phase 2 stub) ──────────────────────────────────────────────

@app.post("/query", tags=["memory"])
async def query_memory(body: dict) -> dict:
    """
    Phase 2: Natural-language memory query.
    Body: {'question': str, 'project_id': str (optional)}
    Response: {'answer': str, 'memories': list, 'grounded': bool}
    """
    question = body.get("question", "")
    project_id = body.get("project_id")
    logger.debug("POST /query — Phase 0 stub | question='%s...'", question[:60])
    return {
        "answer": None,
        "memories": [],
        "grounded": False,
        "note": "Phase 0 stub — implement in Phase 2",
    }


# ─── WebSocket (Phase 3+ live updates) ────────────────────────────────────────

class _ConnectionManager:
    """Manages active WebSocket connections for broadcasting live agent events."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info("WebSocket client connected | total=%d", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        logger.info("WebSocket client disconnected | total=%d", len(self.active))

    async def broadcast(self, message: dict) -> None:
        """Broadcast a JSON message to all connected clients."""
        import json
        payload = json.dumps(message)
        for ws in list(self.active):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(ws)


manager = _ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    WebSocket endpoint for real-time agent → frontend updates.

    Phase 3+: Agent pushes restore-progress steps, autonomous action notifications,
    and morning brief ready events over this channel.
    Phase 0: Accepts connection, echoes a ready message, then holds open.
    """
    await manager.connect(ws)
    await ws.send_json({"type": "connected", "message": "AUTOMATA agent connected"})
    try:
        while True:
            data = await ws.receive_text()
            # Echo back in Phase 0 — Phase 3+ will route messages to agent actions.
            await ws.send_json({"type": "echo", "data": data})
    except WebSocketDisconnect:
        manager.disconnect(ws)
