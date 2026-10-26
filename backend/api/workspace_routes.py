"""
api/workspace_routes.py — routes for the smart-workspace features.

Owns:    HTTP endpoints for local AI setup, offline memory, capture/active
         project, session snapshots and resume. (Later phases add project
         profiles, desktop control, tasks and the Needs inbox here too.)
Never:   Holds business logic — each route delegates to its module.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

router = APIRouter()


def _bool(body: dict, key: str) -> bool:
    value = body.get(key)
    if not isinstance(value, bool):
        raise HTTPException(status_code=422, detail=f"{key} must be true or false")
    return value


# ─── AI / local models ───────────────────────────────────────────────────────


@router.get("/ai/status", tags=["ai"])
def ai_status() -> dict:
    """Online/offline, which providers are configured, local model readiness, last answer."""
    from ai import bedrock_client as bc
    from config import settings

    cloud = {
        name: bool(getattr(settings, attr, ""))
        for name, attr in (
            ("groq", "groq_api_key"), ("openrouter", "openrouter_api_key"), ("gemini", "gemini_api_key"),
            ("cohere", "cohere_api_key"), ("nvidia", "nvidia_api_key"), ("minimax", "minimax_api_key"),
        )
    }
    cloud["bedrock"] = bool(getattr(settings, "bedrock_available", False))
    import api.server as server

    return {
        "online": bc.is_online(),
        "reasoning_mode": server.CURRENT_REASONING_MODE,
        "cloud_providers": cloud,
        "ollama": bc.ollama_status(),
        "offline_embeddings": bc.fastembed_status(),
        "last_answer": dict(bc.LAST_ANSWER),
    }


@router.get("/ai/local/recommendation", tags=["ai"])
def ai_local_recommendation() -> dict:
    from ai.local_models import recommend

    return recommend()


@router.post("/ai/local/pull", tags=["ai"])
def ai_local_pull(body: dict = Body(...)) -> dict:
    from ai.local_models import start_pull

    model = str(body.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="model is required")
    return start_pull(model)


@router.get("/ai/local/pull", tags=["ai"])
def ai_local_pull_status() -> dict:
    from ai.local_models import pull_status

    return pull_status()


@router.post("/ai/local/select", tags=["ai"])
def ai_local_select(body: dict = Body(...)) -> dict:
    from ai.local_models import select_chat_model

    model = str(body.get("chat_model") or "").strip()
    if not model:
        raise HTTPException(status_code=422, detail="chat_model is required")
    return select_chat_model(model)


@router.post("/ai/local/install-ollama", tags=["ai"])
def ai_local_install() -> dict:
    from ai.local_models import launch_ollama_installer

    return launch_ollama_installer()


@router.post("/ai/local/offline-embeddings", tags=["ai"])
def ai_local_offline_embeddings(body: dict = Body(...)) -> dict:
    from ai.local_models import set_offline_embeddings

    return set_offline_embeddings(_bool(body, "enabled"))


# ─── Memory ──────────────────────────────────────────────────────────────────


@router.get("/memory/search", tags=["memory"])
def memory_search(q: str, project_id: str | None = None, limit: int = 10) -> dict:
    """Search local memory (works offline)."""
    from memory.local_store import get_store

    if not q.strip():
        raise HTTPException(status_code=422, detail="q is required")
    hits = get_store().search(q, project_id=project_id, limit=max(1, min(limit, 50)))
    return {"query": q, "results": hits, "message": None if hits else "No memory found for that query"}


@router.get("/memory/stats", tags=["memory"])
def memory_stats(project_id: str | None = None) -> dict:
    from memory.local_store import get_store

    store = get_store()
    return {"project_id": project_id, "counts": store.counts(project_id), "path": store.path}


# ─── Active project, snapshots, resume ───────────────────────────────────────


@router.post("/projects/{project_id}/activate", tags=["workspace"])
def activate_project(project_id: str) -> dict:
    """Make this the active project: capture follows it from now on."""
    from workspace.capture_manager import get_manager

    result = get_manager().activate(project_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Cannot activate project"))
    return result


@router.get("/workspace/capture", tags=["workspace"])
def capture_status() -> dict:
    from workspace.capture_manager import get_manager

    return get_manager().status()


@router.post("/projects/{project_id}/snapshot", tags=["workspace"])
def create_snapshot(project_id: str) -> dict:
    from workspace.snapshot import take_snapshot

    result = take_snapshot(project_id, "manual")
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.get("/projects/{project_id}/snapshot", tags=["workspace"])
def latest_snapshot(project_id: str) -> dict:
    from memory.local_store import get_store

    return {"snapshot": get_store().latest_snapshot(project_id)}


@router.post("/projects/{project_id}/resume", tags=["workspace"])
def resume_project(project_id: str, body: dict | None = Body(None)) -> dict:
    """Reopen editor (with recent files), terminal and dev servers from the last snapshot."""
    from workspace.snapshot import resume

    opts = body or {}
    return resume(
        project_id,
        open_editor=bool(opts.get("open_editor", True)),
        open_terminal=bool(opts.get("open_terminal", True)),
        start_servers=bool(opts.get("start_servers", True)),
    )


@router.post("/workspace/snapshot-active", tags=["workspace"])
def snapshot_active() -> dict:
    """Snapshot whichever project capture is following (used by the tray menu)."""
    from workspace.capture_manager import active_project_id
    from workspace.snapshot import take_snapshot

    pid = active_project_id()
    if not pid:
        raise HTTPException(status_code=404, detail="No active project")
    return take_snapshot(pid, "manual")


# ─── Project intelligence ────────────────────────────────────────────────────


@router.get("/projects/{project_id}/profile", tags=["projects"])
def project_profile(project_id: str, refresh: bool = False) -> dict:
    """Detected stack, run book, env requirements and scored modules for this project."""
    from intelligence.profile import get_profile

    profile = get_profile(project_id, refresh=refresh)
    if not profile.get("ok"):
        raise HTTPException(status_code=404, detail=profile.get("error", "Profile unavailable"))
    return profile


# ─── Work bar (quick assist) ─────────────────────────────────────────────────


@router.post("/assist", tags=["assist"])
def assist(body: dict = Body(...)) -> dict:
    """Work bar entry: {text, project_id}. Quick commands run locally; the rest goes to chat."""
    from assist.commands import run

    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    quick = run(text, body.get("project_id"))
    if quick is not None:
        return {"handled_by": "assist", **quick}
    from api.server import chat

    reply = chat({"message": text, "project_id": body.get("project_id")})
    return {"handled_by": "chat", "intent": reply.get("intent"), "reply": reply.get("reply"),
            "success": not reply.get("error")}


@router.get("/assist/now-playing", tags=["assist"])
def assist_now_playing() -> dict:
    from assist.media import now_playing

    return now_playing()


@router.post("/assist/media", tags=["assist"])
def assist_media(body: dict = Body(...)) -> dict:
    """{action: play_pause|next|previous|volume_up|volume_down|mute} — system media keys."""
    from assist.media import control

    return control(str(body.get("action") or ""))


@router.post("/assist/screen", tags=["assist"])
def assist_screen(body: dict = Body(default={})) -> dict:
    """{question?, app?} — OCR the window you are looking at and answer. Only runs when called."""
    from assist.screen import analyze

    return analyze(str(body.get("question") or ""), body.get("app") or None)


# ─── Desktop control ─────────────────────────────────────────────────────────


@router.get("/desktop/windows", tags=["desktop"])
def desktop_windows() -> dict:
    from automation.desktop import list_windows

    return list_windows()


@router.get("/desktop/tabs", tags=["desktop"])
def desktop_tabs(app: str = "browser") -> dict:
    from automation.desktop import browser_tabs

    return browser_tabs(app)


@router.post("/desktop/tabs/switch", tags=["desktop"])
def desktop_switch_tab(body: dict = Body(...)) -> dict:
    from automation.desktop import switch_tab

    return switch_tab(str(body.get("title", "")), str(body.get("app") or "browser"))


@router.post("/desktop/focus", tags=["desktop"])
def desktop_focus(body: dict = Body(...)) -> dict:
    from automation.desktop import focus

    return focus(str(body.get("app", "")), body.get("title_hint"))


@router.post("/desktop/type", tags=["desktop"])
def desktop_type(body: dict = Body(...)) -> dict:
    from automation.desktop import type_text

    return type_text(str(body.get("text", "")), str(body.get("app") or "") or None)


@router.post("/desktop/read", tags=["desktop"])
def desktop_read(body: dict | None = Body(None)) -> dict:
    """OCR the screen, an app window or a region; optionally check for expected text."""
    from automation.desktop import read_screen

    opts = body or {}
    return read_screen(
        expected_text=opts.get("expected_text"),
        region=opts.get("region"),
        app_name=opts.get("app"),
    )


# ─── Tasks and the Needs inbox ───────────────────────────────────────────────


@router.post("/tasks", tags=["tasks"])
def create_task(body: dict = Body(...)) -> dict:
    """Delegate work to an AI app: {request, agent, project_id}."""
    from tasks.engine import create_delegation_task

    result = create_delegation_task(body.get("project_id"), str(body.get("request", "")), str(body.get("agent", "")))
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error"))
    return result


@router.get("/tasks", tags=["tasks"])
def list_tasks(project_id: str | None = None) -> dict:
    from tasks.store import get_task_store

    return {"tasks": get_task_store().list_tasks(project_id)}


@router.get("/tasks/{task_id}", tags=["tasks"])
def get_task(task_id: str) -> dict:
    from tasks.store import get_task_store

    task = get_task_store().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


@router.post("/tasks/{task_id}/approve", tags=["tasks"])
def approve_task(task_id: str) -> dict:
    from tasks.engine import approve

    result = approve(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error"))
    return result


@router.post("/tasks/{task_id}/answer", tags=["tasks"])
def answer_task(task_id: str, body: dict = Body(default={})) -> dict:
    """Answer the task's questions: {answers: {folder, stack, features, …}}; {} uses the defaults."""
    from tasks.engine import answer

    result = answer(task_id, body.get("answers") or {})
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error"))
    return result


