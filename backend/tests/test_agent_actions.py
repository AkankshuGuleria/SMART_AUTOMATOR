"""
tests/test_agent_actions.py — Regression tests for Phase 4 Agent Actions.
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from api.server import app

client = TestClient(app)


def test_generate_commit_message_route_no_project(monkeypatch):
    with patch("db.client.get_project", return_value=None):
        response = client.post("/projects/proj-missing/generate-commit-message", json={"repo_path": "d:/AUTOMATA"})
        assert response.status_code == 200
        data = response.json()
        assert data["error"] == "Project not found"
        assert data["commit_message"] is None


def test_find_auth_code_route(monkeypatch):
    with patch("db.client.get_project", return_value={"id": "proj-123"}), \
         patch("memory.retrieval.retrieve_by_vector", return_value=[{"content": "auth login token", "table": "file_edits"}]):
        response = client.post("/projects/proj-123/find-auth-code", json={"query": "authentication"})
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == "proj-123"
        assert len(data["results"]) == 1


def test_continue_work_route(monkeypatch):
    with patch("db.client.get_project", return_value={"id": "proj-123"}), \
         patch("db.client.get_active_session", return_value={"id": "sess-1", "started_at": "2026-07-26"}), \
         patch("db.client.get_todos", return_value=[{"description": "Fix bug"}]), \
         patch("agent_actions._recent_memories", return_value=[]), \
         patch("ai.bedrock_client.invoke_reasoning", return_value="Fix bug in auth module"):
        response = client.post("/projects/proj-123/continue-work")
        assert response.status_code == 200
        data = response.json()
        assert data["suggestion"] == "Fix bug in auth module"


def test_project_summary_route(monkeypatch):
    with patch("db.client.get_project", return_value={"id": "proj-123", "name": "Test Project", "repo_path": "d:/AUTOMATA"}), \
         patch("agent_actions._recent_memories", return_value=[]), \
         patch("ai.bedrock_client.invoke_reasoning", return_value="- Bullet 1\n- Bullet 2"):
        response = client.post("/projects/proj-123/project-summary")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "- Bullet 1\n- Bullet 2"


def test_cross_app_tasks_route():
    response = client.post("/cross-app/tasks", json={
        "task_id": "task-test-1",
        "action": "drive_tool",
        "params": {"tool": "git", "repo_path": "d:/AUTOMATA", "command": "status"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("queued", "already_running")

    status_resp = client.get("/cross-app/tasks/task-test-1")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["task_id"] == "task-test-1"
