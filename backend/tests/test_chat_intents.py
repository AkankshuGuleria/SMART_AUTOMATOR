"""
tests/test_chat_intents.py — Tests for intent parsing and chat action executors.

Covers the GIT_LOG intent and the direct git log reply path, plus the
improved terse fallbacks in query_memory. No live LLM or DB calls.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.server import app
from decision_engine.intent_parser import IntentParser, IntentType
from decision_engine.planner import (
    _execute_chat_git_log,
    _execute_chat_query_memory,
    _detect_secondary_query,
    _get_actions_for_trigger,
)


# ─── Intent parsing ───────────────────────────────────────────────────────────

class TestGitLogIntent:

    def test_what_was_last_commit(self):
        p = IntentParser()
        result = p.parse("what was the last commit")
        assert result.intent == IntentType.GIT_LOG

    def test_show_my_recent_commits(self):
        p = IntentParser()
        result = p.parse("show me my recent commits")
        assert result.intent == IntentType.GIT_LOG

    def test_latest_commit(self):
        p = IntentParser()
        result = p.parse("what did I commit last")
        assert result.intent == IntentType.GIT_LOG

    def test_git_log_command(self):
        p = IntentParser()
        result = p.parse("git log")
        assert result.intent == IntentType.GIT_LOG

    def test_what_was_my_last_commit(self):
        p = IntentParser()
        result = p.parse("what was my last commit")
        assert result.intent == IntentType.GIT_LOG

    def test_most_recent_commit(self):
        p = IntentParser()
        result = p.parse("what was my most recent commit")
        assert result.intent == IntentType.GIT_LOG


class TestQueryMemoryIntent:
    """Ensure git-log-style questions don't fall through to QUERY_MEMORY."""

    def test_commit_question_does_not_go_to_query_memory(self):
        p = IntentParser()
        result = p.parse("what was the last commit")
        assert result.intent != IntentType.QUERY_MEMORY


# ─── _execute_chat_git_log ────────────────────────────────────────────────────

class TestExecuteChatGitLog:

    def test_no_project_returns_terse(self):
        result = _execute_chat_git_log({})
        assert result is None or result.get("answer") == "No project selected."

    @patch("db.client.get_commits", return_value=[])
    @patch("db.client.get_project", return_value={"repo_path": "", "name": "test"})
    def test_no_commits_returns_terse(self, mock_proj, mock_commits):
        result = _execute_chat_git_log({"project_id": "proj-123"})
        assert result["answer"] == "No commits found for this project."
        assert result["commits"] == []

    @patch("db.client.get_commits")
    def test_last_commit_answer(self, mock_commits):
        mock_commits.return_value = [{
            "commit_hash": "abcdef1234567890",
            "message": "Fix auth middleware",
            "author": "Alice",
            "committed_at": "2026-08-01 10:00:00",
        }]
        result = _execute_chat_git_log({
            "project_id": "proj-123",
            "question": "what was the last commit",
        })
        assert "Fix auth middleware" in result["answer"]
        assert "abcdef12" in result["answer"]
        assert "Alice" in result["answer"]
        assert result["commits"][0]["message"] == "Fix auth middleware"

    @patch("db.client.get_commits")
    def test_recent_commits_list(self, mock_commits):
        mock_commits.return_value = [
            {"commit_hash": "aaa111", "message": "feat: add login", "author": "Alice", "committed_at": "2026-08-01 10:00:00"},
            {"commit_hash": "bbb222", "message": "fix: typo", "author": "Bob", "committed_at": "2026-07-31 09:00:00"},
        ]
        result = _execute_chat_git_log({
            "project_id": "proj-123",
            "question": "show me recent commits",
        })
        assert "feat: add login" in result["answer"]
        assert "fix: typo" in result["answer"]
        assert "aaa111" in result["answer"]
        assert "bbb222" in result["answer"]

    @patch("os.path.isdir", return_value=True)
    @patch("db.client.get_project")
    @patch("db.client.get_commits", return_value=[])
    def test_falls_back_to_git(self, mock_commits, mock_proj, mock_isdir):
        mock_proj.return_value = {"repo_path": "/fake/repo", "name": "test"}
        fake_commit = type("FakeCommit", (), {
            "hexsha": "deadbeefdeadbeef",
            "message": "feat: new feature\n",
            "author": type("Author", (), {"name": "Alice"})(),
            "committed_datetime": type("DT", (), {
                "strftime": lambda self, fmt: "2026-08-01 12:00",
            })(),
        })
        # Mock the git module in sys.modules so the test doesn't require GitPython
        mock_git = MagicMock()
        mock_repo = mock_git.Repo.return_value
        mock_repo.iter_commits.return_value = iter([fake_commit()])
        with patch.dict("sys.modules", {"git": mock_git}):
            result = _execute_chat_git_log({
                "project_id": "proj-123",
                "question": "what was the last commit",
            })
        assert "feat: new feature" in result["answer"]
        assert "deadbeef" in result["answer"]

    @patch("db.client.get_project")
    @patch("db.client.get_commits", return_value=[])
    def test_falls_back_to_git_when_no_repo_path(self, mock_commits, mock_proj):
        mock_proj.return_value = {"repo_path": "", "name": "test"}
        result = _execute_chat_git_log({
            "project_id": "proj-123",
            "question": "what was the last commit",
        })
        assert result["answer"] == "No commits found for this project."


