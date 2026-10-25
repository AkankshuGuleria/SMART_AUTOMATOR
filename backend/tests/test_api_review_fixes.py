"""
tests/test_api_review_fixes.py — regressions for bugs fixed in the project review.

No database or model provider is used: conftest blanks every connection
setting, so db.client returns empty results.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

import api.server as server
from api.server import app

client = TestClient(app)


def test_register_project_rejects_missing_folder(tmp_path):
    missing = tmp_path / "does-not-exist"
    res = client.post("/projects", json={"name": "x", "repo_path": str(missing)})
    assert res.status_code == 422
    assert "Folder not found" in res.json()["detail"]


def test_register_project_requires_path():
    res = client.post("/projects", json={"name": "x"})
    assert res.status_code == 422


def test_register_project_reports_db_failure_instead_of_fake_success(tmp_path):
    res = client.post("/projects", json={"repo_path": str(tmp_path)})
    assert res.status_code == 503


def test_register_project_returns_existing_for_duplicate_path(tmp_path):
    existing = {"id": "p1", "name": "demo", "repo_path": str(tmp_path)}
    with (
        patch.object(server, "get_projects", return_value=[existing]),
        patch.object(server, "insert_project") as insert,
    ):
        res = client.post("/projects", json={"repo_path": str(tmp_path) + "\\"})
    assert res.status_code == 200
    assert res.json() == {"project": existing, "existing": True}
    insert.assert_not_called()


def test_chat_desktop_intent_works_without_project():
    with patch(
        "agent_actions.open_app_or_url",
        return_value={
            "success": True,
            "action": "open_app",
            "message": "Launched spotify",
        },
    ) as mock_open:
        body = client.post("/chat", json={"message": "open spotify"}).json()
    assert body["intent"] == "open_app"
    assert body["actions"][0]["executed"] is True
    mock_open.assert_called_once()


def test_chat_project_intent_without_project_explains_why():
    body = client.post("/chat", json={"message": "generate commit message"}).json()
    assert body["actions"] == []
    assert "No project selected" in body["reply"]


def test_approve_action_without_project_is_400_for_project_actions():
    res = client.post(
        "/chat/approve-action",
        json={
            "action_type": "chat_generate_commit_message",
            "params": {},
        },
    )
    assert res.status_code == 400


def test_tools_status_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_probe_tools", lambda: calls.append(1) or {"tools": []})
    monkeypatch.setitem(server._TOOLS_CACHE, "value", None)
    client.get("/tools/status")
    client.get("/tools/status")
    assert len(calls) == 1


def test_memory_graph_same_day_edges_are_linear(monkeypatch):
    commits = [
        {"id": i, "message": f"commit {i}", "committed_at": f"2026-10-25T0{i}:00:00"}
        for i in range(8)
    ]
    monkeypatch.setattr(server, "get_commits", lambda pid, limit=20: commits)
    for name in ("get_file_edits", "get_architecture_notes", "get_decision_entries"):
        monkeypatch.setattr(server, name, lambda pid, limit=20: [])
    monkeypatch.setattr(server, "get_todos", lambda pid: [])
    body = client.get("/projects/p1/memory-graph").json()
    same_day = [e for e in body["edges"] if e["type"] == "same_day"]
    assert len(body["nodes"]) == 8
    assert len(same_day) == 7  # chain, not 28 all-pairs edges


def test_health_route_runs_in_threadpool_not_event_loop():
    import inspect

    # Blocking routes must be plain functions so FastAPI runs them off the loop.
    for route in app.routes:
        if getattr(route, "path", "") in {"/chat", "/query", "/projects/{project_id}/metrics/live"}:
            assert not inspect.iscoroutinefunction(route.endpoint), route.path
