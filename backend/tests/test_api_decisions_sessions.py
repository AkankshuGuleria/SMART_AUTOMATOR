"""
tests/test_api_decisions_sessions.py — Phase 4.5 API tests for decisions and session end.

Tests the new GET /projects/{project_id}/decisions and
POST /projects/{project_id}/sessions/end endpoints.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.server import app

client = TestClient(app)


# ─── Decisions list ───────────────────────────────────────────────────────────

class TestListDecisions:

    @patch("db.client.get_decisions", return_value=[
        {"id": "d1", "decision": "ok", "rationale": "r", "decided_at": "2026-07-26T10:00:00"}
    ])
    def test_returns_decisions_for_project(self, mock_get):
        response = client.get("/projects/proj-123/decisions?limit=5")
        assert response.status_code == 200
        body = response.json()
        assert "decisions" in body
        assert len(body["decisions"]) == 1
        mock_get.assert_called_once_with(project_id="proj-123", limit=5)

    @patch("db.client.get_decisions", return_value=[])
    def test_default_limit(self, mock_get):
        response = client.get("/projects/proj-123/decisions")
        assert response.status_code == 200
        mock_get.assert_called_once_with(project_id="proj-123", limit=20)


# ─── End active session ───────────────────────────────────────────────────────

class TestEndActiveSession:

    @patch("db.client.get_active_session", return_value={"id": "sess-1", "started_at": "ts"})
    @patch("db.client.end_session", return_value=True)
    def test_ends_active_session(self, mock_end, mock_active):
        response = client.post("/projects/proj-123/sessions/end", json={"summary": "done"})
        assert response.status_code == 200
        body = response.json()
        assert body["ended"] is True
        assert body["session_id"] == "sess-1"
        mock_end.assert_called_once_with("proj-123", "sess-1", summary="done")

    @patch("db.client.get_active_session", return_value=None)
    def test_no_active_session_returns_error(self, mock_active):
        response = client.post("/projects/proj-123/sessions/end")
        assert response.status_code == 200
        body = response.json()
        assert "error" in body
        assert body.get("session_id") is None

    @patch("db.client.get_active_session", return_value={"id": "sess-1", "started_at": "ts"})
    @patch("db.client.end_session", return_value=False)
    def test_failed_end_returns_error(self, mock_end, mock_active):
        response = client.post("/projects/proj-123/sessions/end")
        assert response.status_code == 200
        body = response.json()
        assert "error" in body
        mock_end.assert_called_once_with("proj-123", "sess-1", summary=None)

    @patch("db.client.get_active_session", return_value={"id": "sess-1", "started_at": "ts"})
    @patch("db.client.end_session", return_value=True)
    def test_empty_body_is_accepted(self, mock_end, mock_active):
        response = client.post("/projects/proj-123/sessions/end")
        assert response.status_code == 200
        mock_end.assert_called_once_with("proj-123", "sess-1", summary=None)
