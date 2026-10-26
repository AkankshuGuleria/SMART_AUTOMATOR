"""
api/server.py - AUTOMATA local FastAPI server.

Owns: HTTP and WebSocket API exposed to the React/Tauri frontend.
Never: Contains memory, reasoning, or OS-action business logic.
Ref: ARCHITECTURE.md section 3.1, section 3.2, TECH_STACK.md frontend transport.
"""

import asyncio
import logging
import os
import re
import subprocess
import threading
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from automation.no_console import install as _hide_child_consoles
from logging_config import configure_logging

_hide_child_consoles()  # also when the app is started as `uvicorn api.server:app`

configure_logging()

from config import settings  # noqa: E402
from db.client import (
    get_architecture_notes,
    get_commits,
    get_commits_over_time,
    get_daily_brief,
    get_file_edits,
    get_file_edits_over_time,
    get_project,
    get_projects,
    get_sessions,
    get_terminal_commands,
    get_todos,
    get_top_files,
    insert_project,
    upsert_daily_brief,
)
from db.client import (
    get_decisions as get_decision_entries,
)
from db.client import (
    health_check as db_health_check,
)

logger = logging.getLogger(__name__)

# Hard wall-clock timeout for a single reasoning call in HTTP routes (seconds).
# Prevents a slow or hung provider from blocking the API endpoint indefinitely.
_ROUTE_LLM_TIMEOUT: float = 45.0

# Worker threads that outlived their route timeout are tracked here. Python
# cannot kill a running thread, so the only safe cleanup is to drop the
# reference once the thread finally returns — without this registry every
# timed-out call leaks a live thread for the lifetime of the process.
_TIMED_OUT_THREADS: set[threading.Thread] = set()
_TIMED_OUT_THREADS_LOCK = threading.Lock()

# Event loop captured at startup for cross-thread WebSocket broadcasts.
_event_loop: asyncio.AbstractEventLoop | None = None


def _lingering_timeout_threads() -> list[threading.Thread]:
    """Return the worker threads that are still running past their timeout."""
    with _TIMED_OUT_THREADS_LOCK:
        return list(_TIMED_OUT_THREADS)


def _call_with_timeout(fn, on_timeout=None, **kwargs) -> Any:
    """Run *fn* in a daemon thread and return its result, or None on timeout.

    If *on_timeout* is provided and the timeout fires, it is called before
    returning None — allowing the caller to set cooldowns or other state.

    A timed-out worker cannot be killed, so it is registered in
    _TIMED_OUT_THREADS and logged as a warning. The worker removes itself from
    the registry as soon as it finishes, so the registry only ever holds
    threads that are genuinely still running.
    """
    result_box: dict[str, Any] = {}
    done = threading.Event()

    def _target() -> None:
        try:
            result_box["value"] = fn(**kwargs)
        except Exception as exc:
            result_box["error"] = exc
        finally:
            done.set()
            with _TIMED_OUT_THREADS_LOCK:
                _TIMED_OUT_THREADS.discard(threading.current_thread())

    t = threading.Thread(
        target=_target,
        daemon=True,
        name=f"route-llm-{getattr(fn, '__name__', 'call')}",
    )
    t.start()
    if not done.wait(timeout=_ROUTE_LLM_TIMEOUT):
        with _TIMED_OUT_THREADS_LOCK:
            # Re-check under the lock: the worker may have finished between the
            # timeout firing and this block, in which case it must not linger.
            still_running = not done.is_set()
            if still_running:
                _TIMED_OUT_THREADS.add(t)
        if still_running:
            logger.warning(
                "Route LLM call timed out after %.1fs — worker thread %s still running",
                _ROUTE_LLM_TIMEOUT,
                t.name,
            )
        if on_timeout:
            on_timeout()
        return None
    if "error" in result_box:
        logger.warning("Route LLM call raised — %s", result_box["error"])
        return None
    return result_box.get("value")


def _generate_chat_reply(message: str, project_id: str) -> tuple[str | None, list[dict], str]:
    """Fallback chat handler for UNKNOWN / GENERAL_CHAT intents.

    Called only when IntentParser returns UNKNOWN or GENERAL_CHAT (i.e. the
    planner has no specific trigger for this message). Delegates to
    _grounded_query so the answer is always grounded in retrieved memory,
    never keyword-matched ad-hoc.

    Returns (reply_text, actions, intent). 'actions' is always [] here —
    action cards are produced by plan() for recognised intents, not here.
    """
    msg_lower = message.lower().strip()

    # Greetings — reply directly without hitting the LLM or the DB.
    _GREETINGS = {
        "hello",
        "hi",
        "hey",
        "howdy",
        "good morning",
        "good afternoon",
        "good evening",
        "greetings",
        "sup",
        "yo",
    }
    greeting_check = msg_lower.replace("automata", "").strip()
    if greeting_check in _GREETINGS or greeting_check.split()[0:1] == ["hello"]:
        return "Hello! I'm AUTOMATA. What can I help you with today?", [], "general_assistant"

    reply, _sources, ok = _grounded_query(message, project_id)
    intent = "general_assistant" if ok else "unavailable"
    return reply, [], intent


_BACKEND_CACHE: dict[str, Any] = {"at": -1e9, "value": False}
_BACKEND_CACHE_TTL = 30.0


def _backend_available() -> bool:
    """Quick check: is at least one LLM backend reachable right now?

    The Ollama probe can take up to 2 s when it is not running, and polling
    UIs call this every few seconds, so the answer is cached briefly.
    """
    if time.monotonic() - float(_BACKEND_CACHE["at"]) < _BACKEND_CACHE_TTL:
        return bool(_BACKEND_CACHE["value"])
    value = _probe_backend_available()
    _BACKEND_CACHE.update(at=time.monotonic(), value=value)
    return value


def _probe_backend_available() -> bool:
    from ai.bedrock_client import _get_ollama_available

    if getattr(settings, "bedrock_available", False):
        return True
    cloud_keys = [
        settings.groq_api_key,
        settings.gemini_api_key,
        settings.nvidia_api_key,
        settings.minimax_api_key,
        settings.openrouter_api_key,
        settings.cohere_api_key,
    ]
    if any(bool(k) for k in cloud_keys):
        return True
    return _get_ollama_available()


def _grounded_query(question: str, project_id: str) -> tuple[str, list[dict], bool]:
    """Retrieve memories and generate a grounded answer via the reasoning engine."""
    from ai.bedrock_client import invoke_reasoning
    from memory.retrieval import retrieve_by_vector, retrieve_recent

    memories: list[dict] = []
    # 1) Local memory (offline, fast): BM25 + local vectors when available.
    try:
        from ai.bedrock_client import invoke_local_embedding
        from memory.local_store import get_store

        local_vec = None
        emb = invoke_local_embedding([question])
        if emb:
            local_vec = emb[0][0]
        memories = get_store().search(question, project_id=project_id, limit=6, query_embedding=local_vec)
    except Exception as exc:
        logger.debug("local memory search failed — %s", exc)
    # 2) Cloud vector retrieval (requires DB + embedding backend)
    try:
        cloud = retrieve_by_vector(
            question,
            ["commits", "todos", "file_edits", "architecture_notes"],
            project_id=project_id,
            top_k=5,
        )
        seen = {" ".join(str(m.get("content") or "").split()).lower() for m in memories}
        for m in cloud or []:
            sig = " ".join(str(m.get("content") or "").split()).lower()
            if sig and sig not in seen:  # the cloud copy often repeats a local row
                seen.add(sig)
                memories.append(m)
    except Exception:
        pass

    # Fallback: recent memory (works without embeddings or even DB connection)
    if not memories:
        for table in ("commits", "todos", "file_edits", "architecture_notes"):
            try:
                memories.extend(retrieve_recent(project_id, table, limit=3))
            except Exception:
                pass

    # Cap token utilisation: keep only top memories, truncate content.
    memories = memories[:8]
    for m in memories:
        if isinstance(m.get("content"), str) and len(m["content"]) > 400:
            m["content"] = m["content"][:400] + "…"

    stack = ""
    try:
        from intelligence.profile import prompt_context

        stack = "\n\nProject facts (detected from its files):\n" + prompt_context(project_id, 700)
    except Exception:
        pass
    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Answer the developer's question "
        "using the provided memory context when relevant. If the context doesn't "
        "contain the answer, say 'I don't have enough memory to answer that.' "
        "Be direct. No chatbot filler, no fabricated details." + stack
    )

    from ai.bedrock_client import _all_llm_backends_exhausted

    reply = _call_with_timeout(
        invoke_reasoning,
        system_prompt=system_prompt,
        user_message=question,
        retrieved_memories=memories,
        reasoning_mode=CURRENT_REASONING_MODE,
        on_timeout=_all_llm_backends_exhausted,
    )

    if reply:
        return (
            reply,
            [
                {
                    "type": m.get("table", "memory"),
                    "summary": m.get("content", ""),
                    "relevance": m.get("score", 0.9),
                }
                for m in memories[:5]
            ],
            True,
        )

    # No backend — return a clear, user-facing message.
    hint = (
        "I couldn't generate a response — no AI backend is available.\n\n"
        "You can still run Ollama locally for free:\n"
        "  1. Install from https://ollama.com\n"
        "  2. Run: ollama pull qwen2.5:7b && ollama serve\n"
        "  3. Restart AUTOMATA\n\n"
        "Or add an API key (OpenRouter, Groq, Gemini, Cohere, NVIDIA) to backend/.env"
    )
    return (
        hint,
        [
            {
                "type": m.get("table", "memory"),
                "summary": m.get("content", ""),
                "relevance": m.get("score", 0.9),
            }
            for m in memories[:5]
        ],
        False,
    )


