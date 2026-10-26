"""
tests/test_local_memory.py — Phase 1: offline-first local memory and routing.

Uses an in-memory SQLite store; no network, no CockroachDB.
"""

import time

import pytest

from memory import local_store
from memory.local_store import LocalStore, fts_query


@pytest.fixture
def store():
    s = LocalStore(":memory:")
    local_store.set_store(s)
    yield s
    local_store.set_store(None)
    s.close()


def test_fts_query_drops_stopwords_and_quotes_terms():
    assert fts_query("what did I do on the JWT auth?") == '"jwt"* OR "auth"*'
    assert fts_query("?!") == ""


def test_record_is_idempotent_by_ref(store):
    first = store.record("p1", "commit", "Commit abc: add login", ref="abc")
    again = store.record("p1", "commit", "Commit abc: add login", ref="abc")
    assert first is not None and again is None
    assert store.counts("p1") == {"commit": 1}


def test_record_redacts_secrets(store):
    store.record("p1", "terminal", "export API=1 token=supersecret123")
    content = store.recent("p1")[0]["content"]
    assert "supersecret123" not in content


def test_keyword_search_finds_relevant_memory_and_scopes_project(store):
    store.record("p1", "commit", "Add JWT authentication middleware")
    store.record("p1", "file_edit", "Edited src/styles/button.css")
    store.record("p2", "commit", "JWT refresh tokens for another project")
    hits = store.search("how does authentication work", project_id="p1")
    assert [h["content"] for h in hits] == ["Add JWT authentication middleware"]
    assert hits[0]["score"] > 0


def test_vector_search_blends_with_keywords(store):
    a = store.record("p1", "note", "database connection pooling")
    b = store.record("p1", "note", "colour palette for the dashboard")
    store.set_embedding(a, [1.0, 0.0, 0.0], "test")
    store.set_embedding(b, [0.0, 1.0, 0.0], "test")
    hits = store.search("pool", project_id="p1", query_embedding=[0.9, 0.1, 0.0])
    assert hits[0]["id"] == a


def test_recent_filters_kind_and_time(store):
    old = time.time() - 3 * 86400
    store.record("p1", "commit", "old commit", created_at=old)
    store.record("p1", "commit", "new commit")
    store.record("p1", "terminal", "npm test")
    recent = store.recent("p1", kinds=["commit"], since=time.time() - 86400)
    assert [r["content"] for r in recent] == ["new commit"]


def test_projects_round_trip_and_ordering(store):
    store.upsert_project({"id": "a", "name": "Alpha", "repo_path": "C:/a"}, source="cloud")
    store.upsert_project({"id": "b", "name": "Beta", "repo_path": "C:/b"}, source="local")
    store.touch_project("b")
    assert [p["id"] for p in store.list_projects()] == ["b", "a"]
    assert store.get_project("a")["source"] == "cloud"


def test_snapshots_keep_latest(store):
    store.save_snapshot("p1", {"branch": "main"}, "idle")
    store.save_snapshot("p1", {"branch": "feature/x"}, "shutdown")
    latest = store.latest_snapshot("p1")
    assert latest["data"]["branch"] == "feature/x"
    assert latest["reason"] == "shutdown"


def test_db_client_falls_back_to_local_projects(store):
    from db import client as db

    store.upsert_project({"id": "loc-1", "name": "Offline", "repo_path": "C:/x"}, source="local")
    assert any(p["id"] == "loc-1" for p in db.get_projects())
    assert db.get_project("loc-1")["name"] == "Offline"
    new_id = db.insert_project("Fresh", "C:/fresh")
    assert store.get_project(new_id)["source"] == "local"


def test_grounded_query_uses_local_memory_when_cloud_is_down(store, monkeypatch):
    import api.server as server

    store.record("p1", "commit", "Fix race condition in websocket reconnect")
    seen = {}

    def fake_reasoning(system_prompt, user_message, retrieved_memories, reasoning_mode=None):
        seen["memories"] = retrieved_memories
        return "Answer from memory"

    monkeypatch.setattr("ai.bedrock_client.invoke_reasoning", fake_reasoning)
    reply, sources, ok = server._grounded_query("what happened with the websocket?", "p1")
    assert ok is True and reply == "Answer from memory"
    assert any("websocket" in m["content"] for m in seen["memories"])


def test_reasoning_skips_cloud_when_offline(monkeypatch):
    import types
    import sys

    from ai import bedrock_client

    calls = []
    monkeypatch.setenv("AUTOMATA_FORCE_ONLINE", "0")
    monkeypatch.setattr(bedrock_client, "_invoke_groq_chat", lambda *a: calls.append("groq"))
    monkeypatch.setattr(bedrock_client, "_get_ollama_available", lambda: True)
    monkeypatch.setattr(bedrock_client, "_invoke_ollama_chat", lambda *a: calls.append("ollama") or "local answer")
    monkeypatch.setattr(sys.modules["config"], "settings", types.SimpleNamespace(
        reasoning_mode="auto", bedrock_available=True, groq_api_key="k", gemini_api_key="",
        nvidia_api_key="", minimax_api_key="", openrouter_api_key="", cohere_api_key="",
        ollama_base_url="http://x", ollama_model="qwen2.5-coder:3b", ollama_embedding_model="e",
    ))
    assert bedrock_client.invoke_reasoning("s", "u", []) == "local answer"
    assert calls == ["ollama"]
    assert bedrock_client.LAST_ANSWER["provider"] == "ollama"
