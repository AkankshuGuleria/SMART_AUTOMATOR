"""
tests/test_workspace.py — Phase 1: active project, snapshots, resume, AI setup routes.

No real editor/terminal is launched; subprocess and OS helpers are faked.
"""

import pytest
from fastapi.testclient import TestClient

from api.server import app
from memory import local_store
from memory.local_store import LocalStore

client = TestClient(app)


@pytest.fixture
def store(tmp_path):
    s = LocalStore(":memory:")
    s.upsert_project({"id": "p1", "name": "Demo", "repo_path": str(tmp_path)}, source="local")
    local_store.set_store(s)
    yield s
    local_store.set_store(None)
    s.close()


def test_snapshot_captures_recent_files_todos_and_chat(store, tmp_path, monkeypatch):
    from workspace import snapshot

    f = tmp_path / "app.py"
    f.write_text("x")
    store.record("p1", "file_edit", "Edited app.py", meta={"file_path": str(f)})
    store.record("p1", "todo", "TODO (pending): add login")
    store.record("p1", "chat", "Q: where is auth?\nA: src/auth.py")
    monkeypatch.setattr(snapshot, "_git", lambda repo, *a: "main" if a[0] == "branch" else "")
    monkeypatch.setattr(snapshot, "_open_windows", lambda name, repo: [])
    monkeypatch.setattr(snapshot, "_dev_servers", lambda repo: [{"port": 5173, "process": "node.exe", "cwd": str(tmp_path), "command": "npm run dev"}])

    res = client.post("/projects/p1/snapshot").json()
    assert res["success"] is True
    data = res["data"]
    assert data["branch"] == "main"
    assert data["recent_files"] == [str(f)]
    assert data["open_todos"] == ["TODO (pending): add login"]
    assert data["dev_servers"][0]["port"] == 5173
    assert client.get("/projects/p1/snapshot").json()["snapshot"]["data"]["branch"] == "main"


def test_resume_reports_each_step_and_skips_running_servers(store, tmp_path, monkeypatch):
    from workspace import snapshot

    store.save_snapshot("p1", {
        "repo_path": str(tmp_path), "branch": "main", "recent_files": [],
        "open_windows": [], "dev_servers": [{"port": 5173, "cwd": str(tmp_path), "command": "npm run dev"}],
        "open_todos": ["TODO: x"],
    }, "idle")
    launched = []
    monkeypatch.setattr(snapshot.subprocess, "Popen", lambda *a, **k: launched.append(a[0]))
    monkeypatch.setattr("automation.os_windows.resolve_executable",
                        lambda cmd: "C:/Programs/Antigravity IDE.exe" if cmd == "antigravity-ide" else None)
    # The user last worked on this project in Antigravity IDE (usage history).
    monkeypatch.setattr(snapshot, "last_editor", lambda pid, repo: {
        "app": "Antigravity IDE", "folder": str(tmp_path), "seen_at": 1.0, "source": "usage history"})
    monkeypatch.setattr("automation.os_windows.open_terminal", lambda cwd="": True)
    monkeypatch.setattr(snapshot, "_dev_servers", lambda repo: [{"port": 5173}])  # already running

    first = client.post("/projects/p1/resume", json={}).json()
    req = first["needs_permission"]  # asks before opening anything
    assert req["category"] == "workspace" and "open Antigravity IDE" in req["action"] and launched == []
    res = client.post("/projects/p1/resume", json={"permission_id": req["id"]}).json()
    steps = {s["step"]: s for s in res["steps"]}
    assert res["success"] is True
    assert steps["editor"]["status"] == "ok" and steps["editor"]["app"] == "Antigravity IDE"
    assert steps["terminal"]["status"] == "ok"
    assert steps["dev_server"]["status"] == "skipped"
    assert launched == [["C:/Programs/Antigravity IDE.exe", str(tmp_path)]]  # not VS Code
    assert res["summary"]["open_todos"] == ["TODO: x"]


def test_resume_without_snapshot_is_an_error(store):
    res = client.post("/projects/p1/resume", json={}).json()
    assert res["success"] is False and "No snapshot" in res["error"]


def test_activate_rejects_missing_folder(store):
    store.upsert_project({"id": "gone", "name": "Gone", "repo_path": "Z:/nope"}, source="local")
    assert client.post("/projects/gone/activate").status_code == 404


def test_memory_search_route(store):
    store.record("p1", "commit", "Add stripe checkout webhook")
    body = client.get("/memory/search", params={"q": "stripe webhook", "project_id": "p1"}).json()
    assert body["results"][0]["content"] == "Add stripe checkout webhook"
    empty = client.get("/memory/search", params={"q": "kubernetes", "project_id": "p1"}).json()
    assert empty["results"] == [] and empty["message"] == "No memory found for that query"


def test_ai_status_reports_offline_and_local_model(store, monkeypatch):
    from ai import bedrock_client as bc

    monkeypatch.setenv("AUTOMATA_FORCE_ONLINE", "0")
    monkeypatch.setattr(bc, "ollama_status", lambda: {"installed": False, "running": False, "models": []})
    body = client.get("/ai/status").json()
    assert body["online"] is False
    assert body["ollama"]["installed"] is False
    assert "groq" in body["cloud_providers"]


def test_selected_local_model_overrides_env(store):
    from ai import bedrock_client as bc

    client.post("/ai/local/select", json={"chat_model": "qwen2.5-coder:1.5b"})
    assert bc._ollama_chat_model() == "qwen2.5-coder:1.5b"


def test_recommendation_fits_small_gpu(monkeypatch):
    from ai import local_models

    monkeypatch.setattr(
        "monitoring.system_metrics.get_system_metrics",
        lambda: {"gpu": {"devices": [{"memory_total_mb": 4096}]}},
    )
    monkeypatch.setattr(local_models, "_free_gb", lambda path: 3.0)
    rec = local_models.recommend()
    assert rec["chat_model"] == "qwen2.5-coder:3b"
    assert rec["warning"] and "OLLAMA_MODELS" in rec["warning"]


def test_pull_requires_running_ollama(monkeypatch):
    monkeypatch.setattr("ai.bedrock_client.ollama_status", lambda: {"running": False})
    body = client.post("/ai/local/pull", json={"model": "qwen2.5-coder:3b"}).json()
    assert body["success"] is False and "not running" in body["error"]