class WebSocketManager:
    """Manages WebSocket connections for real-time agent events."""

    def __init__(self) -> None:
        self._active_connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active_connections.append(ws)
        logger.info("WebSocket: client connected (%d total)", len(self._active_connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active_connections:
            self._active_connections.remove(ws)
        logger.info("WebSocket: client disconnected (%d remaining)", len(self._active_connections))

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to all connected clients."""
        dead: list[WebSocket] = []
        for ws in self._active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


_ws_manager = WebSocketManager()


def broadcast_sync(message: dict) -> None:
    """Broadcast a WebSocket message from any thread (best effort)."""
    if _event_loop and not _event_loop.is_closed():
        asyncio.run_coroutine_threadsafe(_ws_manager.broadcast(message), _event_loop)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Start background services with the API; stop them on shutdown."""
    global _event_loop
    from monitoring.app_usage import start_tracker, stop_tracker
    from monitoring.system_metrics import start_sampler, stop_sampler

    _event_loop = asyncio.get_running_loop()
    await asyncio.to_thread(_resolve_default_project_id)
    start_sampler()
    start_tracker()
    background = os.environ.get("AUTOMATA_DISABLE_BACKGROUND", "") != "1"
    if background:
        from memory.sync import start_sync
        from tasks.engine import recover_interrupted
        from workspace.capture_manager import get_manager
        from workspace.snapshot import start_snapshots

        start_sync()
        await asyncio.to_thread(get_manager().start_default)
        start_snapshots()
        recover_interrupted()
    try:
        yield
    finally:
        if background:
            from memory.sync import stop_sync
            from workspace.capture_manager import get_manager
            from workspace.snapshot import stop_snapshots

            stop_snapshots(final=True)
            get_manager().stop()
            stop_sync()
        stop_tracker()
        stop_sampler()


app = FastAPI(
    lifespan=_lifespan,
    title="AUTOMATA Agent API",
    description="Local API for the AUTOMATA persistent memory developer agent.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from api.workspace_routes import router as _workspace_router  # noqa: E402

app.include_router(_workspace_router)

from security.http_guard import ALLOWED_ORIGINS, LocalOnlyGuard  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),  # Tauri 2 on Windows serves the app from http(s)://tauri.localhost
    allow_credentials=False,  # no cookies or auth headers are used
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
# Outermost: refuse requests from other websites and DNS-rebinding before anything runs.
app.add_middleware(LocalOnlyGuard)

# ─── Global State ──────────────────────────────────────────────────────────────
CURRENT_REASONING_MODE = settings.reasoning_mode or "auto"
DEFAULT_PROJECT_ID: str | None = None
DEFAULT_PROJECT: dict | None = None


def _resolve_default_project_id() -> None:
    global DEFAULT_PROJECT_ID, DEFAULT_PROJECT
    try:
        projects = get_projects() or []
    except Exception as exc:
        logger.warning("startup: failed to fetch projects — %s", exc)
        projects = []
    if projects:
        first = projects[0]
        DEFAULT_PROJECT_ID = str(first.get("id")) if first.get("id") is not None else None
        DEFAULT_PROJECT = {**first, "id": DEFAULT_PROJECT_ID}
        logger.info("startup: resolved DEFAULT_PROJECT_ID=%s", DEFAULT_PROJECT_ID)
    else:
        DEFAULT_PROJECT_ID = None
        DEFAULT_PROJECT = None
        logger.warning("startup: no project registered")


_STARTED_AT = datetime.now(UTC)
_STARTED_MONOTONIC = time.monotonic()

# ─── System Routes ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
def health() -> dict:
    """Return local agent, database, and reasoning-backend health."""
    import time as _time

    from ai.bedrock_client import (
        _EMBEDDING_COOLDOWN_SECONDS,
        _LLM_COOLDOWN_SECONDS,
        _last_embedding_fail_time,
        _last_llm_fail_time,
    )

    emb_cooldown_remaining = max(
        0, _EMBEDDING_COOLDOWN_SECONDS - (_time.monotonic() - _last_embedding_fail_time)
    )
    llm_cooldown_remaining = max(
        0, _LLM_COOLDOWN_SECONDS - (_time.monotonic() - _last_llm_fail_time)
    )

    emb_status = "configured" if settings.embedding_available else "not_configured"
    if emb_cooldown_remaining > 0:
        emb_status = "cooldown"

    return {
        "api": "ok",
        "db": db_health_check(),
        "bedrock": "configured" if settings.bedrock_available else "not_configured",
        "embedding": emb_status,
        "reasoning_mode": CURRENT_REASONING_MODE,
        "embedding_cooldown_seconds": round(emb_cooldown_remaining, 1),
        "llm_cooldown_seconds": round(llm_cooldown_remaining, 1),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket endpoint for real-time agent events.

    The frontend (AgentSocket in lib/api.ts) connects here to receive
    live updates: connection ack, restore progress, brief readiness,
    and autonomous actions.
    """
    await _ws_manager.connect(ws)
    try:
        # Send immediate 'connected' event
        await ws.send_json(
            {
                "type": "connected",
                "data": {"status": "ok", "timestamp": datetime.now(UTC).isoformat()},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            try:
                data = await ws.receive_text()
                # Echo back so the frontend knows the channel is live
                await ws.send_json(
                    {
                        "type": "echo",
                        "data": {"message": data},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            except WebSocketDisconnect:
                _ws_manager.disconnect(ws)
                break
            except Exception:
                _ws_manager.disconnect(ws)
                break
    except WebSocketDisconnect:
        _ws_manager.disconnect(ws)
    except Exception as exc:
        _ws_manager.disconnect(ws)
        logger.warning("WebSocket error: %s", exc)


@app.get("/settings/reasoning-mode", tags=["system"])
def get_reasoning_mode() -> dict:
    return {"reasoning_mode": CURRENT_REASONING_MODE}


@app.post("/settings/reasoning-mode", tags=["system"])
def set_reasoning_mode(body: dict = Body(...)) -> dict:
    global CURRENT_REASONING_MODE
    from ai.bedrock_client import reset_embedding_cooldown, reset_llm_cooldown

    CURRENT_REASONING_MODE = body.get("reasoning_mode", "auto")
    # Reset cooldowns so backends are retried immediately with the new mode.
    reset_embedding_cooldown()
    reset_llm_cooldown()
    return {"reasoning_mode": CURRENT_REASONING_MODE}


@app.post("/settings/reset-cooldowns", tags=["system"])
def reset_cooldowns() -> dict:
    """Reset embedding and LLM cooldowns so backends are retried on next call."""
    from ai.bedrock_client import reset_embedding_cooldown, reset_llm_cooldown

    reset_embedding_cooldown()
    reset_llm_cooldown()
    return {"status": "ok", "cooldowns_reset": True}


_TOOLS_CACHE: dict[str, Any] = {"at": 0.0, "value": None}
_TOOLS_CACHE_TTL = 300.0  # tool versions rarely change; spawning 4 processes is slow


@app.get("/tools/status", tags=["system"])
def get_tools_status() -> dict:
    cached = _TOOLS_CACHE["value"]
    if cached is not None and time.monotonic() - _TOOLS_CACHE["at"] < _TOOLS_CACHE_TTL:
        return cached
    result = _probe_tools()
    _TOOLS_CACHE.update(at=time.monotonic(), value=result)
    return result


def _probe_tools() -> dict:
    import shutil

    tools = [
        {"name": "git", "command": "git", "version_flag": "--version"},
        {"name": "python", "command": "python", "version_flag": "--version"},
        {"name": "node", "command": "node", "version_flag": "--version"},
        {
            "name": "powershell",
            "command": "powershell",
            "version_flag": '-Command "$PSVersionTable.PSVersion.ToString()"',
        },
        {"name": "cockroachdb", "command": None, "version_flag": None},
    ]

    results = []
    for tool in tools:
        if tool["command"] is None:
            available = settings.db_available
            version = "configured" if available else "not configured"
        else:
            path = shutil.which(tool["command"])
            available = path is not None
            version = ""
            if available and tool["version_flag"]:
                try:
                    proc = subprocess.run(
                        [tool["command"]] + tool["version_flag"].split(),
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    version = proc.stdout.strip().splitlines()[0] if proc.stdout else ""
                except Exception:
                    version = "unknown"
            elif available:
                version = "available"
        results.append(
            {
                "name": tool["name"],
                "available": available,
                "version": version,
            }
        )

    return {"tools": results}


def _safe_fetch(fetch_fn, *args, default=None, **kwargs):
    """Return a DB/API result without letting one failing source break a route."""
    try:
        return fetch_fn(*args, **kwargs)
    except Exception as exc:
        logger.warning(
            "safe fetch failed for %s — %s", getattr(fetch_fn, "__name__", fetch_fn), exc
        )
        return default


def _project_repo_path(project_id: str | None) -> str:
    """Resolve a repo path for diagnostic commands without requiring DB availability."""
    if project_id:
        project = _safe_fetch(get_project, project_id, default=None)
        if project and project.get("repo_path"):
            return str(project["repo_path"])
    if DEFAULT_PROJECT and DEFAULT_PROJECT.get("repo_path"):
        return str(DEFAULT_PROJECT["repo_path"])
    return ""


def _run_git(repo_path: str, args: list[str], timeout: int = 5) -> dict[str, Any]:
    """Run a read-only git command and return a structured result."""
    if not repo_path or not os.path.isdir(repo_path):
        return {"ok": False, "stdout": "", "stderr": "Repository path not found.", "exit_code": 1}
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
        }
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "exit_code": 1}


def _activity_rows(
    project_id: str, limit: int
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Fetch activity rows with per-source failure isolation."""
    return (
        _safe_fetch(get_commits, project_id, limit=limit, default=[]) or [],
        _safe_fetch(get_file_edits, project_id, limit=limit, default=[]) or [],
        _safe_fetch(get_terminal_commands, project_id, limit=limit, default=[]) or [],
        _safe_fetch(get_decision_entries, project_id, limit=limit, default=[]) or [],
    )


# ─── Projects Routes ───────────────────────────────────────────────────────────


@app.get("/projects", tags=["projects"])
def list_projects() -> dict:
    projects = _safe_fetch(get_projects, default=[]) or []
    return {"projects": projects}


@app.post("/projects", tags=["projects"])
def create_project(body: dict = Body(...)) -> dict:
    name = str(body.get("name") or "").strip()
    repo_path = str(body.get("repo_path") or "").strip().strip('"')
    remote_url = str(body.get("remote_url") or "").strip()
    if not repo_path:
        raise HTTPException(status_code=422, detail="repo_path is required")
    if not os.path.isdir(repo_path):
        raise HTTPException(status_code=422, detail=f"Folder not found: {repo_path}")
    repo_path = os.path.abspath(repo_path)
    name = name or os.path.basename(os.path.normpath(repo_path)) or "New Project"
    wanted = os.path.normcase(repo_path)
    for existing in _safe_fetch(get_projects, default=[]) or []:
        existing_path = str(existing.get("repo_path") or "")
        if existing_path and os.path.normcase(os.path.abspath(existing_path)) == wanted:
            return {"project": existing, "existing": True}

    project_id = insert_project(name, repo_path, remote_url)
    if not project_id:
        raise HTTPException(
            status_code=503, detail="Failed to register project — is the database connected?"
        )
    project = get_project(project_id) or {
        "id": project_id,
        "name": name,
        "repo_path": repo_path,
        "remote_url": remote_url,
        "created_at": datetime.now(UTC).isoformat(),
    }
    return {"project": project}


@app.get("/projects/{project_id}/brief", tags=["projects"])
def get_morning_brief(project_id: str) -> dict:
    brief = _safe_fetch(get_daily_brief, project_id, default=None)
    if not brief:
        from memory.local_store import get_store

        brief = get_store().get_value(f"brief:{project_id}")
    return {"brief": brief}


# ─── Morning Brief Parsing ─────────────────────────────────────────────────────

_BULLET_PREFIXES = ("•", "‣", "⁃", "▪", "-", "*", "–", "—")
_PENDING_SECTION_RE = re.compile(
    r"^\s*(pending(?:\s+items?)?|todo(?:s)?|next\s+steps?)\s*:?\s*$",
    re.IGNORECASE,
)
_SECTION_HEADER_RE = re.compile(r"^\s*[A-Za-z][A-Za-z /&_-]{0,40}\s*:\s*$")
_MAX_PENDING_ITEM_LENGTH = 200

# Bullets that are part of a brief's narration rather than an actionable TODO.
_NON_ITEM_RE = re.compile(
    r"^(?:last\s+edited\s*:|no\s+(?:recent\s+)?activity|no\s+pending\s+items?|\d+\s+\w+)",
    re.IGNORECASE,
)


def _is_section_header(line: str) -> bool:
    """True when *line* looks like the start of a new reply section."""
    if _SECTION_HEADER_RE.match(line):
        return True
    stripped = line.rstrip(":").strip()
    return bool(stripped) and stripped.isupper() and len(stripped) <= 40


def _strip_bullet(line: str) -> str:
    """Remove a leading bullet marker from *line*."""
    stripped = line.strip()
    for prefix in _BULLET_PREFIXES:
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return stripped


def _normalize_item(text: str) -> str:
    """Case/whitespace-insensitive key used for de-duplication."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _extract_pending_items(reply: str, existing: list[str] | None = None) -> list[str]:
    """Extract only real TODO items from an LLM morning-brief reply.

    The prompt asks the model for a "PENDING ITEMS:" section; only the lines
    inside that section are treated as TODO items. Prose such as "Good
    Morning!", the summary sentences and the closing question are ignored. If
    the model omits the section, bullet lines are the fallback — plain prose
    is never treated as a TODO.

    Items already present in *existing* (case-insensitive) are dropped so the
    brief never repeats what is already listed.
    """
    if not reply:
        return []

    section_items: list[str] = []
    bullet_items: list[str] = []
    in_section = False
    seen_section = False

    for raw_line in reply.strip().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if _PENDING_SECTION_RE.match(line):
            in_section = True
            seen_section = True
            continue

        if in_section and _is_section_header(line):
            in_section = False
            continue

        if line.startswith(_BULLET_PREFIXES):
            bullet_items.append(_strip_bullet(line))
        if in_section:
            section_items.append(_strip_bullet(line))

    candidates = section_items if seen_section else bullet_items

    seen: set[str] = {_normalize_item(item) for item in (existing or []) if item}

    items: list[str] = []
    for candidate in candidates:
        item = candidate.strip()
        if not item or len(item) > _MAX_PENDING_ITEM_LENGTH:
            continue
        if item.endswith("?"):
            # Closing question ("Would you like me to restore the project?").
            continue
        if _NON_ITEM_RE.match(item):
            # Narration bullets (counts, "Last edited: ...") are not TODOs.
            continue
        key = _normalize_item(item)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


def _fallback_brief_text(
    commits: list[dict],
    file_edits: list[dict],
    pending_items: list[str],
    last_edited_file: str | None,
) -> str:
    """Build a plain-text brief from stored activity when the LLM is unavailable.

    Used when the reasoning call times out or no backend is reachable. The
    brief must never be empty — the UI renders `brief_text` directly.
    """
    parts: list[str] = []

    commits_count = len(commits)
    if commits_count:
        parts.append(f"{commits_count} commit{'s' if commits_count != 1 else ''} recorded.")
    else:
        parts.append("No commits recorded.")

    recent = ""
    if commits:
        recent = str(commits[0].get("message", "") or "").strip()
    if not recent and file_edits:
        latest_edit = file_edits[0]
        summary = str(latest_edit.get("change_summary", "") or "").strip()
        path = str(latest_edit.get("file_path", "") or "").strip()
        recent = summary or (f"Edited {path}" if path else "")
    if recent:
        recent = recent.rstrip(".")
        if len(recent) > 140:
            recent = recent[:137].rstrip() + "..."
        parts.append(f"Recent: {recent}.")

    todos_count = len(pending_items)
    if todos_count:
        parts.append(f"{todos_count} pending TODO{'s' if todos_count != 1 else ''}.")

    if last_edited_file:
        parts.append(f"Last edited: {last_edited_file}.")

    return " ".join(parts) if parts else "No recent activity recorded."


@app.post("/projects/{project_id}/brief/generate", tags=["projects"])
def generate_morning_brief(project_id: str) -> dict:
    from ai.bedrock_client import invoke_reasoning

    commits = _safe_fetch(get_commits, project_id, limit=20, default=[]) or []
    file_edits = _safe_fetch(get_file_edits, project_id, limit=20, default=[]) or []
    todos = _safe_fetch(get_todos, project_id, default=[]) or []
    if not commits and not file_edits:
        # Cloud DB down or empty: build the brief from local memory instead.
        from memory.local_store import get_store

        store = get_store()
        commits = [
            {"message": m["content"].split(": ", 1)[-1], "committed_at": m["timestamp"]}
            for m in store.recent(project_id, ["commit"], limit=20)
        ]
        file_edits = [
            {"file_path": (m["meta"] or {}).get("file_path") or m["content"].removeprefix("Edited "),
             "change_summary": m["content"], "edited_at": m["timestamp"]}
            for m in store.recent(project_id, ["file_edit"], limit=20)
        ]

    commits_count = len(commits)

    highlights: list[str] = []
    for c in commits[:3]:
        msg = c.get("message", "")
        if msg:
            highlights.append(str(msg)[:120])

    for fe in file_edits[:2]:
        path = fe.get("file_path", "")
        summary = fe.get("change_summary", "")
        if path:
            highlights.append(f"Edited {path}: {str(summary)[:80]}" if summary else f"Edited {path}")

    pending_items: list[str] = []
    for t in todos:
        if t.get("status") == "pending":
            desc = t.get("description", "")
            if desc:
                pending_items.append(str(desc)[:120])
        if len(pending_items) >= 5:
            break

    last_edited_file = None
    if file_edits:
        last_edited_file = file_edits[0].get("file_path")

    brief_date = datetime.now(UTC).strftime("%Y-%m-%d")

    system_prompt = (
        "You are AUTOMATA's Reasoning Engine. Based on the provided project activity data, "
        "generate a concise morning brief. Reply with exactly two sections:\n"
        "HIGHLIGHTS:\n- <short factual activity>\n"
        "PENDING ITEMS:\n- <one concrete todo to focus on>\n"
        "Only list items that are present in the provided data — never invent activity. "
        "Be direct and factual. No chatbot filler."
    )
    user_message = (
        f"Commits today: {commits_count}\n"
        f"Highlights so far: {', '.join(highlights[:5])}\n"
        f"Pending TODOs: {', '.join(pending_items[:5])}\n"
        f"Last edited file: {last_edited_file or 'unknown'}\n\n"
        "Generate a brief summary of today's activity and suggest pending items to focus on."
    )

    reply = _call_with_timeout(
        invoke_reasoning,
        system_prompt=system_prompt,
        user_message=user_message,
        retrieved_memories=[],
        reasoning_mode=CURRENT_REASONING_MODE,
    )

    brief_text = ""
    if reply:
        brief_text = reply.strip()
        # Only genuine TODO items are taken from the reply — model prose stays
        # in brief_text and must never inflate the pending TODO list.
        for item in _extract_pending_items(reply, existing=pending_items + highlights):
            pending_items.append(item)
    else:
        # The LLM timed out or no backend is reachable — fall back to a
        # plain-text brief built from the activity already fetched.
        brief_text = _fallback_brief_text(
            commits,
            file_edits,
            pending_items,
            last_edited_file,
        )
        logger.warning("Morning brief generated without LLM — using fallback text")

    brief_data = {
        "project_id": project_id,
        "brief_date": brief_date,
        "commits_count": commits_count,
        "highlights": highlights,
        "pending_items": pending_items,
        "last_edited_file": last_edited_file,
        "brief_text": brief_text,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    from memory.local_store import get_store, remember

    remember(project_id, "brief", brief_text, ref=f"brief:{brief_date}", meta=brief_data)
    try:
        get_store().set_value(f"brief:{project_id}", brief_data)
    except Exception:
        pass

    _safe_fetch(
        upsert_daily_brief,
        project_id=project_id,
        brief_date=brief_date,
        commits_count=commits_count,
        highlights=highlights,
        pending_items=pending_items,
        last_edited_file=last_edited_file,
        default=False,
    )

    return {"success": True, "brief": brief_data}


# ─── Restore Workspace Status ──────────────────────────────────────────────────

_RESTORE_OK = "ok"
_RESTORE_PARTIAL = "partial"
_RESTORE_ERROR = "error"

# Per-step status → severity. "skipped" is not a failure.
_RESTORE_STEP_SEVERITY = {
    "ok": 0,
    "success": 0,
    "succeeded": 0,
    "skipped": 0,
    "partial": 1,
    "error": 2,
    "failed": 2,
    "failure": 2,
}


def _overall_restore_status(steps: list[dict[str, Any]], reported: str | None = None) -> str:
    """Derive the overall restore status from the actual per-step results.

    - "ok"      — no step failed (skipped steps do not count as failures)
    - "partial" — some steps failed but at least one succeeded
    - "error"   — every attempted step failed, or no steps ran at all

    *reported* is the Automation Layer's own verdict. A fatal verdict from
    there (e.g. repo path missing) is never downgraded to "partial".
    """
    normalized = [str(step.get("status", "error")).strip().lower() for step in steps]
    failed = [s for s in normalized if _RESTORE_STEP_SEVERITY.get(s, 2) >= 2]
    succeeded = [s for s in normalized if _RESTORE_STEP_SEVERITY.get(s, 2) == 0 and s != "skipped"]

    if not steps:
        derived = _RESTORE_ERROR
    elif not failed:
        derived = _RESTORE_OK
    elif succeeded:
        derived = _RESTORE_PARTIAL
    else:
        derived = _RESTORE_ERROR

    reported_status = str(reported or "").strip().lower()
    if reported_status == "skipped" and derived == _RESTORE_OK:
        return reported_status
    if reported_status in _RESTORE_STEP_SEVERITY:
        reported_severity = _RESTORE_STEP_SEVERITY[reported_status]
        if reported_severity > _RESTORE_STEP_SEVERITY.get(derived, 2):
            return _RESTORE_ERROR if reported_severity >= 2 else _RESTORE_PARTIAL
    return derived


@app.post("/projects/{project_id}/restore", tags=["projects"])
def restore_workspace(project_id: str) -> dict:
    from automation.restore import restore_workspace as run_restore

    result = run_restore(project_id)
    if isinstance(result, dict):
        steps = list(result.get("steps", []) or [])
        reported = result.get("overall")
    else:
        steps = []
        reported = None
    overall = _overall_restore_status(steps, reported)
    return {"project_id": project_id, "steps": steps, "overall": overall}


@app.get("/projects/{project_id}/decisions", tags=["projects"])
def get_decisions(project_id: str, limit: int = 20) -> dict:
    from db import client as db_client

    return {"decisions": db_client.get_decisions(project_id=project_id, limit=limit)}


@app.get("/projects/{project_id}/sessions", tags=["projects"])
def list_sessions(project_id: str, limit: int = 20) -> dict:
    from db import client as db_client

    sessions = db_client.get_sessions(project_id=project_id)
    return {"sessions": sessions[:limit]}


@app.post("/projects/{project_id}/sessions/end", tags=["projects"])
def end_session(project_id: str, body: dict | None = Body(None)) -> dict:
    from db import client as db_client

    active = db_client.get_active_session(project_id)
    if not active:
        return {"project_id": project_id, "session_id": None, "error": "No active session"}

    session_id = str(active.get("id", ""))
    summary = (body or {}).get("summary") if body else None
    ended = db_client.end_session(project_id, session_id, summary=summary)
    if not ended:
        return {
            "project_id": project_id,
            "session_id": session_id,
            "error": "Failed to end session",
        }
    return {"ended": True, "session_id": session_id, "project_id": project_id}


@app.get("/projects/{project_id}/todos", tags=["projects"])
def list_todos(project_id: str) -> dict:
    """Return all todos for a project."""
    from db import client as db_client

    todos = db_client.get_todos(project_id=project_id)
    return {"todos": todos}


@app.post("/projects/{project_id}/todos/{todo_id}/status", tags=["projects"])
def update_todo_status_route(project_id: str, todo_id: str, body: dict = Body(...)) -> dict:
    """Update a todo's status (pending/done/resumed)."""
    from db import client as db_client

    status = str(body.get("status", "")).strip()
    if status not in {"pending", "done", "resumed"}:
        return {"error": "Invalid status", "success": False}

    ok = db_client.update_todo_status(todo_id=todo_id, status=status)
    if not ok:
        return {"error": "Todo not found", "success": False}

    return {"success": True, "todo_id": todo_id, "status": status}


@app.get("/projects/{project_id}/git/branch", tags=["projects"])
def get_git_branch(project_id: str) -> dict:
    """Return the current git branch for the project's repository."""
    repo_path = _project_repo_path(project_id)
    result = _run_git(repo_path, ["branch", "--show-current"])
    if not result.get("ok"):
        return {"branch": None, "error": result.get("stderr", "Unable to read branch")}
    return {"branch": result.get("stdout") or None, "error": None}


# ─── Activity & Memory Routes ──────────────────────────────────────────────────


@app.get("/activity/feed", tags=["activity"])
def get_activity_feed(project_id: str | None = None, limit: int = 50) -> dict:
    pid = project_id
    if not pid:
        raise HTTPException(status_code=400, detail="project_id is required")
    if not get_project(pid):
        raise HTTPException(status_code=404, detail="Project not found")

    commits, file_edits, terminal_cmds, decisions = _activity_rows(pid, limit)

    items: list[dict] = []

    for c in commits:
        items.append(
            {
                "id": str(c.get("id", "")),
                "project_id": pid,
                "kind": "commit",
                "summary": c.get("message", ""),
                "detail": c.get("author", ""),
                "created_at": c.get("committed_at"),
            }
        )

    for fe in file_edits:
        items.append(
            {
                "id": str(fe.get("id", "")),
                "project_id": pid,
                "kind": "file",
                "summary": fe.get("change_summary", ""),
                "detail": fe.get("file_path", ""),
                "created_at": fe.get("edited_at"),
            }
        )

    for tc in terminal_cmds:
        items.append(
            {
                "id": str(tc.get("id", "")),
                "project_id": pid,
                "kind": "terminal",
                "summary": tc.get("command", ""),
                "detail": tc.get("cwd", ""),
                "created_at": tc.get("run_at"),
            }
        )

    for d in decisions:
        items.append(
            {
                "id": str(d.get("id", "")),
                "project_id": pid,
                "kind": "decision",
                "summary": d.get("decision", ""),
                "detail": d.get("rationale", ""),
                "created_at": d.get("decided_at"),
            }
        )

    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    return {"items": items[:limit]}


@app.post("/query", tags=["memory"])
def query_memory(body: dict = Body(...)) -> dict:
    question = body.get("question", "")
    project_id = body.get("project_id") or None  # None when absent or null

    # Validate inputs before hitting the reasoning engine
    if not isinstance(question, str) or not question.strip():
        return {
            "answer": "Ask a question about your project — for example, 'what did I work on yesterday?'",
            "memories": [],
            "grounded": False,
            "backend": "unavailable",
        }

    if not project_id:
        return {
            "answer": "No project selected. Please select a project first.",
            "memories": [],
            "grounded": False,
            "backend": "unavailable",
        }

    reply, memories_used, backend_available = _grounded_query(question, project_id)

    return {
        "answer": reply,
        "memories": memories_used,
        "grounded": backend_available,
        "backend": "available" if backend_available else "unavailable",
    }


# ─── Chat & Intent Routing ─────────────────────────────────────────────────────


def _remember_chat(project_id: str, message: str, reply: str | None, intent: str) -> None:
    """Keep chat turns in local memory so 'what did we discuss' works later."""
    if not project_id or not message:
        return
    from memory.local_store import remember

    text = f"Q: {message.strip()[:500]}\nA: {(reply or '').strip()[:1500]}"
    remember(project_id, "chat", text, meta={"intent": intent})


# Desktop-control intents work without a registered project.
_PROJECT_FREE_INTENT_NAMES = {
    "switch_tab",
    "type_text",
    "list_windows",
    "open_app",
    "open_browser",
    "system_command",
    "copy_to_clipboard",
    "paste_clipboard",
    "focus_app",
    "send_keystroke",
    "submit_prompt",
    "verify_result",
    "capture_screen",
    "ocr_image",
    "read_visible_context",
    "diagnose_visible_error",
    "review_visible_design",
    "generate_prompt_from_screen",
    "verify_visible_result",
}


_PROJECT_FREE_ACTIONS = {
    "switch_tab",
    "type_text",
    "list_windows",
    "chat_open_browser",
    "chat_open_app",
    "chat_system_command",
    "copy_to_clipboard",
    "paste_clipboard",
    "open_url",
    "focus_app",
    "send_keystroke",
    "submit_prompt_to_app",
    "verify_result",
    "capture_screen",
    "ocr_image",
    "read_visible_context",
    "diagnose_visible_error",
    "review_visible_design",
    "generate_prompt_from_screen",
    "verify_visible_result",
}


def _project_free_intents() -> set:
    from decision_engine.intent_parser import IntentType

    return {IntentType(name) for name in _PROJECT_FREE_INTENT_NAMES}


@app.post("/chat", tags=["chat"])
def chat(body: dict = Body(...)) -> dict:
    message = body.get("message", "")
    resolved = body.get("project_id") or body.get("active_project_id")
    project_id = str(resolved) if resolved else ""
    project_known = bool(project_id) and get_project(project_id) is not None

    if not isinstance(message, str) or not message.strip():
        return {
            "intent": "general_assistant",
            "confidence": 0.0,
            "reply": "Please enter a message.",
            "actions": [],
            "executed_actions": [],
            "project_id": project_id,
            "backend": "ok" if _backend_available() else "unavailable",
        }

    # Quick everyday commands (music, search, screen) need no project or planner.
    from assist.commands import run as run_quick_command

    quick = run_quick_command(message, project_id or None, body.get("permission_id"))
    if quick is not None:
        return {
            "intent": quick["intent"],
            "confidence": 1.0,
            "reply": quick["reply"],
            "actions": [],
            "executed_actions": [],
            "project_id": project_id or None,
            "backend": "ok",
            **({"needs_permission": quick["needs_permission"]} if quick.get("needs_permission") else
               {} if quick["success"] else {"error": quick["reply"]}),
        }

    from decision_engine.intent_parser import IntentType, parse_intent
    from decision_engine.planner import plan

    parsed_intent = parse_intent(message, active_project_id=project_id or None)
    if parsed_intent.intent not in _project_free_intents() and not project_known:
        error = (
            "Project not found. Select a registered project first."
            if project_id
            else "No project selected. Select or add a project first."
        )
        return {
            "intent": parsed_intent.intent.value,
            "confidence": parsed_intent.confidence,
            "reply": error,
            "error": error,
            "actions": [],
            "executed_actions": [],
            "project_id": project_id or None,
            "backend": "ok",
        }
    trigger_by_intent = {
        IntentType.MORNING_BRIEF: "chat:morning_brief",
        IntentType.RUN_TESTS: "chat:run_tests",
        IntentType.EXPLAIN_REPO: "chat:explain_repo",
        IntentType.GENERATE_COMMIT_MESSAGE: "chat:generate_commit_message",
        IntentType.FIND_AUTH: "chat:find_auth",
        IntentType.CONTINUE_WORK: "chat:continue_work",
        IntentType.START_DEV_ENV: "chat:start_dev_env",
        IntentType.GIT_LOG: "chat:git_log",
        IntentType.OPEN_APP: "chat:open_app",
        IntentType.OPEN_BROWSER: "chat:open_browser",
        IntentType.SYSTEM_COMMAND: "chat:system_command",
        IntentType.RUN_COMMAND: "chat:system_command",
        IntentType.QUERY_MEMORY: "chat:query_memory",
        IntentType.COPY_TO_CLIPBOARD: "chat:copy_to_clipboard",
        IntentType.PASTE_CLIPBOARD: "chat:paste_clipboard",
        IntentType.FOCUS_APP: "chat:focus_app",
        IntentType.SEND_KEYSTROKE: "chat:send_keystroke",
        IntentType.SUBMIT_PROMPT: "chat:submit_prompt",
        IntentType.VERIFY_RESULT: "chat:verify_result",
        IntentType.CAPTURE_SCREEN: "chat:capture_screen",
        IntentType.OCR_IMAGE: "chat:ocr_image",
        IntentType.READ_VISIBLE_CONTEXT: "chat:read_visible_context",
        IntentType.DIAGNOSE_VISIBLE_ERROR: "chat:diagnose_visible_error",
        IntentType.REVIEW_VISIBLE_DESIGN: "chat:review_visible_design",
        IntentType.GENERATE_PROMPT_FROM_SCREEN: "chat:generate_prompt_from_screen",
        IntentType.VERIFY_VISIBLE_RESULT: "chat:verify_visible_result",
        IntentType.DELEGATE_TASK: "chat:delegate_task",
        IntentType.SWITCH_TAB: "chat:switch_tab",
        IntentType.TYPE_TEXT: "chat:type_text",
        IntentType.LIST_WINDOWS: "chat:list_windows",
    }
    trigger = trigger_by_intent.get(parsed_intent.intent)
    if trigger:
        planned = plan(
            trigger,
            {
                "project_id": project_id,
                "message": message,
                "parsed": parsed_intent.params or {},
                "reasoning_mode": CURRENT_REASONING_MODE,
            },
        )
        executed_actions = [
            action for action in planned.get("actions", []) if action.get("executed")
        ]
        _remember_chat(project_id, message, planned.get("reply", ""), parsed_intent.intent.value)
        return {
            "intent": parsed_intent.intent.value,
            "confidence": parsed_intent.confidence,
            "reply": planned.get("reply", ""),
            "actions": planned.get("actions", []),
            "executed_actions": executed_actions,
            "project_id": project_id,
            "backend": "ok",
        }

    reply, actions, intent = _generate_chat_reply(message, project_id)
    _remember_chat(project_id, message, reply, intent)

    return {
        "intent": intent,
        "confidence": 0.98 if intent != "unavailable" else 0.0,
        "reply": reply,
        "actions": actions,
        "executed_actions": [],
        "project_id": project_id,
        "backend": "ok" if intent != "unavailable" else "unavailable",
    }


@app.post("/chat/approve-action", tags=["chat"])
def approve_action(body: dict = Body(...)) -> dict:
    """Execute a pending, policy-gated chat action after user approval."""
    from decision_engine.planner import ACTION_POLICY, _execute_action

    action_type = str(body.get("action_type", "")).strip()
    if not action_type:
        raise HTTPException(status_code=422, detail="action_type is required")

    from security.permissions import needs_card

    policy = ACTION_POLICY.get(action_type)
    if policy not in {"suggest", "confirm_once", "require_approval"} and not needs_card(action_type):
        raise HTTPException(status_code=400, detail="Action does not require approval")

    params = body.get("params") or {}
    if not isinstance(params, dict):
        raise HTTPException(status_code=422, detail="params must be an object")
    params.setdefault("project_id", body.get("project_id") or body.get("active_project_id"))
    if params.get("project_id") is None and action_type not in _PROJECT_FREE_ACTIONS:
        raise HTTPException(status_code=400, detail="No project selected. Add a project first.")

    try:
        result = _execute_action({"type": action_type, "params": params})
    except Exception as exc:
        logger.warning("Approved action failed | type=%s error=%s", action_type, exc)
        result = {"success": False, "error": str(exc)}

    return {
        "action_type": action_type,
        "executed": bool(result and result.get("success", False)),
        "result": result or {"success": False, "error": "Action did not return a result."},
    }


@app.get("/workflows", tags=["workflow"])
def list_workflows() -> dict:
    """List workflow definitions discovered by the registry."""
    from workflow_engine.registry import list_definitions

    return {"workflows": list_definitions()}


@app.post("/workflows/{workflow_id}/start", tags=["workflow"])
def start_workflow(workflow_id: str, body: dict = Body(...)) -> dict:
    """Start a registered workflow; execution pauses at its derived gates."""
    from workflow_engine.executor import WorkflowExecutor

    project_id = str(body.get("project_id") or body.get("active_project_id") or "")
    if not project_id or project_id == "None":
        return {"error": "No project selected. Add a project first.", "projects": []}
    if not get_project(project_id):
        return {"error": "Project not found", "projects": []}
    inputs = body.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=422, detail="inputs must be an object")
    inputs.setdefault("project_id", project_id)
    try:
        run = WorkflowExecutor().start(
            workflow_id, inputs, project_id, initiated_by=str(body.get("initiated_by") or "user")
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": vars(run)}


@app.post("/workflows/{run_id}/approve", tags=["workflow"])
def approve_workflow(run_id: str, body: dict = Body(default={})) -> dict:
    """Approve the current workflow gate and continue until the next gate."""
    from workflow_engine.executor import WorkflowExecutor

    try:
        run = WorkflowExecutor().approve_gate(run_id, str(body.get("approved_by") or "user"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": vars(run)}


@app.get("/external-agents/status", tags=["automation"])
def external_agent_status() -> dict:
    """Report optional external-agent integrations without invoking them."""
    from automation.agent_bridge import AgentBridge

    bridge = AgentBridge()
    return {
        "tools": [vars(bridge.check_tool(tool)) for tool in ("claude", "cursor", "antigravity", "vscode")]
    }


@app.post("/external-agents/{tool}/prompt", tags=["automation"])
def send_external_agent_prompt(tool: str, body: dict = Body(...)) -> dict:
    """Send a prompt to an external agent only after explicit API approval."""
    from automation.agent_bridge import AgentBridge
    from memory.capture import redact_secrets

    if tool not in {"claude", "cursor", "antigravity", "vscode", "kilo"}:
        raise HTTPException(status_code=404, detail="Unknown external agent")
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="prompt is required")
    # A caller-supplied "approved" flag is not consent: the user approves in the UI.
    from security.permissions import check

    request = check("app_control", f"Send a {len(prompt)}-character prompt to {tool}", body.get("permission_id"))
    if request is not None:
        return {"result": None, "needs_permission": request}

    result = AgentBridge().send_prompt(tool, redact_secrets(prompt), body.get("params"))
    return {"result": vars(result)}


# ─── Command Execution & OS Automation ─────────────────────────────────────────


@app.post("/commands/execute", tags=["automation"])
def execute_command(body: dict = Body(...)) -> dict:
    cmd = str(body.get("command", "")).strip()
    cwd = str(body.get("cwd") or os.getcwd())
    project_id = body.get("project_id") or body.get("active_project_id")
    if not project_id:
        return {"error": "No project selected. Add a project first.", "projects": []}
    project_id = str(project_id)

    if not cmd:
        return {
            "command": "",
            "status": "error",
            "executed": False,
            "suggested": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": "Empty command",
            "executed_at": datetime.now(UTC).isoformat(),
        }

    allow_execute = bool(body.get("allow_execute", False))
    if allow_execute:
        # Running a shell command is the user's call, not the caller's flag.
        from security.permissions import check

        request = check("system", f"Run `{cmd[:200]}` in {cwd}", body.get("permission_id"))
        if request is not None:
            return {"command": cmd, "status": "needs_permission", "executed": False, "suggested": True,
                    "needs_permission": request, "exit_code": None, "stdout": "", "stderr": "",
                    "executed_at": None}

    try:
        from automation.command_executor import CommandExecutor

        result = CommandExecutor(
            cwd=cwd, allow_auto_execute=allow_execute
        ).execute(
            cmd,
            context=str(body.get("context", "")),
            session_id=body.get("session_id"),
        )
        try:
            from db.client import insert_mistake, insert_terminal_command

            insert_terminal_command(
                project_id, body.get("session_id"), cmd, cwd, exit_code=result.exit_code
            )
            if result.executed and result.status in {"error", "timeout"}:
                stderr = (result.stderr or result.stdout or "Command failed").strip()
                insert_mistake(
                    project_id,
                    symptom=f"Command failed: {cmd[:120]}",
                    root_cause=stderr[:500],
                    fix="Review the failing command output and current git diff.",
                    module="automation_layer",
                )
        except Exception as exc:
            logger.warning("commands/execute: persistence skipped — %s", exc)
        return {
            "command": cmd,
            "status": "success" if result.status == "ok" else result.status,
            "executed": result.executed,
            "suggested": result.suggested,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "executed_at": result.executed_at,
            "undo_hint": result.undo_hint,
            "suggestion_reason": result.suggestion_reason,
        }
    except Exception as exc:
        try:
            from db.client import insert_mistake, insert_terminal_command

            insert_terminal_command(project_id, body.get("session_id"), cmd, cwd, exit_code=1)
            insert_mistake(
                project_id,
                symptom=f"Command crashed: {cmd[:120]}",
                root_cause=str(exc)[:500],
                fix="Check command availability, cwd, and recent code changes.",
                module="automation_layer",
            )
        except Exception as persist_exc:
            logger.warning("commands/execute: failure persistence skipped — %s", persist_exc)
        return {
            "command": cmd,
            "status": "error",
            "executed": False,
            "suggested": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "executed_at": datetime.now(UTC).isoformat(),
        }


@app.post("/execute/open_browser", tags=["automation"])
def execute_open_browser(body: dict = Body(...)) -> dict:
    url = str(body.get("url", "")).strip()
    if not url:
        return {"success": False, "error": "url is required"}

    try:
        if not re.match(r"^https?://[^@/\s]+", url):
            raise ValueError("Invalid URL format")
        from security.permissions import check

        request = check("launch", f"Open {url[:200]} in your browser", body.get("permission_id"))
        if request is not None:
            return {"success": False, "needs_permission": request}

        from automation.os_windows import launch_browser

        ok = launch_browser(url)
        return {"success": ok, "opened": ok, "url": url}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─── Phase 4 Agent Actions ─────────────────────────────────────────────────────


@app.post("/projects/{project_id}/generate-commit-message", tags=["agent_actions"])
def generate_commit_msg(project_id: str, body: dict | None = Body(None)) -> dict:
    from agent_actions import generate_commit_message

    payload = body or {}
    return generate_commit_message(
        project_id,
        repo_path=str(payload.get("repo_path", "")),
        staged=bool(payload.get("staged", True)),
    )


@app.post("/projects/{project_id}/find-auth-code", tags=["agent_actions"])
def find_auth(project_id: str, body: dict | None = Body(None)) -> dict:
    from agent_actions import find_authentication_code

    return find_authentication_code(
        project_id, query=str((body or {}).get("query", "authentication"))
    )


@app.post("/projects/{project_id}/continue-work", tags=["agent_actions"])
def continue_work(project_id: str) -> dict:
    from agent_actions import continue_previous_work

    return continue_previous_work(project_id)


@app.post("/projects/{project_id}/project-summary", tags=["agent_actions"])
def project_summary(project_id: str) -> dict:
    from agent_actions import generate_project_summary

    return generate_project_summary(project_id)


@app.post("/projects/{project_id}/start-dev-environment", tags=["agent_actions"])
def start_dev_env(project_id: str, body: dict | None = Body(None)) -> dict:
    from agent_actions import start_development_environment
    from security.permissions import check

    request = check("workspace", "Start this project's dev servers in new terminal windows",
                    (body or {}).get("permission_id"))
    if request is not None:
        return {"success": False, "needs_permission": request}
    return start_development_environment(project_id)


@app.post("/cross-app/tasks", tags=["agent_actions"])
def submit_task(body: dict = Body(...)) -> dict:
    task_id = body.get("task_id", "task-1")
    action = body.get("action", "")
    params = body.get("params", {})
    if not action:
        return {"task_id": task_id, "status": "error", "error": "action is required"}
    if not isinstance(params, dict):
        return {"task_id": task_id, "status": "error", "error": "params must be an object"}
    from security.permissions import check

    request = check("app_control", f"Run the cross-app action “{action}”", body.get("permission_id"))
    if request is not None:
        return {"task_id": task_id, "status": "needs_permission", "needs_permission": request}
    from agent_actions import submit_cross_app_task

    return submit_cross_app_task(task_id, action, params)


@app.get("/cross-app/tasks/{task_id}", tags=["agent_actions"])
def get_task_status(task_id: str) -> dict:
    from agent_actions import cross_app_task_status

    return cross_app_task_status(task_id)


@app.post("/projects/{project_id}/explain-repository", tags=["agent_actions"])
def explain_repo(project_id: str, body: dict | None = Body(None)) -> dict:
    from agent_actions import explain_repository

    project = get_project(project_id)
    if project is None:
        return {
            "project_id": project_id,
            "repo_path": "",
            "readme_summary": "",
            "folder_structure": [],
            "architecture_notes": [],
            "explanation": "Project not found.",
            "error": "Project not found",
        }

    repo_path = project.get("repo_path", "")
    return explain_repository(project_id, repo_path)


# ─── Analytics & Memory Graph ──────────────────────────────────────


@app.get("/projects/{project_id}/analytics", tags=["projects"])
def get_project_analytics(project_id: str) -> dict:
    commits_over_time = _safe_fetch(get_commits_over_time, project_id, days=7, default=[]) or []
    file_edits_over_time = (
        _safe_fetch(get_file_edits_over_time, project_id, days=7, default=[]) or []
    )

    pending_todos = _safe_fetch(get_todos, project_id, status="pending", default=[]) or []
    done_todos = _safe_fetch(get_todos, project_id, status="done", default=[]) or []
    todo_stats = {
        "pending": len(pending_todos),
        "completed": len(done_todos),
        "total": len(pending_todos) + len(done_todos),
    }

    sessions = _safe_fetch(get_sessions, project_id, default=[]) or []
    total_sessions = len(sessions)
    total_time_seconds = 0
    for s in sessions:
        started = s.get("started_at")
        ended = s.get("ended_at")
        if started and ended:
            try:
                start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(str(ended).replace("Z", "+00:00"))
                total_time_seconds += (end_dt - start_dt).total_seconds()
            except Exception:
                pass

    top_files = _safe_fetch(get_top_files, project_id, limit=10, default=[]) or []

    analytics = {
        "project_id": project_id,
        "commits_over_time": commits_over_time,
        "file_edits_over_time": file_edits_over_time,
        "todo_stats": todo_stats,
        "session_stats": {
            "total_sessions": total_sessions,
            "total_time_seconds": round(total_time_seconds, 1),
        },
        "top_files": top_files,
    }
    return {"analytics": analytics, **analytics}


@app.get("/projects/{project_id}/metrics/live", tags=["projects"])
def get_live_project_metrics(project_id: str) -> dict:
    """Return fresh project and agent performance metrics for polling UIs."""
    started = time.perf_counter()
    commits, file_edits, terminal_cmds, decisions = _activity_rows(project_id, 200)
    pending_todos = _safe_fetch(get_todos, project_id, status="pending", default=[]) or []
    done_todos = _safe_fetch(get_todos, project_id, status="done", default=[]) or []
    sessions = _safe_fetch(get_sessions, project_id, default=[]) or []
    repo_path = _project_repo_path(project_id)
    git_status = _run_git(repo_path, ["status", "--short"])
    changed_files = [
        line[3:].strip() if len(line) > 3 else line.strip()
        for line in git_status.get("stdout", "").splitlines()
        if line.strip()
    ]

    now = datetime.now(UTC)
    one_hour_ago = now.timestamp() - 3600

    def _ts(value: Any) -> float | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except Exception:
            return None

    recent_events = 0
    for row, key in (
        *[(row, "committed_at") for row in commits],
        *[(row, "edited_at") for row in file_edits],
        *[(row, "run_at") for row in terminal_cmds],
        *[(row, "decided_at") for row in decisions],
    ):
        ts = _ts(row.get(key))
        if ts is not None and ts >= one_hour_ago:
            recent_events += 1

    failed_commands = [
        c
        for c in terminal_cmds
        if c.get("exit_code") not in (None, 0, "0")
        or any(
            marker in str(c.get("command", "")).lower()
            for marker in ("error", "failed", "traceback")
        )
    ]
    test_commands = [
        c
        for c in terminal_cmds
        if any(
            marker in str(c.get("command", "")).lower()
            for marker in ("pytest", "npm test", "npm run build", "vitest", "ruff", "tsc")
        )
    ]
    recent_test_failures = [
        c
        for c in test_commands
        if c.get("exit_code") not in (None, 0, "0")
        or any(marker in str(c.get("command", "")).lower() for marker in ("failed", "error"))
    ]
    active_sessions = [s for s in sessions if not s.get("ended_at")]
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    todo_total = len(done_todos) + len(pending_todos)
    db_status = db_health_check()
    reasoning_ok = _backend_available()

    # Modules come from the project's own structure (intelligence/profile.py),
    # not a fixed list — a Next.js app and a Django app get different cards.
    module_health: list[dict[str, Any]] = []
    try:
        from intelligence.profile import get_profile

        profile = get_profile(project_id)
        if profile.get("ok"):
            module_health = [
                {"name": m["name"], "path": m["path"], "pct": m["pct"], "basis": m["basis"]}
                for m in profile["modules"]
            ]
    except Exception as exc:
        logger.debug("profile modules unavailable — %s", exc)

    return {
        "project_id": project_id,
        "generated_at": now.isoformat(),
        "agent": {
            "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC, 1),
            "started_at": _STARTED_AT.isoformat(),
            "api_latency_ms": latency_ms,
            "db_status": db_status,
            "reasoning_backend": "available" if reasoning_ok else "unavailable",
        },
        "memory": {
            "commits": len(commits),
            "file_edits": len(file_edits),
            "terminal_commands": len(terminal_cmds),
            "decisions": len(decisions),
            "todos_pending": len(pending_todos),
            "todos_done": len(done_todos),
            "events_last_hour": recent_events,
            "failed_commands": len(failed_commands),
            "test_commands": len(test_commands),
            "recent_test_failures": len(recent_test_failures),
            "changed_files": len(changed_files),
        },
        "performance": {
            "events_per_minute_last_hour": round(recent_events / 60, 2),
            "active_sessions": len(active_sessions),
            "completion_percent": round((len(done_todos) / max(1, todo_total)) * 100, 1),
            "module_health": module_health,
        },
    }


@app.get("/projects/{project_id}/diagnostics/commit-error", tags=["projects"])
def diagnose_commit_error(project_id: str) -> dict:
    """Correlate current git changes with stored error and mistake memory."""
    repo_path = _project_repo_path(project_id)
    status = _run_git(repo_path, ["status", "--short"])
    changed = _run_git(repo_path, ["diff", "--name-only", "HEAD"])
    staged = _run_git(repo_path, ["diff", "--cached", "--name-only"])
    last_commit = _run_git(repo_path, ["log", "-1", "--pretty=format:%H%n%s%n%an%n%cI"])

    changed_files = [
        line.strip()
        for line in "\n".join([changed.get("stdout", ""), staged.get("stdout", "")]).splitlines()
        if line.strip()
    ]
    changed_files = list(dict.fromkeys(changed_files))

    terminal_cmds = _safe_fetch(get_terminal_commands, project_id, limit=30, default=[]) or []
    recent_errors = [
        c
        for c in terminal_cmds
        if c.get("exit_code") not in (None, 0, "0")
        or any(
            marker in str(c.get("command", "")).lower()
            for marker in ("error", "failed", "traceback", "pytest")
        )
    ][:8]

    from db.client import get_mistakes

    mistakes = _safe_fetch(get_mistakes, project_id, default=[]) or []

    suspected_files: list[dict[str, Any]] = []
    error_text = " ".join(str(e.get("command", "")) for e in recent_errors).lower()
    for file_path in changed_files:
        score = 0.35
        name = os.path.basename(file_path).lower()
        if name and name in error_text:
            score += 0.4
        if any(part in error_text for part in file_path.lower().replace("\\", "/").split("/")):
            score += 0.15
        suspected_files.append(
            {
                "file_path": file_path,
                "score": round(min(score, 0.95), 2),
                "reason": "Changed file referenced by recent error memory"
                if score > 0.35
                else "Changed since HEAD",
            }
        )
    suspected_files.sort(key=lambda item: item["score"], reverse=True)

    recommendations = []
    if recent_errors:
        recommendations.append(
            "Start with the most recent failed terminal command; its output is now stored in persistent memory."
        )
    if changed_files:
        recommendations.append(
            "Review the changed files above against the failing command before committing."
        )
    if mistakes:
        recommendations.append("Check similar mistake-log entries before applying a fix.")
    if not recommendations:
        recommendations.append(
            "No stored error found yet; run the failing test/build through AUTOMATA so it can capture the failure."
        )

    return {
        "project_id": project_id,
        "repo_path": repo_path,
        "git": {
            "status": status,
            "changed_files": changed_files,
            "last_commit": last_commit,
        },
        "recent_errors": recent_errors,
        "related_mistakes": mistakes[:5],
        "suspected_files": suspected_files[:10],
        "recommendations": recommendations,
    }


_GRAPH_STOPWORDS = {
    "this", "that", "with", "from", "into", "have", "were", "will", "when", "then",
    "than", "also", "only", "file", "files", "edit", "edited", "update", "updated",
    "change", "changed", "changes", "added", "remove", "removed", "modified",
}


@app.get("/projects/{project_id}/memory-graph", tags=["projects"])
def get_memory_graph(project_id: str) -> dict:

    nodes: list[dict] = []
    edges: list[dict] = []

    table_sources = {
        "commits": get_commits,
        "file_edits": get_file_edits,
        "todos": get_todos,
        "architecture_notes": get_architecture_notes,
        "decision_log": get_decision_entries,
    }

    for table_name, fetch_fn in table_sources.items():
        try:
            if table_name == "todos":
                records = fetch_fn(project_id)
            else:
                records = fetch_fn(project_id, limit=20)
        except Exception:
            records = []

        for rec in records:
            node_id = f"{table_name}:{rec.get('id', '')}"
            content = ""
            timestamp = None

            if table_name == "commits":
                content = rec.get("message", "")
                timestamp = rec.get("committed_at")
            elif table_name == "file_edits":
                content = rec.get("change_summary", "") or rec.get("file_path", "")
                timestamp = rec.get("edited_at")
            elif table_name == "todos":
                content = rec.get("description", "")
                timestamp = rec.get("created_at")
            elif table_name == "architecture_notes":
                content = rec.get("title", "") or rec.get("content", "")
                timestamp = rec.get("updated_at")
            elif table_name == "decision_log":
                content = rec.get("decision", "") or rec.get("rationale", "")
                timestamp = rec.get("decided_at")

            nodes.append(
                {
                    "id": node_id,
                    "table": table_name,
                    "content": content[:200],
                    "timestamp": timestamp,
                }
            )

    # Same-day edges: link each node to the next one that day (a chain) rather
    # than every pair, which grows quadratically and swamps the graph view.
    by_day: dict[str, list[dict]] = {}
    for node in nodes:
        ts = node.get("timestamp")
        if ts:
            by_day.setdefault(str(ts)[:10], []).append(node)
    for day_nodes in by_day.values():
        day_nodes.sort(key=lambda n: str(n.get("timestamp")))
        for prev, nxt in zip(day_nodes, day_nodes[1:], strict=False):
            edges.append({"source": prev["id"], "target": nxt["id"], "type": "same_day"})

    # Keyword edges between commits and file edits, ignoring filler words.
    def _terms(text: str) -> set[str]:
        return {w for w in re.findall(r"[a-z0-9_]{4,}", text.lower()) if w not in _GRAPH_STOPWORDS}

    commit_terms = [(n, _terms(n["content"])) for n in nodes if n["table"] == "commits"]
    file_terms = [(n, _terms(n["content"])) for n in nodes if n["table"] == "file_edits"]
    for cn, c_words in commit_terms:
        if not c_words:
            continue
        for fn, f_words in file_terms:
            overlap = c_words & f_words
            if len(overlap) >= 2:
                edges.append(
                    {
                        "source": cn["id"],
                        "target": fn["id"],
                        "type": "keyword_match",
                        "shared_terms": sorted(overlap)[:3],
                    }
                )

    return {
        "project_id": project_id,
        "nodes": nodes,
        "edges": edges,
    }


# ─── System Resources & App Usage ──────────────────────────────────────────────


@app.get("/system/metrics", tags=["system"])
def system_metrics(processes: bool = False) -> dict:
    """Live CPU / GPU / RAM / disk / network snapshot with ~6 min of history."""
    from monitoring.system_metrics import get_system_metrics

    return get_system_metrics(include_processes=processes)


@app.get("/usage/summary", tags=["usage"])
def usage_summary(range: str = "today") -> dict:  # noqa: A002 - query parameter name
    """Foreground-app time per app/category for today, the last 7 or 30 days."""
    from monitoring.app_usage import RANGE_DAYS
    from monitoring.app_usage import usage_summary as summarize_usage

    if range not in RANGE_DAYS:
        raise HTTPException(status_code=422, detail="range must be today, week or month")
    return summarize_usage(range)


@app.get("/usage/timeline", tags=["usage"])
def usage_timeline(day: str | None = None) -> dict:
    """Focus segments for one local day (YYYY-MM-DD, default today)."""
    from monitoring.app_usage import usage_timeline as timeline

    return timeline(day)


@app.get("/usage/status", tags=["usage"])
def usage_status() -> dict:
    from monitoring.app_usage import tracker_status

    return tracker_status()


@app.post("/usage/tracking", tags=["usage"])
def set_usage_tracking(body: dict = Body(...)) -> dict:
    """Pause or resume background app-usage recording."""
    from monitoring.app_usage import set_tracking

    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="enabled must be true or false")
    return set_tracking(enabled)


@app.get("/system/autostart", tags=["system"])
def get_autostart() -> dict:
    from automation.autostart import autostart_status

    return autostart_status()


@app.post("/system/autostart", tags=["system"])
def set_autostart_route(body: dict = Body(...)) -> dict:
    """Enable/disable starting the background agent at Windows sign-in."""
    from automation.autostart import set_autostart

    enabled = body.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="enabled must be true or false")
    return set_autostart(enabled)