@router.post("/tasks/{task_id}/cancel", tags=["tasks"])
def cancel_task(task_id: str) -> dict:
    from tasks.engine import cancel

    result = cancel(task_id)
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error"))
    return result


@router.get("/needs", tags=["tasks"])
def list_needs(project_id: str | None = None, refresh: bool = False) -> dict:
    """Open 'needs from you' items; refresh=true rescans the project's env requirements."""
    from tasks.needs import collect_needs
    from tasks.store import get_task_store

    if project_id:
        # Reconcile with the (cached) profile so fixed or unused items disappear.
        return {"needs": collect_needs(project_id, refresh=refresh)}
    return {"needs": get_task_store().list_needs(project_id=project_id)}


@router.post("/needs/{need_id}/resolve", tags=["tasks"])
def resolve_need(need_id: str, body: dict = Body(...)) -> dict:
    """{save_to: keyring|env_file|both|done|dismiss, value?}. The value is never stored by AUTOMATA."""
    from tasks.needs import resolve

    result = resolve(need_id, body.get("value"), str(body.get("save_to", "")))
    if not result.get("success"):
        raise HTTPException(status_code=422, detail=result.get("error"))
    return result


# ─── Self-check ──────────────────────────────────────────────────────────────


@router.get("/system/self-check", tags=["system"])
def self_check() -> dict:
    """Everything the workspace depends on, each with status and a fix hint."""
    import shutil
    import sys

    from ai import bedrock_client as bc
    from automation import uia
    from automation.autostart import autostart_status
    from config import data_dir
    from db.client import health_check
    from monitoring.app_usage import tracker_status
    from workspace.capture_manager import get_manager

    checks = []

    def add(key, label, ok, detail, fix=None, level="error"):
        checks.append({"key": key, "label": label, "ok": bool(ok), "detail": detail,
                       "fix": None if ok else fix, "level": "ok" if ok else level})

    db = health_check()
    add("cloud_db", "Cloud memory (CockroachDB)", db.get("db") == "connected",
        "Connected" if db.get("db") == "connected" else db.get("reason", "Not connected"),
        "Optional — local memory keeps working. Set COCKROACHDB_CONNECTION_STRING in backend/.env to sync.", "warning")
    online = bc.is_online()
    add("internet", "Internet", online, "Online" if online else "Offline — using local models only",
        "Cloud AI is skipped while offline.", "warning")
    oll = bc.ollama_status()
    add("ollama", "Local AI (Ollama)", oll["running"] and oll["chat_model_ready"],
        f"{oll['chat_model']} ready" if oll["running"] and oll["chat_model_ready"]
        else ("Running, model not pulled" if oll["running"] else ("Installed, not running" if oll["installed"] else "Not installed")),
        "Open Setup → Local AI to install Ollama and download the recommended model.", "warning")
    emb = bc.fastembed_status()
    add("semantic_search", "Offline semantic search", emb["enabled"] or oll.get("embedding_model_ready"),
        "On" if emb["enabled"] or oll.get("embedding_model_ready") else "Keyword search only (works offline)",
        "Pull nomic-embed-text in Ollama, or install the local-ai extra.", "info")
    ocr_ok = False
    if sys.platform == "win32":
        import subprocess

        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]|Out-Null;"
                 "([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages|%{$_.LanguageTag}) -join ','"],
                capture_output=True, text=True, timeout=10)
            langs = out.stdout.strip()
            ocr_ok = bool(langs)
        except Exception:
            langs = ""
    else:
        langs = ""
    add("ocr", "Screen reading (OCR)", ocr_ok, f"Windows OCR: {langs}" if ocr_ok else "No OCR language installed",
        "Windows Settings → Time & language → Language → add an OCR-capable language pack.", "warning")
    add("ui_automation", "Reading other apps (UI Automation)", uia.available(),
        "Available" if uia.available() else "Unavailable", "Install comtypes (uv sync).", "warning")
    cap = get_manager().status()
    add("capture", "Activity capture", bool(cap.get("threads")),
        f"Following {cap.get('project_path')}" if cap.get("threads") else "Not following any project",
        "Select a project with a valid folder in Projects.", "warning")
    usage = tracker_status()
    add("usage", "App-usage tracking", usage["running"] and not usage["paused"],
        "Recording" if usage["running"] and not usage["paused"] else ("Paused" if usage["paused"] else "Not running"),
        "Turn on 'Record app usage' in Settings.", "info")
    auto = autostart_status()
    add("autostart", "Start at sign-in", auto.get("enabled"), "On" if auto.get("enabled") else "Off",
        "Turn on 'Start at sign-in' in Settings so the agent is always running.", "info")
    free = round(shutil.disk_usage(data_dir()).free / 2**30, 1)
    add("disk", "Free disk (data folder)", free >= 2, f"{free} GB free", "Free up disk space.", "warning")
    return {"ok": all(c["ok"] or c["level"] != "error" for c in checks), "checks": checks}