# ─── _execute_chat_query_memory fallbacks ─────────────────────────────────────

class TestQueryMemoryFallbacks:

    def test_no_llm_no_memories_returns_terse(self):
        with patch("memory.retrieval.retrieve_by_vector", return_value=[]), \
             patch("memory.retrieval.retrieve_recent", return_value=[]), \
             patch("ai.bedrock_client.invoke_reasoning", return_value=None):
            result = _execute_chat_query_memory({
                "project_id": "proj-123",
                "question": "what is the meaning of life",
                "raw": "what is the meaning of life",
                "reasoning_mode": None,
            })
        assert result is not None
        assert result["answer"] == "No AI backend is currently available. Install Ollama or configure API keys to enable responses."
        assert result["memories_used"] == 0

    def test_no_llm_with_memories_returns_listed(self):
        fake_memories = [
            {"table": "commits", "content": "feat: add login", "timestamp": "2026-08-01 10:00:00"},
        ]
        with patch("memory.retrieval.retrieve_by_vector", return_value=[]), \
             patch("memory.retrieval.retrieve_recent", return_value=fake_memories), \
             patch("ai.bedrock_client.invoke_reasoning", return_value=None):
            result = _execute_chat_query_memory({
                "project_id": "proj-123",
                "question": "what did I work on",
                "raw": "what did I work on",
                "reasoning_mode": None,
            })
        assert result is not None
        assert "feat: add login" in result["answer"]
        assert "commits" in result["answer"]


# ─── Compound request detection ───────────────────────────────────────────────

class TestCompoundRequestDetection:

    def test_detects_open_and_generate(self):
        assert _detect_secondary_query("open claude and generate a prompt for ui fix") is True

    def test_detects_open_and_create(self):
        assert _detect_secondary_query("open chrome and create a prompt for a ui/ux fix .md file") is True

    def test_detects_open_and_write(self):
        assert _detect_secondary_query("open claude and write a prompt") is True

    def test_detects_open_and_draft(self):
        assert _detect_secondary_query("open claude and draft a prompt") is True

    def test_detects_exact_user_message_with_typo(self):
        msg = "open claude and generate a promt i should give to it so that can create a whole ui/ux fix .md file"
        assert _detect_secondary_query(msg) is True

    def test_does_not_detect_simple_open(self):
        assert _detect_secondary_query("open claude") is False

    def test_does_not_detect_generate_without_open_context(self):
        assert _detect_secondary_query("generate a prompt") is False

    def test_get_actions_returns_secondary_for_open_browser(self):
        actions = _get_actions_for_trigger("chat:open_browser", {
            "message": "open claude and generate a prompt for ui fix",
            "parsed": {"target": "open claude and generate a prompt for ui fix"},
            "project_id": "proj-123",
        })
        type_list = [a["type"] for a in actions]
        assert "chat_open_browser" in type_list
        assert "chat_generate_prompt" in type_list

    def test_get_actions_single_action_for_plain_open(self):
        actions = _get_actions_for_trigger("chat:open_browser", {
            "message": "open claude",
            "parsed": {"target": "open claude"},
            "project_id": "proj-123",
        })
        type_list = [a["type"] for a in actions]
        assert type_list == ["chat_open_browser"]


class TestChatRouteIntentRouting:

    def test_open_chatgpt_routes_to_cross_app_control(self):
        with patch("agent_actions.open_app_or_url", return_value={
            "success": True,
            "action": "open_browser",
            "message": "Opened https://chatgpt.com",
        }) as mock_open:
            response = TestClient(app).post("/chat", json={
                "message": "open chatgpt",
                "project_id": "proj-123",
            })

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "open_browser"
        assert body["actions"][0]["type"] == "chat_open_browser"
        assert body["actions"][0]["executed"] is True
        assert "general_assistant" != body["intent"]
        mock_open.assert_called_once()

    def test_open_spotify_routes_to_app_control(self):
        with patch("agent_actions.open_app_or_url", return_value={
            "success": True,
            "action": "open_app",
            "message": "Launched spotify",
        }) as mock_open:
            response = TestClient(app).post("/chat", json={
                "message": "open spotify",
                "project_id": "proj-123",
            })

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "open_app"
        assert body["actions"][0]["type"] == "chat_open_app"
        assert body["actions"][0]["executed"] is True
        mock_open.assert_called_once()

    def test_paste_clipboard_pauses_for_confirmation(self):
        with patch("automation.os_windows.paste_clipboard") as mock_paste:
            response = TestClient(app).post("/chat", json={
                "message": "paste it there",
                "project_id": "proj-123",
            })

        assert response.status_code == 200
        body = response.json()
        assert body["intent"] == "paste_clipboard"
        assert body["actions"][0]["policy"] == "confirm_once"
        assert body["actions"][0]["executed"] is False
        mock_paste.assert_not_called()
